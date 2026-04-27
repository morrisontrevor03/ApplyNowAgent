"use client";
import { useMemo, useRef, useState, useCallback, useEffect } from "react";
import { Contact } from "@/lib/api";

// ── Constants ────────────────────────────────────────────────────────────

const NODE_R = 26;

const STAGE_COLORS: Record<string, string> = {
  discovered:        "#71717a",
  message_drafted:   "#60a5fa",
  sent:              "#a78bfa",
  replied:           "#fbbf24",
  meeting_scheduled: "#34d399",
};

const STAGE_LABELS: Record<string, string> = {
  discovered:        "Discovered",
  message_drafted:   "Drafted",
  sent:              "Sent",
  replied:           "Replied",
  meeting_scheduled: "Meeting",
};

// ── Helpers ──────────────────────────────────────────────────────────────

function initials(c: Contact) {
  const parts = [c.first_name, c.last_name].filter(Boolean);
  return parts.length ? parts.map((p) => p![0].toUpperCase()).join("") : "?";
}

function displayName(c: Contact) {
  const name = [c.first_name, c.last_name].filter(Boolean).join(" ") || "Unknown";
  return name.length > 16 ? name.slice(0, 14) + "…" : name;
}

// ── Layout ───────────────────────────────────────────────────────────────

interface LayoutNode {
  contact: Contact;
  x: number;
  y: number;
}

