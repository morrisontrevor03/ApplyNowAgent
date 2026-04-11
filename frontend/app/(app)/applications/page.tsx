"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { applications, ApplicationDraft } from "@/lib/api";
import { FileText, ExternalLink } from "lucide-react";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-emerald-400/10 text-emerald-400",
    draft: "bg-blue-400/10 text-blue-400",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[status] ?? "bg-white/5 text-zinc-400"}`}>
      {status}
    </span>
  );
}

export default function ApplicationsPage() {
  const { data = [], isLoading } = useQuery<ApplicationDraft[]>({
    queryKey: ["applications"],
    queryFn: () => applications.list(),
  });

  if (isLoading) return <div className="animate-pulse text-zinc-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Applications</h1>
        <p className="text-sm text-zinc-400 mt-1">Tailored drafts ready for you to apply</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl border border-white/8 bg-white/3 p-12 text-center grid-bg">
          <FileText className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400 text-sm">No drafts yet.</p>
          <p className="text-zinc-500 text-xs mt-1">The Application Agent creates tailored drafts for high-match jobs.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((app) => (
            <div key={app.id} className="rounded-xl border border-white/8 bg-white/3 p-5 flex items-center justify-between gap-4 hover:border-white/12 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge status={app.status} />
                  <span className="text-xs text-zinc-500">{new Date(app.created_at).toLocaleDateString()}</span>
                </div>
                <h3 className="font-medium text-zinc-100 truncate">{app.job?.title ?? "Unknown role"}</h3>
                <p className="text-sm text-zinc-400">{app.job?.company}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {app.job && (
                  <a
                    href={app.job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                <Link
                  href={`/applications/${app.id}`}
                  className="text-xs font-medium text-white bg-white/8 hover:bg-white/12 rounded-lg px-3 py-1.5 transition-colors"
                >
                  Review →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
