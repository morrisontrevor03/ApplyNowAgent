import Link from "next/link";
import { Zap, BriefcaseBusiness, Users, FileCheck } from "lucide-react";

const features = [
  {
    icon: BriefcaseBusiness,
    title: "Job Scout — 24/7",
    description:
      "AI agents scan thousands of job boards every 30 minutes and email you the moment a high-match posting appears — before most people even see it.",
  },
  {
    icon: Users,
    title: "Strategic Networking",
    description:
      "Automatically finds the right people at your target companies — hiring managers, staff engineers, recruiters — and drafts a personalized coffee chat message for each one.",
  },
  {
    icon: FileCheck,
    title: "Instant Application Drafts",
    description:
      "For every strong match, Claude tailors your resume bullets and writes a cover letter. You get a draft in your inbox within minutes of the job posting going live.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen text-zinc-50">
      {/* Nav */}
      <header className="border-b border-white/[0.06] backdrop-blur-xl backdrop-saturate-150 sticky top-0 z-40 bg-zinc-950/60">
        <div className="mx-auto max-w-5xl px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-sm font-semibold">ApplyNow</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors">
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-white px-4 py-1.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-bg grid-bg-fade pointer-events-none" />
        <div className="relative mx-auto max-w-3xl px-6 py-28 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-zinc-300 mb-8">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
            </span>
            AI agents working for you 24/7
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight mb-5">
            The job search agent that never sleeps
          </h1>
          <p className="text-lg text-zinc-400 leading-relaxed mb-10 max-w-xl mx-auto">
            ApplyNow runs AI agents around the clock to find jobs, build your network,
            and draft tailored applications — so you respond before anyone else.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-white px-6 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition-colors shadow-lg shadow-white/10"
            >
              Start free
            </Link>
            <Link
              href="/pricing"
              className="rounded-xl border border-white/10 px-6 py-3 text-sm font-medium text-zinc-300 hover:bg-white/5 transition-colors"
            >
              View pricing
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="grid gap-5 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="rounded-2xl border border-white/8 bg-white/3 p-6 space-y-3 hover:border-white/12 transition-colors"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5">
                <Icon className="h-5 w-5 text-zinc-300" />
              </div>
              <h3 className="font-semibold text-zinc-100">{title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-5xl px-6 pb-24">
        <div className="relative overflow-hidden rounded-2xl border border-white/8 bg-white/3 p-10 text-center grid-bg">
          <h2 className="text-2xl font-bold mb-3">Ready to get ahead?</h2>
          <p className="text-zinc-400 text-sm mb-6">Start free — no credit card required.</p>
          <Link
            href="/register"
            className="inline-flex rounded-xl bg-white px-6 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition-colors"
          >
            Create your account →
          </Link>
        </div>
      </section>

      <footer className="border-t border-white/6 py-6 text-center text-xs text-zinc-600">
        © {new Date().getFullYear()} ApplyNow · apply-now-ai.com
      </footer>
    </div>
  );
}
