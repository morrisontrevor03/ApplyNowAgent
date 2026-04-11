"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { contacts, Contact } from "@/lib/api";
import { Copy, ExternalLink, Users } from "lucide-react";

const STATUS_OPTIONS = [
  "discovered", "message_drafted", "sent", "replied", "meeting_scheduled"
];

const STATUS_LABELS: Record<string, string> = {
  discovered: "Discovered",
  message_drafted: "Message Drafted",
  sent: "Sent",
  replied: "Replied",
  meeting_scheduled: "Meeting Scheduled",
};

function ContactCard({ contact }: { contact: Contact }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const update = useMutation({
    mutationFn: (data: Partial<Contact>) => contacts.update(contact.id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["contacts"] }),
  });

  const copyMessage = () => {
    if (contact.outreach_message) {
      navigator.clipboard.writeText(contact.outreach_message)
        .then(() => toast.success("Message copied to clipboard"));
    }
  };

  const score = contact.relevance_score ?? 0;
  const scorePct = Math.round(score * 100);
  const scoreColor = scorePct >= 80 ? "text-emerald-400 bg-emerald-400/10" : scorePct >= 60 ? "text-amber-400 bg-amber-400/10" : "text-zinc-400 bg-white/5";

  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${scoreColor}`}>
              {scorePct}% relevant
            </span>
            <span className="text-xs text-zinc-500">{contact.company}</span>
          </div>
          <h3 className="font-medium text-zinc-100">
            {[contact.first_name, contact.last_name].filter(Boolean).join(" ") || "Unknown"}
          </h3>
          <p className="text-sm text-zinc-400">{contact.title}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {contact.linkedin_url && (
            <a
              href={contact.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-zinc-500">Status:</label>
        <select
          value={contact.outreach_status}
          onChange={(e) => update.mutate({ outreach_status: e.target.value })}
          className="text-xs bg-white/5 border border-white/8 rounded-lg px-2 py-1 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-white/20"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {/* Message */}
      {contact.outreach_message && (
        <div>
          <button
            onClick={() => setExpanded((x) => !x)}
            className="text-xs font-medium text-zinc-400 hover:text-zinc-200 mb-2 transition-colors"
          >
            {expanded ? "Hide" : "Show"} outreach message
          </button>
          {expanded && (
            <div className="relative">
              <div className="rounded-lg border border-white/8 bg-white/3 px-4 py-3 text-sm text-zinc-300 leading-relaxed">
                {contact.outreach_message}
              </div>
              <button
                onClick={copyMessage}
                className="mt-2 flex items-center gap-1.5 text-xs font-medium text-white bg-white/8 hover:bg-white/12 rounded-lg px-3 py-1.5 transition-colors"
              >
                <Copy className="h-3.5 w-3.5" /> Copy message
              </button>
            </div>
          )}
        </div>
      )}

      {/* Reasoning */}
      {contact.relevance_reasoning && (
        <p className="text-xs text-zinc-500 leading-relaxed">{contact.relevance_reasoning}</p>
      )}
    </div>
  );
}

export default function NetworkingPage() {
  const { data = [], isLoading } = useQuery<Contact[]>({
    queryKey: ["contacts"],
    queryFn: () => contacts.list(),
  });

  // Group by company
  const byCompany = data.reduce<Record<string, Contact[]>>((acc, c) => {
    if (!acc[c.company]) acc[c.company] = [];
    acc[c.company].push(c);
    return acc;
  }, {});

  if (isLoading) return <div className="animate-pulse text-zinc-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Networking</h1>
        <p className="text-sm text-zinc-400 mt-1">{data.length} contact{data.length !== 1 ? "s" : ""} · Copy the message and send on LinkedIn</p>
      </div>

      {data.length === 0 ? (
        <div className="rounded-xl border border-white/8 bg-white/3 p-12 text-center grid-bg">
          <Users className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400 text-sm">No contacts yet.</p>
          <p className="text-zinc-500 text-xs mt-1">Add target companies in Settings and run the Networking Agent.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(byCompany).map(([company, companyContacts]) => (
            <div key={company}>
              <h2 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
                {company}
                <span className="text-xs text-zinc-500 font-normal">{companyContacts.length} contact{companyContacts.length > 1 ? "s" : ""}</span>
              </h2>
              <div className="space-y-3">
                {companyContacts.map((c) => <ContactCard key={c.id} contact={c} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
