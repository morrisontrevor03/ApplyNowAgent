"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { stripe } from "@/lib/api";
import { Check, Zap } from "lucide-react";

const FREE_FEATURES = [
  "5 job suggestions / month",
  "3 networking contacts / month",
  "Tailored resume + cover letter drafts",
  "Email alerts for high-match jobs",
];

const PRO_FEATURES = [
  "Unlimited job suggestions",
  "Unlimited networking contacts",
  "Unlimited application drafts",
  "Email alerts for high-match jobs",
  "Priority agent processing",
];

export default function PricingPage() {
  const [loading, setLoading] = useState(false);

  const handleUpgrade = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      window.location.href = "/register";
      return;
    }
    setLoading(true);
    try {
      const { url } = await stripe.createCheckout();
      window.location.href = url;
    } catch {
      toast.error("Failed to start checkout");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#08080f] text-[#ededff]">
      {/* Nav */}
      <header className="border-b border-violet-500/10 sticky top-0 z-40 bg-[#08080f]/80 backdrop-blur">
        <div className="mx-auto max-w-5xl px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/20 border border-violet-500/20">
              <Zap className="h-4 w-4 text-violet-400" />
            </div>
            <span className="text-sm font-semibold">ApplyNow</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-slate-400 hover:text-[#ededff] transition-colors">Sign in</Link>
            <Link href="/register" className="rounded-lg bg-violet-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-violet-500 transition-colors">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-24">
        <div className="text-center mb-14">
          <h1 className="text-3xl font-bold mb-3 gradient-text">Simple, honest pricing</h1>
          <p className="text-slate-400">Start free. Upgrade when the agents prove their worth.</p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          {/* Free */}
          <div className="rounded-2xl border border-violet-500/12 bg-violet-500/3 p-7 flex flex-col">
            <div className="mb-6">
              <p className="text-sm font-medium text-slate-400 mb-1">Free</p>
              <p className="text-3xl font-bold">$0</p>
              <p className="text-xs text-slate-500 mt-1">Forever</p>
            </div>
            <ul className="space-y-2.5 flex-1 mb-8">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300">
                  <Check className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className="block text-center rounded-xl border border-violet-500/20 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:bg-violet-500/8 transition-colors"
            >
              Get started free
            </Link>
          </div>

          {/* Pro */}
          <div className="rounded-2xl border border-violet-500/40 bg-violet-500/8 p-7 flex flex-col relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(124,58,237,0.2),transparent)] pointer-events-none" />
            <div className="absolute top-4 right-4">
              <span className="text-xs font-semibold bg-violet-600 text-white px-2.5 py-1 rounded-full">Popular</span>
            </div>
            <div className="relative mb-6">
              <p className="text-sm font-medium text-violet-300 mb-1">Pro</p>
              <div className="flex items-baseline gap-1">
                <p className="text-3xl font-bold">$19</p>
                <p className="text-sm text-slate-400">/ month</p>
              </div>
              <p className="text-xs text-slate-500 mt-1">Cancel anytime</p>
            </div>
            <ul className="relative space-y-2.5 flex-1 mb-8">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-[#ededff]">
                  <Check className="h-4 w-4 text-violet-400 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="relative rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50 transition-colors shadow-lg shadow-violet-500/20"
            >
              {loading ? "Redirecting…" : "Upgrade to Pro →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
