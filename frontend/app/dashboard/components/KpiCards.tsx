"use client";
/**
 * Overview KPIs. Every figure comes from /api/dashboard-kpis; resolution-time
 * groups use the backend's single definition (services/metrics.py).
 */
import { useState } from "react";
import {
  AlarmClock, Bot, ChevronRight, CircleCheck, Clock, FileSearch, Gauge, Layers, Timer, TriangleAlert,
  Trophy, User, Users, Zap, type LucideIcon,
} from "lucide-react";
import DrillDownModal from "./DrillDownModal";

interface MttrStat { avg_hours: number | null; tickets: number }

interface DashboardKpis {
  total_tickets: number;
  record_type?: { type: string; label: string; confidence?: number; evidence?: string[]; mix?: Record<string, number> };
  automation_value: {
    total_tickets: number;
    already_automated: number; already_automated_pct: number;
    can_automate: number; can_automate_pct: number;
    manual_only: number; manual_only_pct: number;
    hours_saved_monthly: number; annual_savings_lakhs: number;
    savings_assumptions?: { effort_minutes_per_ticket: number; hourly_cost_inr: number; months_covered: number };
  };
  operational_efficiency: {
    avg_mttr_hours: number; mttr_automated_hours: number; mttr_manual_hours: number;
    mttr_by_status?: { overall: MttrStat; automated: MttrStat; human_handled: MttrStat; can_automate: MttrStat; manual_only: MttrStat };
    priority_distribution: { priority: string; count: number }[];
    high_priority_count: number; high_priority_pct: number;
    sla_breach_risk_count: number; sla_breach_risk_pct: number;
  };
  team_performance: {
    top_teams_by_volume: { team: string; count: number; avg_mttr: number }[];
    best_mttr_team: { team: string; mttr: number } | null;
    worst_mttr_team: { team: string; mttr: number } | null;
    most_automated_team: { team: string; pct: number } | null;
  };
  channel_analysis: {
    by_channel: { channel: string; count: number; automated: number; automation_pct: number }[];
  };
  ml_patterns: { solution_distribution: { solution: string; count: number; pct: number }[] };
}

const hours = (h: number | null | undefined) => (h == null ? "—" : h >= 100 ? `${Math.round(h)}h` : `${h.toFixed(1)}h`);

