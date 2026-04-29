"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { stripe } from "@/lib/api";
import { Check, Zap } from "lucide-react";

const FREE_FEATURES = [
  "3 Job Scout runs / month",
  "3 Networking runs / month",
  "3 Application Draft runs / month",
  "Email alerts for high-match jobs",
];

const PRO_FEATURES = [
  "Unlimited Job Scout runs",
  "Unlimited Networking runs",
  "Unlimited Application Draft runs",
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
    <div className="min-h-screen text-zinc-50">
      {/* Nav */}
      <header className="border-b border-white/[0.06] backdrop-blur-xl backdrop-saturate-150 sticky top-0 z-40 bg-zinc-950/60">
        <div className="mx-auto max-w-5xl px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-sm font-semibold">ApplyNow</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors">Sign in</Link>
            <Link href="/register" className="rounded-lg bg-white px-4 py-1.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition-colors">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-24">
        <div className="text-center mb-14">
          <h1 className="text-3xl font-bold mb-3">Simple, honest pricing</h1>
          <p className="text-zinc-400">Start free. Upgrade when the agents prove their worth.</p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          {/* Free */}
          <div className="rounded-2xl border border-white/8 bg-white/3 p-7 flex flex-col">
            <div className="mb-6">
              <p className="text-sm font-medium text-zinc-400 mb-1">Free</p>
              <p className="text-3xl font-bold">$0</p>
              <p className="text-xs text-zinc-500 mt-1">Forever</p>
            </div>
            <ul className="space-y-2.5 flex-1 mb-8">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-zinc-300">
                  <Check className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className="block text-center rounded-xl border border-white/10 px-5 py-2.5 text-sm font-semibold text-zinc-200 hover:bg-white/5 transition-colors"
            >
              Get started free
            </Link>
          </div>

          {/* Pro */}
          <div className="rounded-2xl border border-white/20 bg-white/5 p-7 flex flex-col relative overflow-hidden">
            <div className="absolute top-4 right-4">
              <span className="text-xs font-semibold bg-white text-zinc-900 px-2.5 py-1 rounded-full">Popular</span>
            </div>
            <div className="mb-6">
              <p className="text-sm font-medium text-zinc-300 mb-1">Pro</p>
              <div className="flex items-baseline gap-1">
                <p className="text-3xl font-bold">$34.99</p>
                <p className="text-sm text-zinc-400">/ month</p>
              </div>
              <p className="text-xs text-zinc-500 mt-1">Cancel anytime</p>
            </div>
            <ul className="space-y-2.5 flex-1 mb-8">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-zinc-200">
                  <Check className="h-4 w-4 text-white shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              {loading ? "Redirecting…" : "Upgrade to Pro →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
