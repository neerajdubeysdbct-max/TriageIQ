"use client";
/**
 * Category classifier detail: held-out accuracy against baselines, how often it is
 * confident enough to auto-route, and what it confuses. Data: /api/system/model-evaluation.
 */
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowRight, Loader2, Tags } from "lucide-react";
import Drawer from "../components/Drawer";
import { DataTable, Metric, Panel, Pill, Ring } from "../components/Kit";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const num = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(3));
const AXIS = { fontSize: 11, fill: "#71717A" };

const LEVELS: Record<string, { name: string; hint: string }> = {
  l1: { name: "L1 tower", hint: "The broad team or area a ticket belongs to" },
  l2: { name: "L2 subcategory", hint: "The specific ticket type within a tower" },
};

export default function CategoryDrillDown({ uploadId, isOpen, onClose }: { uploadId: number; isOpen: boolean; onClose: () => void }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState<"l1" | "l2">("l1");

  useEffect(() => {
    if (!isOpen || !uploadId || data) return;
    fetch(`${API}/api/system/model-evaluation/${uploadId}`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } })
      .then(async (r) => (r.ok ? setData(await r.json()) : setError((await r.json()).detail || r.statusText)))
      .catch((e) => setError(String(e)));
  }, [isOpen, uploadId, data]);

  const report = data?.category;
  const upload = data?.category_upload;
  const lv = report?.levels?.[level];
  const model = lv?.test_results?.[lv.test_results.length - 1];

  return (
    <Drawer isOpen={isOpen} onClose={onClose} icon={Tags} title="Category classifier"
      subtitle="Routes a ticket to a tower (L1) and subcategory (L2) from creation-time fields only">
      <div className="mx-auto max-w-5xl space-y-6 p-8">
        {error ? (
          <p className="py-20 text-center text-sm text-zinc-500">No evaluation available: {error}</p>
        ) : !data ? (
          <div className="flex justify-center py-24"><Loader2 className="h-5 w-5 animate-spin text-indigo-500" /></div>
        ) : !report ? (
          <p className="py-20 text-center text-sm text-zinc-500">The category model has not been trained yet.</p>
        ) : (
          <>
            <p className="text-[13px] leading-relaxed text-zinc-600">
              Logistic regression on TF-IDF word and character n-grams, plus channel, category field and priority. Closure
              notes and the assigned team are excluded on purpose: they don&apos;t exist when a ticket needs routing.
              Scores below are from {report.data.split.test.toLocaleString()} held-out tickets of{" "}
              <code className="rounded bg-white px-1.5 py-0.5 text-[12px] ring-1 ring-zinc-200">{report.data.tickets}</code>.
            </p>

            <div className="inline-flex gap-1 rounded-xl bg-zinc-200/60 p-1">
              {Object.keys(report.levels).map((k) => (
                <button key={k} onClick={() => setLevel(k as "l1" | "l2")}
                  className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${level === k ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-800"}`}>
                  {LEVELS[k]?.name ?? k}
                </button>
              ))}
            </div>

            {lv && model && (
              <>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  <Metric accent label="Test accuracy" value={pct(model.accuracy)} sub={`${lv.n_classes} classes · ${LEVELS[level]?.hint}`} />
                  <Metric label="Test macro F1" value={num(model.macro_f1)} sub="average across classes" />
                  <Metric label="Best baseline"
                    value={pct(Math.max(...lv.test_results.slice(0, -1).map((r: any) => r.accuracy)))}
                    sub={lv.test_results.slice(0, -1).sort((a: any, b: any) => b.accuracy - a.accuracy)[0]?.model} />
                  <div className="flex items-center gap-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm shadow-zinc-900/[0.03]">
                    <Ring value={upload?.auto_routable_share} size={64} />
                    <div>
                      <div className="text-xs font-medium text-zinc-500">Auto-routable here</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums text-zinc-900">{pct(upload?.auto_routable_share, 0)}</div>
                      <div className="text-xs text-zinc-500">at ≥ {upload?.auto_route_threshold ?? "—"} confidence</div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-6 lg:grid-cols-2">
                  <Panel title="Against baselines" note="A model only earns its place if it beats the simple alternatives on the same test tickets.">
                    <ResponsiveContainer width="100%" height={Math.max(160, lv.test_results.length * 44)}>
                      <BarChart data={lv.test_results} layout="vertical" margin={{ left: 8, right: 24 }}>
                        <CartesianGrid horizontal={false} stroke="#F4F4F5" />
                        <XAxis type="number" domain={[0, 1]} tick={AXIS} axisLine={false} tickLine={false} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                        <YAxis type="category" dataKey="model" width={170} tick={{ ...AXIS, fill: "#3F3F46" }} axisLine={false} tickLine={false} />
                        <Tooltip formatter={(v: any): any => [pct(Number(v)), "Accuracy"]} cursor={{ fill: "#FAFAFA" }} />
                        <Bar dataKey="accuracy" radius={[0, 6, 6, 0]} barSize={18}>
                          {lv.test_results.map((_: any, i: number) => <Cell key={i} fill={i === lv.test_results.length - 1 ? "#6366F1" : "#D4D4D8"} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Panel>

                  <Panel title="Route only when confident" note="Raising the confidence bar trades coverage for accuracy. Tickets below it go to a person.">
                    <DataTable
                      head={["Confidence ≥", "Share of tickets", "Accuracy"]}
                      rows={lv.selective_accuracy.map((s: any) => [String(s.threshold), pct(s.coverage), pct(s.accuracy)])}
                    />
                  </Panel>
                </div>

                <Panel title="What it confuses" note="The most frequent mistakes on the test set. Many are genuinely ambiguous wording, such as two issues that both say &quot;unable to login&quot;.">
                  {lv.top_confusions?.length ? (
                    <ul className="divide-y divide-zinc-100">
                      {lv.top_confusions.map((c: any, i: number) => (
                        <li key={i} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                          <span className="flex flex-wrap items-center gap-2 text-[13px]">
                            <Pill tone="green">{c.true}</Pill>
                            <ArrowRight className="h-3.5 w-3.5 text-zinc-300" />
                            <Pill tone="red">{c.predicted}</Pill>
                          </span>
                          <span className="text-[13px] tabular-nums text-zinc-500"><b className="font-semibold text-zinc-900">{c.count}</b> tickets</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-sm text-zinc-500">No notable confusions recorded.</p>}
                </Panel>
              </>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
}