interface LayoutEdge {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface GroupLabel {
  company: string;
  cx: number;
  cy: number;
  clusterR: number;
}

function buildLayout(contacts: Contact[]): {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  labels: GroupLabel[];
} {
  if (!contacts.length) return { nodes: [], edges: [], labels: [] };

  // Group by company
  const byCompany = new Map<string, Contact[]>();
  for (const c of contacts) {
    const arr = byCompany.get(c.company) ?? [];
    arr.push(c);
    byCompany.set(c.company, arr);
  }

  // Sort by member count descending
  const companies = Array.from(byCompany.entries()).sort((a, b) => b[1].length - a[1].length);
  const numCompanies = companies.length;

  // Grid layout for companies
  const cols = Math.max(1, Math.ceil(Math.sqrt(numCompanies * 1.4)));
  const numRows = Math.ceil(numCompanies / cols);
  const COL_W = 280;
  const ROW_H = 240;

  const nodes: LayoutNode[] = [];
  const edges: LayoutEdge[] = [];
  const labels: GroupLabel[] = [];

  companies.forEach(([company, members], i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const cx = (col - (Math.min(cols, numCompanies) - 1) / 2) * COL_W;
    const cy = (row - (numRows - 1) / 2) * ROW_H;

    const clusterR = members.length === 1 ? 0 : Math.min(75, 32 + members.length * 10);
    labels.push({ company, cx, cy, clusterR });

    const companyNodes: LayoutNode[] = [];

    members.forEach((contact, j) => {
      let x: number;
      let y: number;

      if (members.length === 1) {
        x = cx;
        y = cy;
      } else {
        const angle = (j / members.length) * 2 * Math.PI - Math.PI / 2;
        x = cx + Math.cos(angle) * clusterR;
        y = cy + Math.sin(angle) * clusterR;
      }

      companyNodes.push({ contact, x, y });
      nodes.push({ contact, x, y });
    });

    // Edges within company
    if (companyNodes.length >= 2) {
      if (companyNodes.length <= 6) {
        // All pairs
        for (let a = 0; a < companyNodes.length; a++) {
          for (let b = a + 1; b < companyNodes.length; b++) {
            edges.push({
              id: `e-${companyNodes[a].contact.id}-${companyNodes[b].contact.id}`,
              x1: companyNodes[a].x, y1: companyNodes[a].y,
              x2: companyNodes[b].x, y2: companyNodes[b].y,
            });
          }
        }
      } else {
        // Hub-spoke: highest relevance as hub
        const hub = [...companyNodes].sort(
          (a, b) => (b.contact.relevance_score ?? 0) - (a.contact.relevance_score ?? 0)
        )[0];
        for (const n of companyNodes) {
          if (n === hub) continue;
          edges.push({
            id: `e-${hub.contact.id}-${n.contact.id}`,
            x1: hub.x, y1: hub.y,
            x2: n.x, y2: n.y,
          });
        }
      }
    }
  });

  return { nodes, edges, labels };
}

// ── Graph component ───────────────────────────────────────────────────────

export function NetworkGraph({
  contacts,
  onSelectContact,
  selectedId,
}: {
  contacts: Contact[];
  onSelectContact: (c: Contact) => void;
  selectedId: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [containerSize, setContainerSize] = useState({ w: 800, h: 600 });
  const isPanning = useRef(false);
  const lastPointer = useRef({ x: 0, y: 0 });

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setContainerSize({ w: width, h: height });
    });
    ro.observe(el);
    const { width, height } = el.getBoundingClientRect();
    setContainerSize({ w: width, h: height });
    return () => ro.disconnect();
  }, []);

  const { nodes, edges, labels } = useMemo(() => buildLayout(contacts), [contacts]);

  // Zoom toward a point
  const applyZoom = useCallback((factor: number, mouseX: number, mouseY: number) => {
    const halfW = containerSize.w / 2;
    const halfH = containerSize.h / 2;
    setScale((oldScale) => {
      const newScale = Math.min(3, Math.max(0.12, oldScale * factor));
      const ratio = newScale / oldScale;
      setPan((p) => ({
        x: mouseX - halfW - (mouseX - halfW - p.x) * ratio,
        y: mouseY - halfH - (mouseY - halfH - p.y) * ratio,
      }));
      return newScale;
    });
  }, [containerSize.w, containerSize.h]);

  // Wheel zoom (passive: false so we can preventDefault)
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      applyZoom(e.deltaY > 0 ? 0.88 : 1.14, e.clientX - rect.left, e.clientY - rect.top);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [applyZoom]);

  // Pan
  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const target = e.target as Element;
    if (target.closest("[data-node]")) return;
    isPanning.current = true;
    lastPointer.current = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPointer.current.x;
    const dy = e.clientY - lastPointer.current.y;
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
    lastPointer.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onPointerUp = useCallback(() => { isPanning.current = false; }, []);

  const halfW = containerSize.w / 2;
  const halfH = containerSize.h / 2;
  const transform = `translate(${halfW + pan.x}, ${halfH + pan.y}) scale(${scale})`;

  return (
    <div
      ref={containerRef}
      className="relative w-full rounded-xl border border-white/8 overflow-hidden select-none"
      style={{ height: "calc(100vh - 260px)", minHeight: 480, background: "#080808", cursor: isPanning.current ? "grabbing" : "grab" }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    >
      {/* Dot-grid background */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern
            id="dotgrid"
            width="32"
            height="32"
            patternUnits="userSpaceOnUse"
            patternTransform={`translate(${(halfW + pan.x) % 32}, ${(halfH + pan.y) % 32})`}
          >
            <circle cx="1" cy="1" r="0.8" fill="rgba(255,255,255,0.07)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dotgrid)" />
      </svg>

      {/* Main graph */}
      <svg width="100%" height="100%" style={{ display: "block", position: "relative" }}>
        <g transform={transform}>
          {/* Edges */}
          {edges.map((e) => (
            <line
              key={e.id}
              x1={e.x1} y1={e.y1}
              x2={e.x2} y2={e.y2}
              stroke="white"
              strokeOpacity={0.1}
              strokeWidth={1.5 / scale}
            />
          ))}

          {/* Company labels */}
          {labels.map(({ company, cx, cy, clusterR }) => (
            <text
              key={company}
              x={cx}
              y={cy - clusterR - NODE_R - 14}
              textAnchor="middle"
              fontSize={11}
              fontWeight={500}
              fill="#3f3f46"
              style={{ userSelect: "none", pointerEvents: "none" }}
            >
              {company.length > 22 ? company.slice(0, 20) + "…" : company}
            </text>
          ))}

          {/* Nodes */}
          {nodes.map((node) => {
            const color = STAGE_COLORS[node.contact.outreach_status] ?? "#71717a";
            const isSelected = selectedId === node.contact.id;
            return (
              <g
                key={node.contact.id}
                data-node="true"
                transform={`translate(${node.x}, ${node.y})`}
                onClick={() => onSelectContact(node.contact)}
                style={{ cursor: "pointer" }}
              >
                {/* Selection halo */}
                {isSelected && (
                  <circle
                    r={NODE_R + 8}
                    fill="none"
                    stroke="white"
                    strokeWidth={1.5}
                    opacity={0.25}
                  />
                )}
                {/* Status glow ring */}
                <circle
                  r={NODE_R + 5}
                  fill="none"
                  stroke={color}
                  strokeWidth={1}
                  opacity={0.2}
                />
                {/* Body */}
                <circle
                  r={NODE_R}
                  fill="#131315"
                  stroke={color}
                  strokeWidth={2.5}
                />
                {/* Initials */}
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={11}
                  fontWeight={700}
                  fill="white"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {initials(node.contact)}
                </text>
                {/* Name label */}
                <text
                  y={NODE_R + 14}
                  textAnchor="middle"
                  fontSize={10}
                  fill="#71717a"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {displayName(node.contact)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Zoom controls */}
      <div
        className="absolute bottom-4 right-4 z-10 flex flex-col gap-1"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => applyZoom(1.25, containerSize.w / 2, containerSize.h / 2)}
          className="h-8 w-8 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 border border-white/8 text-zinc-300 flex items-center justify-center text-lg font-light transition-colors"
        >+</button>
        <button
          onClick={() => applyZoom(0.8, containerSize.w / 2, containerSize.h / 2)}
          className="h-8 w-8 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 border border-white/8 text-zinc-300 flex items-center justify-center text-lg font-light transition-colors"
        >−</button>
        <button
          onClick={() => { setScale(1); setPan({ x: 0, y: 0 }); }}
          className="h-8 w-8 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 border border-white/8 text-zinc-500 flex items-center justify-center text-sm transition-colors"
          title="Reset view"
        >↺</button>
      </div>

      {/* Legend */}
      <div
        className="absolute top-3 left-3 z-10 rounded-xl border border-white/8 bg-zinc-950/90 backdrop-blur-sm p-3 space-y-1.5"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <p className="text-xs font-medium text-zinc-500 mb-1">Stage</p>
        {Object.entries(STAGE_LABELS).map(([key, label]) => (
          <div key={key} className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full shrink-0" style={{ background: STAGE_COLORS[key] }} />
            <span className="text-xs text-zinc-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Stats footer */}
      <div className="absolute bottom-4 left-4 z-10 pointer-events-none">
        <span className="text-xs text-zinc-700">
          {contacts.length} contact{contacts.length !== 1 ? "s" : ""} · {labels.length} compan{labels.length !== 1 ? "ies" : "y"}
        </span>
      </div>
    </div>
  );
}
