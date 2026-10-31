"use client";
/**
 * Animated architecture diagram in plain SVG. Dots travel along every connection;
 * selecting a box shows what it is, the technology and why it was chosen. With
 * `steps`, a player walks through the flow one stage at a time for presenting.
 */
import { useEffect, useMemo, useState } from "react";
import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";

export type Tone = "user" | "process" | "store" | "model" | "llm" | "external" | "output" | "control";

export interface DNode {
  id: string;
  x: number; y: number; w?: number; h?: number;
  title: string;
  sub?: string;
  tone: Tone;
  what: string;
  tech?: string;
  why?: string;
  numbers?: string;
}
type Side = "top" | "bottom" | "left" | "right";
/** `via` routes the connection through fixed points (right angles), for busy diagrams. */
export interface DEdge {
  from: string; to: string; label?: string; dashed?: boolean; bend?: number;
  via?: [number, number][]; fromSide?: Side; toSide?: Side;
  /** move the end points along their side, to run two connections side by side */
  fromShift?: number; toShift?: number;
}
export interface DGroup { x: number; y: number; w: number; h: number; label: string }

const TONES: Record<Tone, { fill: string; stroke: string; text: string; tag: string }> = {
  user:     { fill: "#f8fafc", stroke: "#64748b", text: "#0f172a", tag: "Actor" },
  process:  { fill: "#eff6ff", stroke: "#2563eb", text: "#1e3a8a", tag: "Process" },
  store:    { fill: "#fffbeb", stroke: "#d97706", text: "#78350f", tag: "Data store" },
  model:    { fill: "#f5f3ff", stroke: "#7c3aed", text: "#4c1d95", tag: "Model" },
  llm:      { fill: "#ecfdf5", stroke: "#059669", text: "#064e3b", tag: "Local LLM" },
  external: { fill: "#f9fafb", stroke: "#9ca3af", text: "#374151", tag: "External" },
  output:   { fill: "#f0fdfa", stroke: "#0d9488", text: "#134e4a", tag: "Output" },
  control:  { fill: "#fef2f2", stroke: "#dc2626", text: "#7f1d1d", tag: "Control" },
};

const W = 150, H = 54;

function box(n: DNode) {
  const w = n.w ?? W, h = n.h ?? H;
  return { x: n.x, y: n.y, w, h, cx: n.x + w / 2, cy: n.y + h / 2 };
}

function anchor(n: DNode, side: Side, shift = 0): [number, number] {
  const b = box(n);
  return side === "top" ? [b.cx + shift, b.y] : side === "bottom" ? [b.cx + shift, b.y + b.h]
    : side === "left" ? [b.x, b.cy + shift] : [b.x + b.w, b.cy + shift];
}

function routedPath(a: DNode, b: DNode, e: DEdge) {
  const pts = [anchor(a, e.fromSide ?? "right", e.fromShift), ...(e.via ?? []), anchor(b, e.toSide ?? "left", e.toShift)];
  const mid = Math.floor((pts.length - 1) / 2);
  const [p, q] = [pts[mid], pts[mid + 1]];
  return { d: "M" + pts.map(([x, y]) => `${x},${y}`).join(" L"), mx: (p[0] + q[0]) / 2, my: (p[1] + q[1]) / 2 };
}

