"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { settingsApi } from "@/lib/api";
import { Zap, ChevronRight, Check } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

type SalaryType = "salary" | "hourly";
type VibeKey = "startup" | "corporate" | "small_business" | "remote";

interface OnboardingState {
  // Step 1 – Roles
  target_roles: string[];
  experience_level: string;
  // Step 2 – Salary
  salary_type: SalaryType;
  min_salary: number | null;
  // Step 3 – Location
  target_locations: string[];
  location_flexible: boolean;
  // Step 4 – Vibe
  work_environment: VibeKey[];
}

// ── Small reusable pieces ─────────────────────────────────────────────────

function TagInput({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState("");

  const add = () => {
    const trimmed = input.trim();
    if (trimmed && !items.includes(trimmed)) onChange([...items, trimmed]);
    setInput("");
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder={placeholder}
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-white/20"
        />
        <button
          type="button"
          onClick={add}
          className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-300 hover:bg-white/10 transition-colors"
        >
          Add
        </button>
      </div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <span
              key={item}
              className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs text-zinc-200"
            >
              {item}
              <button
                type="button"
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="text-zinc-500 hover:text-zinc-300 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function VibeCard({
  selected,
  onClick,
  label,
  description,
  emoji,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  description: string;
  emoji: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-col gap-1.5 rounded-xl border p-4 text-left transition-all ${
        selected
          ? "border-white/40 bg-white/10"
          : "border-white/8 bg-white/3 hover:border-white/20 hover:bg-white/6"
      }`}
    >
      {selected && (
        <span className="absolute right-3 top-3 flex h-4 w-4 items-center justify-center rounded-full bg-white">
          <Check className="h-2.5 w-2.5 text-zinc-900" />
        </span>
      )}
      <span className="text-xl">{emoji}</span>
      <span className="text-sm font-medium text-zinc-100">{label}</span>
      <span className="text-xs text-zinc-500">{description}</span>
    </button>
  );
}

// ── Step components ───────────────────────────────────────────────────────

function StepRoles({
  state,
  update,
}: {
  state: OnboardingState;
  update: (patch: Partial<OnboardingState>) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">What roles are you targeting?</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Your agents will search for these job titles. Add as many as you like.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-zinc-400">Job titles</label>
        <TagInput
          items={state.target_roles}
          onChange={(v) => update({ target_roles: v })}
          placeholder="e.g. Software Engineer, Product Manager"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-zinc-400">Experience level</label>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {["entry", "junior", "mid", "senior", "staff", "lead"].map((lvl) => (
            <button
              key={lvl}
              type="button"
              onClick={() =>
                update({ experience_level: state.experience_level === lvl ? "" : lvl })
              }
              className={`rounded-lg border py-2 text-xs font-medium capitalize transition-all ${
                state.experience_level === lvl
                  ? "border-white/40 bg-white/10 text-white"
                  : "border-white/8 bg-white/3 text-zinc-400 hover:border-white/20 hover:text-zinc-200"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function StepSalary({
  state,
  update,
}: {
  state: OnboardingState;
  update: (patch: Partial<OnboardingState>) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">What&apos;s your salary goal?</h2>
        <p className="mt-1 text-sm text-zinc-400">
          We&apos;ll only surface jobs that meet your minimum. Leave blank to see everything.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-zinc-400">Pay structure</label>
        <div className="flex gap-2">
          {(["salary", "hourly"] as SalaryType[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => update({ salary_type: t })}
              className={`flex-1 rounded-lg border py-2.5 text-sm font-medium capitalize transition-all ${
                state.salary_type === t
                  ? "border-white/40 bg-white/10 text-white"
                  : "border-white/8 bg-white/3 text-zinc-400 hover:border-white/20 hover:text-zinc-200"
              }`}
            >
              {t === "salary" ? "Annual salary" : "Hourly rate"}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-zinc-400">
          Minimum {state.salary_type === "hourly" ? "hourly rate ($)" : "annual salary ($)"}
        </label>
        <input
          type="number"
          value={state.min_salary ?? ""}
          onChange={(e) =>
            update({ min_salary: e.target.value ? Number(e.target.value) : null })
          }
          placeholder={state.salary_type === "hourly" ? "e.g. 50" : "e.g. 100000"}
          className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-white/20"
        />
      </div>
    </div>
  );
}

function StepLocation({
  state,
  update,
}: {
  state: OnboardingState;
  update: (patch: Partial<OnboardingState>) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Where do you want to work?</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Add cities, states, or &quot;Remote&quot;. You can add multiple.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-zinc-400">Preferred locations</label>
        <TagInput
          items={state.target_locations}
          onChange={(v) => update({ target_locations: v })}
          placeholder="e.g. New York, Remote, Austin TX"
        />
      </div>

      <div className="space-y-3">
        <label className="text-xs font-medium text-zinc-400">How firm is this?</label>
        <div className="flex gap-2">
          {[
            { value: false, label: "Firm", description: "Only show jobs in these locations" },
            { value: true, label: "Flexible", description: "Also show jobs nearby or remote" },
          ].map(({ value, label, description }) => (
            <button
              key={label}
              type="button"
              onClick={() => update({ location_flexible: value })}
              className={`flex-1 rounded-xl border p-3.5 text-left transition-all ${
                state.location_flexible === value
                  ? "border-white/40 bg-white/10"
                  : "border-white/8 bg-white/3 hover:border-white/20"
              }`}
            >
              <p className="text-sm font-medium text-zinc-100">{label}</p>
              <p className="mt-0.5 text-xs text-zinc-500">{description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function StepVibe({
  state,
  update,
}: {
  state: OnboardingState;
  update: (patch: Partial<OnboardingState>) => void;
}) {
  const toggle = (key: VibeKey) => {
    const current = state.work_environment;
    update({
      work_environment: current.includes(key)
        ? current.filter((k) => k !== key)
        : [...current, key],
    });
  };

  const vibes: Array<{ key: VibeKey; label: string; description: string; emoji: string }> = [
    { key: "startup", label: "Startup", description: "Fast-paced, early-stage, equity-driven", emoji: "🚀" },
    { key: "corporate", label: "Corporate", description: "Established org, structure, benefits", emoji: "🏢" },
    { key: "small_business", label: "Small business", description: "Close-knit team, wide ownership", emoji: "🏪" },
    { key: "remote", label: "Remote-first", description: "Async culture, distributed teams", emoji: "🌍" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">What&apos;s your vibe?</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Pick all that apply — your agents will prioritize matching companies.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {vibes.map((v) => (
          <VibeCard
            key={v.key}
            selected={state.work_environment.includes(v.key)}
            onClick={() => toggle(v.key)}
            label={v.label}
            description={v.description}
            emoji={v.emoji}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main onboarding page ──────────────────────────────────────────────────

const STEPS = ["Roles", "Salary", "Location", "Vibe"] as const;

const INITIAL: OnboardingState = {
  target_roles: [],
  experience_level: "",
  salary_type: "salary",
  min_salary: null,
  target_locations: [],
  location_flexible: true,
  work_environment: [],
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<OnboardingState>(INITIAL);
  const [saving, setSaving] = useState(false);

  const update = (patch: Partial<OnboardingState>) =>
    setState((s) => ({ ...s, ...patch }));

  const next = () => setStep((s) => s + 1);
  const back = () => setStep((s) => s - 1);

  const finish = async () => {
    setSaving(true);
    try {
      await settingsApi.update({
        target_roles: state.target_roles,
        experience_level: state.experience_level || null,
        salary_type: state.salary_type,
        min_salary: state.min_salary,
        target_locations: state.target_locations,
        location_flexible: state.location_flexible,
        work_environment: state.work_environment,
      });
      router.replace("/resume");
    } catch {
      toast.error("Failed to save preferences, please try again.");
      setSaving(false);
    }
  };

  const isLast = step === STEPS.length - 1;

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 grid-bg px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <h1 className="text-xl font-semibold">Set up your job search</h1>
          <p className="text-sm text-zinc-400">Takes about 60 seconds. You can change this any time.</p>
        </div>

        {/* Step indicators */}
        <div className="mb-6 flex items-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex flex-1 items-center gap-2">
              <div className="flex flex-1 flex-col items-center gap-1">
                <div
                  className={`h-1 w-full rounded-full transition-all ${
                    i <= step ? "bg-white" : "bg-white/15"
                  }`}
                />
                <span
                  className={`text-[10px] font-medium ${
                    i === step ? "text-zinc-200" : "text-zinc-600"
                  }`}
                >
                  {label}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="rounded-xl border border-white/8 bg-white/3 p-6">
          {step === 0 && <StepRoles state={state} update={update} />}
          {step === 1 && <StepSalary state={state} update={update} />}
          {step === 2 && <StepLocation state={state} update={update} />}
          {step === 3 && <StepVibe state={state} update={update} />}
        </div>

        {/* Navigation */}
        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={step === 0 ? () => router.replace("/resume") : back}
            className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            {step === 0 ? "Skip for now" : "Back"}
          </button>

          <button
            type="button"
            onClick={isLast ? finish : next}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : isLast ? "Finish setup" : "Continue"}
            {!saving && !isLast && <ChevronRight className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
