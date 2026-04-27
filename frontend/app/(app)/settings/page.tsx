"use client";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { settingsApi, Preferences } from "@/lib/api";
import { X, Plus } from "lucide-react";

function TagInput({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState("");

  const add = () => {
    const trimmed = input.trim();
    if (trimmed && !items.includes(trimmed)) {
      onChange([...items, trimmed]);
    }
    setInput("");
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-slate-400">{label}</label>
      <div className="flex flex-wrap gap-1.5 min-h-[32px]">
        {items.map((item) => (
          <span key={item} className="flex items-center gap-1 text-xs bg-violet-500/10 border border-violet-500/20 text-violet-200 px-2.5 py-1 rounded-full">
            {item}
            <button onClick={() => onChange(items.filter((i) => i !== item))}>
              <X className="h-3 w-3 text-violet-400 hover:text-violet-200" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder={placeholder}
          className="flex-1 rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-1.5 text-sm text-[#ededff] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
        />
        <button
          onClick={add}
          className="flex items-center gap-1 text-xs text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 rounded-lg px-3 py-1.5 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> Add
        </button>
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange, description }: { label: string; checked: boolean; onChange: (v: boolean) => void; description?: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-[#ededff]">{label}</p>
        {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors shrink-0 ${checked ? "bg-violet-600" : "bg-violet-500/15"}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Preferences>({ queryKey: ["settings"], queryFn: settingsApi.get });
  const [form, setForm] = useState<Partial<Preferences>>({});
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const update = (patch: Partial<Preferences>) => {
    setForm((f) => ({ ...f, ...patch }));
    setDirty(true);
  };

  const save = useMutation({
    mutationFn: () => settingsApi.update(form),
    onSuccess: () => { toast.success("Settings saved"); setDirty(false); qc.invalidateQueries({ queryKey: ["settings"] }); },
    onError: () => toast.error("Failed to save"),
  });

  if (isLoading) return <div className="animate-pulse text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Configure what your agents search for</p>
      </div>

      {/* Job targets */}
      <div className="rounded-xl border border-violet-500/12 bg-violet-500/3 p-6 space-y-5">
        <h2 className="text-sm font-medium">Job Targets</h2>
        <TagInput
          label="Target roles"
          items={form.target_roles ?? []}
          onChange={(v) => update({ target_roles: v })}
          placeholder="e.g. Software Engineer"
        />
        <TagInput
          label="Target companies"
          items={form.target_companies ?? []}
          onChange={(v) => update({ target_companies: v })}
          placeholder="e.g. Stripe"
        />
        {(form.target_companies ?? []).length > 0 && (
          <label className="flex items-start gap-3 cursor-pointer group">
            <div className="relative mt-0.5">
              <input
                type="checkbox"
                checked={form.open_to_similar_companies ?? false}
                onChange={(e) => update({ open_to_similar_companies: e.target.checked })}
                className="sr-only"
              />
              <div className={`h-4 w-4 rounded border transition-colors ${
                form.open_to_similar_companies
                  ? "bg-violet-600 border-violet-600"
                  : "border-violet-500/25 bg-violet-500/5 group-hover:border-violet-500/50"
              }`}>
                {form.open_to_similar_companies && (
                  <svg viewBox="0 0 10 8" className="w-full h-full p-0.5" fill="none">
                    <path d="M1 4l3 3 5-6" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
            </div>
            <div>
              <p className="text-sm text-[#ededff]">Also target similar companies</p>
              <p className="text-xs text-slate-500 mt-0.5">
                The networking agent will expand your list to ~25 companies by finding ones similar to the companies you listed.
              </p>
            </div>
          </label>
        )}
        <TagInput
          label="Locations"
          items={form.target_locations ?? []}
          onChange={(v) => update({ target_locations: v })}
          placeholder="e.g. Remote"
        />
        <TagInput
          label="Excluded companies"
          items={form.excluded_companies ?? []}
          onChange={(v) => update({ excluded_companies: v })}
          placeholder="Companies to skip"
        />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Min salary ($)</label>
            <input
              type="number"
              value={form.min_salary ?? ""}
              onChange={(e) => update({ min_salary: e.target.value ? Number(e.target.value) : undefined })}
              className="w-full rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-1.5 text-sm text-[#ededff] focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              placeholder="80000"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Experience level</label>
            <select
              value={form.experience_level ?? ""}
              onChange={(e) => update({ experience_level: e.target.value || null })}
              className="w-full rounded-lg border border-violet-500/15 bg-[#0d0d1a] px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
            >
              <option value="">Any</option>
              {["entry", "junior", "mid", "senior", "staff", "lead"].map((l) => (
                <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Agent toggles */}
      <div className="rounded-xl border border-violet-500/12 bg-violet-500/3 p-6 space-y-4">
        <h2 className="text-sm font-medium">Agent Settings</h2>
        <Toggle
          label="Job Scout"
          description="Searches for new jobs every 30 minutes"
          checked={form.scout_enabled ?? true}
          onChange={(v) => update({ scout_enabled: v })}
        />
        <div className="border-t border-violet-500/8" />
        <Toggle
          label="Networking Agent"
          description="Finds contacts at your target companies twice daily"
          checked={form.networking_enabled ?? true}
          onChange={(v) => update({ networking_enabled: v })}
        />
        <div className="border-t border-violet-500/8" />
        <Toggle
          label="Application Agent"
          description="Auto-drafts tailored resumes and cover letters"
          checked={form.application_agent_enabled ?? true}
          onChange={(v) => update({ application_agent_enabled: v })}
        />
      </div>

      {dirty && (
        <div className="flex items-center gap-3">
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50 transition-colors shadow-lg shadow-violet-500/20"
          >
            {save.isPending ? "Saving…" : "Save changes"}
          </button>
          <button
            onClick={() => { setForm(data ?? {}); setDirty(false); }}
            className="text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