/** Connection from the side of `a` facing `b` to the side of `b` facing `a`, as a cubic curve. */
function edgePath(a: DNode, b: DNode, bend = 0) {
  const A = box(a), B = box(b);
  const dx = B.cx - A.cx, dy = B.cy - A.cy;
  let x1, y1, x2, y2, c1x, c1y, c2x, c2y;
  if (Math.abs(dx) >= Math.abs(dy) * 1.2) {
    x1 = dx > 0 ? A.x + A.w : A.x; y1 = A.cy;
    x2 = dx > 0 ? B.x : B.x + B.w; y2 = B.cy;
    const k = Math.max(30, Math.abs(x2 - x1) / 2);
    c1x = x1 + (dx > 0 ? k : -k); c1y = y1 + bend; c2x = x2 - (dx > 0 ? k : -k); c2y = y2 + bend;
  } else {
    x1 = A.cx; y1 = dy > 0 ? A.y + A.h : A.y;
    x2 = B.cx; y2 = dy > 0 ? B.y : B.y + B.h;
    const k = Math.max(24, Math.abs(y2 - y1) / 2);
    c1x = x1 + bend; c1y = y1 + (dy > 0 ? k : -k); c2x = x2 + bend; c2y = y2 - (dy > 0 ? k : -k);
  }
  return { d: `M${x1},${y1} C${c1x},${c1y} ${c2x},${c2y} ${x2},${y2}`, mx: (x1 + x2) / 2 + bend * 0.75, my: (y1 + y2) / 2 + bend * 0.75 };
}