function Tile({ label, value, sub, icon: Icon, tone = "text-gray-400", onClick }: {
  label: string; value: string | number; sub?: React.ReactNode; icon: LucideIcon; tone?: string; onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="group text-left bg-white border border-gray-200 rounded-xl px-4 py-4 shadow-sm shadow-zinc-900/[0.03] enabled:hover:border-blue-300 enabled:hover:shadow-md enabled:hover:shadow-indigo-500/5 transition-colors disabled:cursor-default"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500">{label}</span>
        <Icon className={`w-4 h-4 ${tone}`} strokeWidth={1.75} />
      </div>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <span className="text-2xl font-semibold text-gray-900 tabular-nums tracking-tight">{value}</span>
        {onClick && <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-blue-500 mb-1" />}
      </div>
      {sub && <div className="mt-1 text-xs text-gray-500 leading-snug">{sub}</div>}
    </button>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-2.5">{title}</h2>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">{children}</div>
    </section>
  );
}

function Bar({ label, value, pct, note }: { label: string; value: string; pct: number; note?: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-700">{label}</span>
        <span className="text-gray-900 tabular-nums">{value}{note && <span className="text-gray-500 ml-2">{note}</span>}</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

export default function KpiCards({ data, onTabChange }: { data: DashboardKpis; onTabChange?: (tab: string) => void }) {
  const av = data.automation_value;
  const oe = data.operational_efficiency;
  const tp = data.team_performance;
  const m = oe.mttr_by_status;
  const rt = data.record_type;
  const a = av.savings_assumptions;

  const [modal, setModal] = useState<{ type: string; title: string; subtitle?: string } | null>(null);
  const open = (type: string, title: string, subtitle?: string) => setModal({ type, title, subtitle });

  return (
    <div className="space-y-5">
      <DrillDownModal
        isOpen={!!modal}
        onClose={() => setModal(null)}
        title={modal?.title ?? ""}
        subtitle={modal?.subtitle ?? ""}
        type={modal?.type ?? ""}
        data={data as any}
      />

      {rt && rt.type !== "unknown" && (
        <div className="flex items-start gap-2 text-xs text-gray-600 bg-white border border-gray-200 rounded-lg px-4 py-2.5">
          <FileSearch className="w-4 h-4 text-gray-400 mt-px shrink-0" />
          <span>
            <span className="font-medium text-gray-900">{rt.label} export</span>
            {rt.evidence?.length ? <> · detected from {rt.evidence.join("; ")}</> : null}
          </span>
        </div>
      )}

      <Group title="Automation">
        <Tile label="Already automated" value={av.already_automated.toLocaleString()} icon={Bot}
          sub={`${av.already_automated_pct}% of tickets`}
          onClick={() => open("teams_automation", "Automation by team")} />
        <Tile label="Can be automated" value={av.can_automate.toLocaleString()} icon={Zap} tone="text-blue-500"
          sub={`${av.can_automate_pct}% of tickets`}
          onClick={() => open("solutions", "Recommended solutions", "How these tickets can be automated")} />
        <Tile label="Manual only" value={av.manual_only.toLocaleString()} icon={User}
          sub={`${av.manual_only_pct}% need human judgement`} />
        <Tile label="Effort that could be saved" value={`${av.hours_saved_monthly.toLocaleString()} h/mo`} icon={AlarmClock}
          sub={a ? <>₹{av.annual_savings_lakhs}L per year · {a.effort_minutes_per_ticket} min/ticket at ₹{a.hourly_cost_inr}/h, {a.months_covered} months of data</> : `₹${av.annual_savings_lakhs}L per year`}
          onClick={() => open("hours_saved", "Savings by solution")} />
      </Group>

      <Group title="Operations">
        <Tile label="Tickets" value={av.total_tickets.toLocaleString()} icon={Layers}
          onClick={() => open("categories", "Ticket distribution", "By category")} />
        <Tile label="Average resolution time" value={hours(oe.avg_mttr_hours)} icon={Timer}
          sub={m ? <>Automated {hours(m.automated.avg_hours)} · human-handled {hours(m.human_handled.avg_hours)}</> : null}
          onClick={() => open("mttr_breakdown", "Resolution time", "By automation status")} />
        <Tile label="Human-handled resolution time" value={hours(m?.human_handled.avg_hours ?? oe.mttr_manual_hours)} icon={Clock}
          sub={m ? <>Can be automated {hours(m.can_automate.avg_hours)} · manual only {hours(m.manual_only.avg_hours)}</> : null}
          onClick={() => open("mttr_breakdown", "Resolution time", "By automation status")} />
        <Tile label="High priority (P1/P2)" value={(oe.high_priority_count ?? 0).toLocaleString()} icon={TriangleAlert} tone="text-amber-500"
          sub={`${oe.high_priority_pct ?? 0}% of tickets · ${oe.sla_breach_risk_pct}% breached SLA`}
          onClick={() => open("priority", "Priority distribution")} />
      </Group>

      <Group title="Teams">
        <Tile label="Highest volume" value={tp.top_teams_by_volume[0]?.team ?? "—"} icon={Users}
          sub={`${tp.top_teams_by_volume[0]?.count.toLocaleString() ?? 0} tickets`}
          onClick={() => open("teams_volume", "Teams by volume")} />
        <Tile label="Fastest resolution" value={tp.best_mttr_team?.team ?? "—"} icon={Trophy}
          sub={`${hours(tp.best_mttr_team?.mttr)} average`}
          onClick={() => open("teams_mttr", "Resolution time by team")} />
        <Tile label="Most automated" value={tp.most_automated_team?.team ?? "—"} icon={CircleCheck}
          sub={`${tp.most_automated_team?.pct ?? 0}% of its tickets`}
          onClick={() => open("teams_automation", "Automation rate by team")} />
        <Tile label="Slowest resolution" value={tp.worst_mttr_team?.team ?? "—"} icon={Gauge}
          sub={`${hours(tp.worst_mttr_team?.mttr)} average`}
          onClick={() => open("teams_mttr", "Resolution time by team")} />
      </Group>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm shadow-zinc-900/[0.03]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-900">Channels</h2>
            <button className="text-xs text-blue-700 hover:underline" onClick={() => open("channels", "Channel analysis")}>Details</button>
          </div>
          <div className="space-y-3">
            {data.channel_analysis.by_channel.slice(0, 5).map((c) => (
              <Bar key={c.channel} label={c.channel} value={c.count.toLocaleString()} pct={(c.count / av.total_tickets) * 100}
                note={`${c.automation_pct}% automated`} />
            ))}
          </div>
        </section>
        <section className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm shadow-zinc-900/[0.03]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-900">Solution mix</h2>
            <button className="text-xs text-blue-700 hover:underline" onClick={() => onTabChange?.("roi")}>ROI calculator</button>
          </div>
          <div className="space-y-3">
            {data.ml_patterns.solution_distribution.slice(0, 5).map((s) => (
              <Bar key={s.solution} label={s.solution} value={s.count.toLocaleString()} pct={s.pct} note={`${s.pct}%`} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
