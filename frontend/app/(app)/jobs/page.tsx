"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { jobs, Job } from "@/lib/api";
import { ExternalLink, X, MapPin, DollarSign } from "lucide-react";
import Link from "next/link";

function MatchBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 85 ? "text-emerald-400 bg-emerald-400/10" : pct >= 70 ? "text-amber-400 bg-amber-400/10" : "text-slate-400 bg-violet-500/5";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${pct >= 85 ? "bg-emerald-400" : pct >= 70 ? "bg-amber-400" : "bg-slate-400"}`} />
      {pct}%
    </span>
  );
}

function JobCard({ job, onDismiss }: { job: Job; onDismiss: (id: string) => void }) {
  return (
    <div className={`rounded-xl border ${job.is_new ? "border-violet-500/25 bg-violet-500/5" : "border-violet-500/12 bg-violet-500/3"} p-5 flex flex-col gap-3 hover:border-violet-500/30 transition-colors`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {job.is_new && (
              <span className="text-xs font-medium text-violet-300 bg-violet-500/15 border border-violet-500/20 px-2 py-0.5 rounded-full">New</span>
            )}
            <MatchBadge score={job.match_score} />
          </div>
          <h3 className="font-medium text-[#ededff] leading-snug">{job.title}</h3>
          <p className="text-sm text-slate-400 mt-0.5">{job.company}</p>
        </div>
        <button
          onClick={() => onDismiss(job.id)}
          className="shrink-0 text-slate-600 hover:text-slate-400 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Meta */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {job.location && (
          <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>
        )}
        {(job.salary_min || job.salary_max) && (
          <span className="flex items-center gap-1">
            <DollarSign className="h-3 w-3" />
            {job.salary_min ? `$${(job.salary_min / 1000).toFixed(0)}k` : ""}
            {job.salary_min && job.salary_max ? " – " : ""}
            {job.salary_max ? `$${(job.salary_max / 1000).toFixed(0)}k` : ""}
          </span>
        )}
        {job.employment_type && <span>{job.employment_type.replace("_", " ")}</span>}
      </div>

      {/* Reasoning */}
      {job.match_reasoning && (
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{job.match_reasoning}</p>
      )}

      <div className="flex items-center gap-2 mt-1">
        <Link
          href={`/jobs/${job.id}`}
          className="text-xs font-medium text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 rounded-lg px-3 py-1.5 transition-colors"
        >
          View Draft
        </Link>
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ExternalLink className="h-3 w-3" /> Original posting
        </a>
      </div>
    </div>
  );
}

export default function JobsPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: () => jobs.list(),
  });

  const dismissMutation = useMutation({
    mutationFn: jobs.dismiss,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
    onError: () => toast.error("Failed to dismiss"),
  });

  if (isLoading) return <div className="animate-pulse text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Jobs</h1>
          <p className="text-sm text-slate-400 mt-1">{data.length} job{data.length !== 1 ? "s" : ""} found</p>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl border border-violet-500/12 bg-violet-500/3 p-12 text-center grid-bg">
          <p className="text-slate-400 text-sm">No jobs yet. The Job Scout agent runs every 30 minutes.</p>
          <p className="text-slate-500 text-xs mt-2">You can trigger it manually from the Dashboard.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((job) => (
            <JobCard key={job.id} job={job} onDismiss={(id) => dismissMutation.mutate(id)} />
          ))}
        </div>
      )}
    </div>
  );
}
