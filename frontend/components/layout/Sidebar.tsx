"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Briefcase, FileText, Users, Upload, Settings, LogOut, Zap
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/applications", label: "Applications", icon: FileText },
  { href: "/networking", label: "Networking", icon: Users },
  { href: "/resume", label: "Resume", icon: Upload },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-full w-56 flex-col border-r border-violet-500/10 bg-[#09091a]">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-violet-500/10">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/20 border border-violet-500/20">
          <Zap className="h-4 w-4 text-violet-400" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-[#ededff]">ApplyNow</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              pathname.startsWith(href)
                ? "bg-violet-500/15 text-violet-200 border border-violet-500/20"
                : "text-slate-400 hover:bg-violet-500/8 hover:text-slate-200 border border-transparent"
            )}
          >
            <Icon className={cn("h-4 w-4 shrink-0", pathname.startsWith(href) ? "text-violet-400" : "")} />
            {label}
          </Link>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-violet-500/10 px-3 py-3">
        <div className="mb-1 px-2 py-1">
          <p className="text-xs text-slate-500 truncate">{user?.email}</p>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-violet-500/8 hover:text-slate-200 transition-colors border border-transparent"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
