"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Zap } from "lucide-react";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { access_token } = await auth.register(email, password, fullName || undefined);
      await login(access_token);
      router.replace("/onboarding");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#08080f] grid-bg relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_0%,rgba(124,58,237,0.18),transparent)] pointer-events-none" />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-500/25 bg-violet-500/15">
            <Zap className="h-5 w-5 text-violet-400" />
          </div>
          <h1 className="text-xl font-semibold">Create your account</h1>
          <p className="text-sm text-slate-400">Start your AI job search in minutes</p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-xl border border-violet-500/15 bg-[#0d0d1a] p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Full name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-2 text-sm text-[#ededff] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              placeholder="Alex Chen"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-2 text-sm text-[#ededff] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              placeholder="you@example.com"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-lg border border-violet-500/15 bg-violet-500/5 px-3 py-2 text-sm text-[#ededff] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              placeholder="Min. 8 characters"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50 transition-colors shadow-lg shadow-violet-500/20"
          >
            {loading ? "Creating account…" : "Get started"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="text-violet-400 hover:text-violet-300 transition-colors">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
