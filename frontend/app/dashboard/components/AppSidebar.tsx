"use client";
/**
 * Single navigation for the whole application.
 * Views are grouped by purpose; the active view lives in the URL (?view=).
 */
import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import {
  BadgeCheck, Calculator, ClipboardCheck, ChevronDown, Database, Gauge, History, Layers, LayoutDashboard,
  MessageSquare, Network, Settings, ShieldAlert, Table2, TrendingUp, Upload, Workflow,
  type LucideIcon,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type View =
  | "overview" | "tickets" | "automation" | "clusters" | "sla" | "anomalies" | "roi"
  | "copilot" | "review" | "evaluation" | "health" | "architecture" | "activity" | "settings";

interface NavItem { view: View; label: string; icon: LucideIcon }

export const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Analysis", items: [
    { view: "overview", label: "Overview", icon: LayoutDashboard },
    { view: "tickets", label: "Tickets", icon: Table2 },
    { view: "automation", label: "Automation Opportunities", icon: Workflow },
    { view: "clusters", label: "Ticket Themes", icon: Network },
    { view: "sla", label: "SLA & Forecast", icon: TrendingUp },
    { view: "anomalies", label: "Anomalies", icon: ShieldAlert },
    { view: "roi", label: "ROI Calculator", icon: Calculator },
  ]},
  { section: "Intelligence", items: [
    { view: "copilot", label: "Copilot", icon: MessageSquare },
    { view: "review", label: "Review Queue", icon: ClipboardCheck },
    { view: "evaluation", label: "Model Evaluation", icon: BadgeCheck },
    { view: "health", label: "Model Health", icon: Gauge },
  ]},
  { section: "Platform", items: [
    { view: "architecture", label: "Architecture", icon: Layers },
  ]},
  { section: "Administration", items: [
    { view: "activity", label: "Activity Log", icon: History },
    { view: "settings", label: "Settings", icon: Settings },
  ]},
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

interface Upload { id: number; filename: string; total_tickets: number; status: string; created_at: string }
interface Health { status: "healthy" | "degraded" | "unhealthy"; checks: Record<string, string> }

interface Props {
  view: View;
  onViewChange: (view: View) => void;
  uploads: Upload[];
  selectedUploadId?: number;
  onDatasetChange: (uploadId: number) => void;
  user?: { username: string; team_id: string; role?: string } | null;
}

export default function AppSidebar({ view, onViewChange, uploads, selectedUploadId, onDatasetChange, user }: Props) {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const selected = uploads.find((u) => u.id === selectedUploadId);

  useEffect(() => {
    fetch(`${API}/health`).then((r) => r.json()).then(setHealth).catch(() => setHealth(null));
  }, []);

  const statusTone = !health ? "bg-red-500" : health.status === "healthy" ? "bg-emerald-500" : health.status === "degraded" ? "bg-amber-500" : "bg-red-500";
  const statusText = !health
    ? "Backend unreachable"
    : health.status === "healthy"
    ? "All services healthy"
    : Object.entries(health.checks).filter(([, v]) => v !== "ok").map(([k, v]) => `${k.replace("_", " ")}: ${v}`).join(" · ");

  return (
    <aside className="w-64 shrink-0 h-screen flex flex-col bg-white text-zinc-600 border-r border-zinc-200">
      <div className="px-5 h-16 flex items-center border-b border-zinc-100">
        <Logo tagline="Ticket analytics" />
      </div>

      {/* Dataset */}
      <div className="px-3 pt-4 relative">
        <button
          onClick={() => setOpen(!open)}
          className="w-full text-left rounded-xl border border-zinc-200 bg-zinc-50/70 px-3 py-2.5 transition hover:border-zinc-300 hover:bg-zinc-50"
        >
          <div className="flex items-center justify-between text-[11px] font-medium text-zinc-500">
            <span className="flex items-center gap-1.5"><Database className="w-3 h-3" /> Dataset</span>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </div>
          <div className="text-[13px] font-medium text-zinc-900 truncate mt-1">{selected?.filename ?? "No dataset"}</div>
          {selected && (
            <div className="text-[11px] text-zinc-500 mt-0.5">
              {selected.total_tickets?.toLocaleString()} tickets · {new Date(selected.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
            </div>
          )}
        </button>
        {open && (
          <div className="absolute left-3 right-3 mt-1.5 z-50 max-h-72 overflow-y-auto rounded-xl border border-zinc-200 bg-white shadow-lg shadow-zinc-900/5">
            {uploads.map((u) => (
              <button
                key={u.id}
                onClick={() => { setOpen(false); onDatasetChange(u.id); }}
                className={`w-full text-left px-3 py-2.5 border-b border-zinc-100 last:border-0 hover:bg-zinc-50 ${u.id === selectedUploadId ? "bg-indigo-50/70" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[12px] font-medium truncate ${u.id === selectedUploadId ? "text-indigo-700" : "text-zinc-800"}`}>{u.filename}</span>
                  <span className={`text-[10px] font-medium uppercase tracking-wide ${u.status === "completed" ? "text-emerald-600" : u.status === "failed" ? "text-red-600" : "text-amber-600"}`}>
                    {u.status}
                  </span>
                </div>
                <div className="text-[11px] text-zinc-500">#{u.id} · {u.total_tickets?.toLocaleString() ?? 0} tickets</div>
              </button>
            ))}
            <a href="/upload" className="flex items-center gap-2 px-3 py-2.5 text-[12px] font-medium text-indigo-600 hover:bg-zinc-50">
              <Upload className="w-3.5 h-3.5" /> Upload new dataset
            </a>
          </div>
        )}
      </div>

      <div className="px-3 pt-2.5">
        <a
          href="/upload"
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-white text-[13px] font-medium py-2.5 shadow-sm transition"
        >
          <Upload className="w-4 h-4" /> Upload dataset
        </a>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{group.section}</div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = view === item.view;
                return (
                  <button
                    key={item.view}
                    onClick={() => onViewChange(item.view)}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition ${
                      active ? "bg-indigo-50 text-indigo-700 font-medium" : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100/80"
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${active ? "text-indigo-600" : "text-zinc-400"}`} strokeWidth={1.75} />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-zinc-100 px-4 py-3 space-y-2.5">
        <div className="flex items-center gap-2 text-[11px] text-zinc-500" title={health ? JSON.stringify(health.checks) : ""}>
          <span className={`w-1.5 h-1.5 rounded-full ${statusTone}`} />
          <span className="truncate">{statusText}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[12px] font-semibold uppercase text-indigo-700">
              {(user?.username ?? "?").charAt(0)}
            </div>
            <div className="min-w-0">
              <div className="text-[12px] font-medium text-zinc-900 truncate">{user?.username ?? "—"}</div>
              <div className="text-[11px] text-zinc-500 truncate">{user ? `${user.team_id}${user.role ? " · " + user.role : ""}` : ""}</div>
            </div>
          </div>
          <button
            onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }}
            className="text-[11px] font-medium text-zinc-500 hover:text-zinc-900"
          >
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
