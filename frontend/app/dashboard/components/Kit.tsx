"use client";
/** Small presentational pieces shared by the Model Health and Model Evaluation views. */
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export const card = "bg-white border border-zinc-200 rounded-2xl shadow-sm shadow-zinc-900/[0.03]";

type Tone = "green" | "amber" | "red" | "indigo" | "zinc";
const TONES: Record<Tone, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/15",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/15",
  zinc: "bg-zinc-100 text-zinc-600 ring-zinc-500/10",
};

export function Pill({ tone = "zinc", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function IconTile({ icon: Icon, tone = "indigo" }: { icon: LucideIcon; tone?: Tone }) {
  return (
    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset ${TONES[tone]}`}>
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
    </span>
  );
}

/** Section heading with an optional description, used above a card or inside one. */
export function Heading({ title, note, right }: { title: string; note?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold tracking-tight text-zinc-900">{title}</h3>
        {note && <p className="mt-1 text-[13px] leading-relaxed text-zinc-500">{note}</p>}
      </div>
      {right}
    </div>
  );
}

export function Panel({ title, note, right, children, className = "" }: {
  title?: string; note?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`${card} p-6 ${className}`}>
      {title && <Heading title={title} note={note} right={right} />}
      <div className={title ? "mt-5" : ""}>{children}</div>
    </section>
  );
}

/** Big number with a label; the value is the thing to read first. */
export function Metric({ label, value, sub, accent = false }: { label: string; value: ReactNode; sub?: ReactNode; accent?: boolean }) {
  return (
    <div className={`${card} p-5 ${accent ? "bg-gradient-to-br from-indigo-50 via-white to-white border-indigo-100" : ""}`}>
      <div className="text-xs font-medium text-zinc-500">{label}</div>
      <div className="mt-2 text-[28px] font-semibold leading-none tracking-tight text-zinc-900 tabular-nums">{value}</div>
      {sub && <div className="mt-2 text-xs leading-snug text-zinc-500">{sub}</div>}
    </div>
  );
}

/** Horizontal meter: value as a share (0-100) of the track. */
export function Meter({ pct, tone = "indigo" }: { pct: number; tone?: "indigo" | "green" | "amber" | "zinc" }) {
  const fill = { indigo: "bg-indigo-500", green: "bg-emerald-500", amber: "bg-amber-500", zinc: "bg-zinc-400" }[tone];
  return (
    <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
      <div className={`h-full rounded-full ${fill}`} style={{ width: `${Math.max(0, Math.min(pct, 100))}%` }} />
    </div>
  );
}

/** Circular gauge for a 0-1 score. */
export function Ring({ value, size = 56 }: { value: number | null | undefined; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const v = value == null ? 0 : Math.max(0, Math.min(value, 1));
  return (
    <svg width={size} height={size} className="-rotate-90 shrink-0" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f4f4f5" strokeWidth={6} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#6366f1" strokeWidth={6} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - v)} />
    </svg>
  );
}

/** Table with a quiet header. `highlightLast` marks the model row under test against its baselines. */
export function DataTable({ head, rows, highlightLast = false }: { head: string[]; rows: ReactNode[][]; highlightLast?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-zinc-50/80 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
            {head.map((h, i) => <th key={i} className={`px-4 py-2.5 ${i > 0 ? "text-right" : ""}`}>{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {rows.map((r, i) => (
            <tr key={i} className={highlightLast && i === rows.length - 1 ? "bg-indigo-50/50 font-medium" : "hover:bg-zinc-50/60"}>
              {r.map((c, j) => (
                <td key={j} className={`px-4 py-2.5 ${j === 0 ? "text-zinc-900" : "text-right tabular-nums text-zinc-700"}`}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
