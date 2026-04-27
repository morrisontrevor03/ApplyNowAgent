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
    <div className="min-h-screen bg-[#08080f] text-[#ededff]">
      {/* Nav */}
      <header className="border-b border-violet-500/10 backdrop-blur sticky top-0 z-40 bg-[#08080f]/80">
        <div className="mx-auto max-w-5xl px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/20 border border-violet-500/20">
              <Zap className="h-4 w-4 text-violet-400" />
            </div>
            <span className="text-sm font-semibold">ApplyNow</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-slate-400 hover:text-[#ededff] transition-colors">
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-violet-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-violet-500 transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden hero-glow">
        <div className="absolute inset-0 grid-bg grid-bg-fade pointer-events-none" />
        <div className="relative mx-auto max-w-3xl px-6 py-28 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/20 bg-violet-500/8 px-4 py-1.5 text-xs font-medium text-violet-300 mb-8">
            <Zap className="h-3 w-3 text-violet-400" />
            AI agents working for you 24/7
          </div>
          <h1 className="gradient-text text-4xl sm:text-5xl font-bold tracking-tight leading-tight mb-5">
            The job search agent that never sleeps
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed mb-10 max-w-xl mx-auto">
            ApplyNow runs AI agents around the clock to find jobs, build your network,
            and draft tailored applications — so you respond before anyone else.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-violet-600 px-6 py-3 text-sm font-semibold text-white hover:bg-violet-500 transition-colors shadow-lg shadow-violet-500/20"
            >
              Start free
            </Link>
            <Link
              href="/pricing"
              className="rounded-xl border border-violet-500/20 px-6 py-3 text-sm font-medium text-slate-300 hover:bg-violet-500/8 transition-colors"
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
              className="rounded-2xl border border-violet-500/12 bg-violet-500/3 p-6 space-y-3 hover:border-violet-500/25 hover:bg-violet-500/5 transition-colors"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-500/20 bg-violet-500/10">
                <Icon className="h-5 w-5 text-violet-400" />
              </div>
              <h3 className="font-semibold text-[#ededff]">{title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-5xl px-6 pb-24">
        <div className="relative overflow-hidden rounded-2xl border border-violet-500/20 bg-violet-500/5 p-10 text-center grid-bg">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_60%_at_50%_100%,rgba(124,58,237,0.15),transparent)] pointer-events-none" />
          <h2 className="relative text-2xl font-bold mb-3 gradient-text">Ready to get ahead?</h2>
          <p className="relative text-slate-400 text-sm mb-6">Start free — no credit card required.</p>
          <Link
            href="/register"
            className="relative inline-flex rounded-xl bg-violet-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 transition-colors shadow-lg shadow-violet-500/20"
          >
            Create your account →
          </Link>
        </div>
      </section>

      <footer className="border-t border-violet-500/8 py-6 text-center text-xs text-slate-600">
        © {new Date().getFullYear()} ApplyNow · apply-now-ai.com
      </footer>
    </div>
  );
}
