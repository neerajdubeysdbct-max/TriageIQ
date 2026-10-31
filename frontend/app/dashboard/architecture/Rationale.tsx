"use client";
/**
 * Design rationale as slides: one decision per slide with the problem, the options
 * compared (bars where a measured number exists), how the chosen approach works,
 * and the decision, evidence and trade-off. Arrow keys move between slides; at the
 * first or last slide they fall through to section navigation.
 */
import { useEffect, useState } from "react";
import { ArrowRight, Check, ChevronLeft, ChevronRight, LayoutGrid } from "lucide-react";
import { WHYS, WHY_TOPICS, type Why } from "./whys";

const TOPIC_TONE: Record<string, string> = {
  "Problem and data": "#d97706", "Models": "#7c3aed", "Evaluation": "#0d9488",
  "Learning loop": "#dc2626", "Copilot (RAG)": "#059669", "Platform": "#2563eb",
};

export default function Rationale({ start = 0 }: { start?: number }) {
  const [index, setIndex] = useState(start);
  const [grid, setGrid] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (grid || tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" && index < WHYS.length - 1) { setIndex(index + 1); e.stopImmediatePropagation(); e.preventDefault(); }
      if (e.key === "ArrowLeft" && index > 0) { setIndex(index - 1); e.stopImmediatePropagation(); e.preventDefault(); }
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [index, grid]);

  const why = WHYS[index];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => setGrid(!grid)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border ${grid ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200"}`}>
          <LayoutGrid className="w-3.5 h-3.5" />All {WHYS.length}
        </button>
        {WHY_TOPICS.map((t) => {
          const first = WHYS.findIndex((w) => w.topic === t);
          const active = !grid && why.topic === t;
          return (
            <button key={t} onClick={() => { setIndex(first); setGrid(false); }}
              className={`px-2.5 py-1.5 rounded-md text-xs border ${active ? "text-white" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}
              style={active ? { background: TOPIC_TONE[t], borderColor: TOPIC_TONE[t] } : undefined}>
              {t}
            </button>
          );
        })}
        {!grid && (
          <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
            <span className="tabular-nums mr-1">{index + 1} / {WHYS.length}</span>
            <button onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0} className="p-1.5 rounded border border-gray-200 bg-white disabled:opacity-40"><ChevronLeft className="w-3.5 h-3.5" /></button>
            <button onClick={() => setIndex(Math.min(WHYS.length - 1, index + 1))} disabled={index === WHYS.length - 1} className="p-1.5 rounded border border-gray-200 bg-white disabled:opacity-40"><ChevronRight className="w-3.5 h-3.5" /></button>
          </div>
        )}
      </div>

      {grid ? <Index onOpen={(i) => { setIndex(i); setGrid(false); }} /> : <Slide key={index} why={why} n={index + 1} />}
    </div>
  );
}

function Index({ onOpen }: { onOpen: (i: number) => void }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {WHY_TOPICS.map((t) => (
        <section key={t} className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: TOPIC_TONE[t] }}>{t}</h3>
          <ol className="space-y-1">
            {WHYS.map((w, i) => w.topic !== t ? null : (
              <li key={i}>
                <button onClick={() => onOpen(i)} className="w-full text-left flex gap-2 text-sm text-gray-800 hover:text-blue-700">
                  <span className="w-5 text-right tabular-nums text-gray-400">{i + 1}</span>{w.q}
                </button>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function Slide({ why, n }: { why: Why; n: number }) {
  const tone = TOPIC_TONE[why.topic];
  return (
    <article className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="h-1" style={{ background: tone }} />
      <div className="p-6 space-y-5">
        <header>
          <div className="text-xs font-medium" style={{ color: tone }}>{why.topic} · Decision {n}</div>
          <h3 className="text-2xl font-semibold text-gray-900 mt-1">{why.q}</h3>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-5">
          <Panel label="The problem" accent="#94a3b8">
            <p className="text-[15px] text-gray-800 leading-relaxed">{why.problem}</p>
          </Panel>
          <Panel label={why.metric ? `Options compared · ${why.metric.label}${why.metric.better === "lower" ? " (lower is better)" : ""}` : "Options considered"} accent={tone}>
            <Options why={why} tone={tone} />
          </Panel>
        </div>

        {why.flow && <Flow steps={why.flow} tone={tone} />}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Box title="Decision" color="#1d4ed8" bg="#eff6ff">{why.decision}</Box>
          <Box title="Evidence" color="#047857" bg="#ecfdf5">
            <ul className="space-y-1.5">
              {why.evidence.map((e, i) => <li key={i} className="flex gap-2"><Check className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />{e}</li>)}
            </ul>
          </Box>
          <Box title="Trade-off" color="#92400e" bg="#fffbeb">
            <p>{why.tradeoff}</p>
            <p className="mt-2 text-gray-600"><span className="font-medium text-gray-700">We would change it if: </span>{why.revisit}</p>
          </Box>
        </div>
      </div>
    </article>
  );
}

function Panel({ label, accent, children }: { label: string; accent: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 p-4" style={{ borderLeft: `3px solid ${accent}` }}>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-2">{label}</div>
      {children}
    </section>
  );
}

function Options({ why, tone }: { why: Why; tone: string }) {
  const max = why.metric?.max ?? Math.max(...why.options.map((o) => o.value ?? 0), 1);
  return (
    <div className="space-y-2.5">
      {why.options.map((o, i) => (
        <div key={i}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className={`flex items-center gap-1.5 ${o.chosen ? "font-semibold text-gray-900" : "text-gray-700"}`}>
              {o.chosen && <Check className="w-4 h-4" style={{ color: tone }} />}{o.name}
            </span>
            {o.display && <span className={`tabular-nums whitespace-nowrap ${o.chosen ? "font-semibold text-gray-900" : "text-gray-500"}`}>{o.display}</span>}
          </div>
          {o.value !== undefined && (
            <div className="h-2 mt-1 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-2 rounded-full transition-[width] duration-700 ease-out"
                style={{ width: `${Math.max(1.5, Math.min(100, (o.value / max) * 100))}%`, background: o.chosen ? tone : "#cbd5e1" }} />
            </div>
          )}
          {o.note && <div className="text-xs text-gray-500 mt-0.5">{o.note}</div>}
        </div>
      ))}
    </div>
  );
}

/** The chosen approach as a sequence; the highlight walks along the steps. */
function Flow({ steps, tone }: { steps: string[]; tone: string }) {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setActive((a) => (a + 1) % steps.length), 1300);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <section>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-2">How it works</div>
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="px-3 py-2 rounded-lg text-sm border transition-colors duration-300"
              style={i === active ? { background: tone, color: "white", borderColor: tone } : { background: "white", color: "#374151", borderColor: "#e5e7eb" }}>
              {s}
            </span>
            {i < steps.length - 1 && <ArrowRight className="w-4 h-4 text-gray-300" />}
          </div>
        ))}
      </div>
    </section>
  );
}

function Box({ title, color, bg, children }: { title: string; color: string; bg: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg p-4 text-sm text-gray-800 leading-relaxed" style={{ background: bg }}>
      <div className="text-[11px] font-semibold uppercase tracking-wide mb-1.5" style={{ color }}>{title}</div>
      {children}
    </section>
  );
}