export default function Diagram({ nodes, edges, groups = [], width, height, steps, caption }: {
  nodes: DNode[]; edges: DEdge[]; groups?: DGroup[]; width: number; height: number;
  steps?: string[]; caption?: string;
}) {
  const byId = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const [selected, setSelected] = useState<string>(steps?.[0] ?? nodes[0]?.id);
  const [step, setStep] = useState<number>(-1);       // -1: free view, all flows animate
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing || !steps) return;
    const t = setInterval(() => {
      setStep((s) => {
        const next = s + 1;
        if (next >= steps.length) { setPlaying(false); return s; }
        setSelected(steps[next]);
        return next;
      });
    }, 2200);
    return () => clearInterval(t);
  }, [playing, steps]);

  const activeNodes = useMemo(() => (steps && step >= 0 ? new Set(steps.slice(0, step + 1)) : null), [steps, step]);
  const current = steps && step >= 0 ? steps[step] : null;
  const previous = steps && step > 0 ? steps[step - 1] : null;
  const isActiveEdge = (e: DEdge) => !activeNodes || (activeNodes.has(e.from) && activeNodes.has(e.to));
  const isCurrentEdge = (e: DEdge) => !!current && e.to === current && (e.from === previous || activeNodes?.has(e.from));

  function go(i: number) {
    if (!steps) return;
    const s = Math.max(0, Math.min(steps.length - 1, i));
    setStep(s); setSelected(steps[s]);
  }

  const sel = byId[selected];
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_300px] gap-4">
      <div className="bg-white border border-gray-200 rounded-lg p-3">
        {steps && (
          <div className="flex items-center gap-2 mb-2 text-xs">
            <button onClick={() => { if (step >= steps.length - 1) go(0); setPlaying(!playing); if (step < 0) go(0); }}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-blue-600 text-white hover:bg-blue-700">
              {playing ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}{playing ? "Pause" : "Play flow"}
            </button>
            <button onClick={() => { setPlaying(false); go(step - 1); }} className="p-1 rounded hover:bg-gray-100" title="Previous stage"><SkipBack className="w-3.5 h-3.5" /></button>
            <button onClick={() => { setPlaying(false); go(step + 1); }} className="p-1 rounded hover:bg-gray-100" title="Next stage"><SkipForward className="w-3.5 h-3.5" /></button>
            <button onClick={() => { setPlaying(false); setStep(-1); }} className="p-1 rounded hover:bg-gray-100" title="Show all flows"><RotateCcw className="w-3.5 h-3.5" /></button>
            <span className="text-gray-500 ml-1">
              {step >= 0 ? `Stage ${step + 1} of ${steps.length}: ${byId[steps[step]]?.title}` : "All flows. Press Play to walk through the stages, or select any box."}
            </span>
          </div>
        )}
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label={caption}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
            </marker>
            <marker id="arrow-on" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="#2563eb" />
            </marker>
          </defs>

          {groups.map((g) => (
            <g key={g.label}>
              <rect x={g.x} y={g.y} width={g.w} height={g.h} rx={10} fill="#f8fafc" stroke="#cbd5e1" strokeDasharray="5 4" />
              <text x={g.x + 10} y={g.y + 16} fontSize={11} fontWeight={600} fill="#64748b">{g.label}</text>
            </g>
          ))}

          {edges.map((e, i) => {
            const a = byId[e.from], b = byId[e.to];
            if (!a || !b) return null;
            const { d, mx, my } = e.via ? routedPath(a, b, e) : edgePath(a, b, e.bend);
            const on = isActiveEdge(e), cur = isCurrentEdge(e);
            return (
              <g key={i} opacity={on ? 1 : 0.18}>
                <path d={d} fill="none" stroke={cur ? "#2563eb" : "#94a3b8"} strokeWidth={cur ? 2.2 : 1.4}
                  strokeDasharray={e.dashed ? "5 4" : undefined} markerEnd={cur ? "url(#arrow-on)" : "url(#arrow)"} />
                {on && (
                  <circle r={cur ? 4 : 3} fill={cur ? "#2563eb" : "#60a5fa"}>
                    <animateMotion dur={`${cur ? 1.2 : 2.6}s`} repeatCount="indefinite" begin={`${(i % 7) * 0.35}s`} path={d} />
                  </circle>
                )}
                {e.label && (
                  <text x={mx} y={my - 5} fontSize={9.5} textAnchor="middle" fill="#64748b"
                    style={{ paintOrder: "stroke", stroke: "white", strokeWidth: 3 }}>{e.label}</text>
                )}
              </g>
            );
          })}

          {nodes.map((n) => {
            const b = box(n), t = TONES[n.tone];
            const dim = activeNodes && !activeNodes.has(n.id);
            const isSel = selected === n.id, isCur = current === n.id;
            return (
              <g key={n.id} onClick={() => setSelected(n.id)} style={{ cursor: "pointer" }} opacity={dim ? 0.25 : 1}>
                {isCur && (
                  <rect x={b.x - 5} y={b.y - 5} width={b.w + 10} height={b.h + 10} rx={11} fill="none" stroke="#2563eb" strokeWidth={2}>
                    <animate attributeName="opacity" values="1;0.3;1" dur="1.2s" repeatCount="indefinite" />
                  </rect>
                )}
                <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={8} fill={t.fill} stroke={t.stroke} strokeWidth={isSel ? 2.4 : 1.2} />
                <text x={b.cx} y={n.sub ? b.cy - 4 : b.cy + 4} fontSize={12} fontWeight={600} textAnchor="middle" fill={t.text}>{n.title}</text>
                {n.sub && <text x={b.cx} y={b.cy + 12} fontSize={9.5} textAnchor="middle" fill="#64748b">{n.sub}</text>}
              </g>
            );
          })}
        </svg>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-gray-500">
          {Array.from(new Set(nodes.map((n) => n.tone))).map((tone) => (
            <span key={tone} className="inline-flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm border" style={{ background: TONES[tone].fill, borderColor: TONES[tone].stroke }} />
              {TONES[tone].tag}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-400" />Data in motion</span>
        </div>
      </div>

      <aside className="bg-white border border-gray-200 rounded-lg p-4 text-sm self-start xl:sticky xl:top-0">
        {sel ? (
          <>
            <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: TONES[sel.tone].stroke }}>{TONES[sel.tone].tag}</div>
            <h3 className="text-base font-semibold text-gray-900 mt-0.5">{sel.title}</h3>
            <p className="text-gray-700 mt-2 leading-relaxed">{sel.what}</p>
            {sel.tech && <Detail label="Technology">{sel.tech}</Detail>}
            {sel.why && <Detail label="Why this choice">{sel.why}</Detail>}
            {sel.numbers && <Detail label="Measured">{sel.numbers}</Detail>}
          </>
        ) : <p className="text-gray-500">Select a box to see its details.</p>}
      </aside>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <div className="text-[11px] font-medium text-gray-500">{label}</div>
      <div className="text-gray-800 mt-0.5 leading-relaxed">{children}</div>
    </div>
  );
}
