import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_run import AgentRun


class BaseAgent:
    """
    Base class for all ApplyNow agents.

    Wraps the Anthropic Claude tool-use loop and provides:
    - Automatic tool dispatch via subclass implementation of `dispatch_tool`
    - Agent run logging to the database
    - Token tracking
    """

    agent_type: str = "base"
    model: str = "claude-sonnet-4-6"
    max_iterations: int = 20

    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=6,  # up from default 2; SDK uses exponential backoff on 429/529
        )
        self._tool_calls_log: list[dict] = []
        self._total_tokens: int = 0
        self._run: AgentRun | None = None

    async def run(self, trigger: str = "scheduled", **kwargs) -> dict:
        """Entry point. Creates an AgentRun record, executes the agent, updates the record."""
        self._run = AgentRun(
            user_id=self.user_id,
            agent_type=self.agent_type,
            trigger=trigger,
            status="running",
            input_data=kwargs,
        )
        self.db.add(self._run)
        await self.db.commit()

        start_ms = int(time.time() * 1000)
        result: dict = {}
        try:
            result = await self._execute(**kwargs)
            self._run.status = "completed"
            self._run.output_summary = result.get("summary", "")
            self._run.jobs_found = result.get("jobs_found", 0)
            self._run.contacts_found = result.get("contacts_found", 0)
            self._run.applications_created = result.get("applications_created", 0)
        except Exception as exc:
            self._run.status = "failed"
            self._run.error_message = str(exc)
            raise
        finally:
            self._run.tool_calls = self._tool_calls_log
            self._run.tokens_used = self._total_tokens
            self._run.completed_at = datetime.now(timezone.utc)
            self._run.duration_ms = int(time.time() * 1000) - start_ms
            await self.db.commit()

        return result

    async def _execute(self, **kwargs) -> dict:
        """Override in subclasses to implement agent logic."""
        raise NotImplementedError

    async def run_tool_loop(
        self,
        system_prompt: str,
        initial_message: str,
        tools: list[dict],
    ) -> str:
        """
        Runs the Claude tool-use agentic loop until stop_reason == "end_turn".
        Returns the final text response.
        """
        messages: list[dict] = [{"role": "user", "content": initial_message}]

        for _ in range(self.max_iterations):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
            messages.append({"role": "assistant", "content": response.content})

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if tool_use_blocks:
                # Always respond with a tool_result for every tool_use block,
                # regardless of stop_reason (guards against "max_tokens" edge cases).
                tool_results = []
                for block in tool_use_blocks:
                    self._tool_calls_log.append({
                        "tool": block.name,
                        "input": block.input,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    try:
                        result = await self.dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                    except Exception as exc:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {exc}",
                            "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

        return "Max iterations reached"

    async def dispatch_tool(self, name: str, input_data: dict) -> Any:
        """Override in subclasses to handle tool calls."""
        raise NotImplementedError(f"Tool '{name}' not implemented in {self.__class__.__name__}")
