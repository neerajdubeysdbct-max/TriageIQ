"use client";
/**
 * Copilot. Each question is planned by the local model (data query, ticket search or
 * both), answered only from that evidence, and verified: every cited ticket must be
 * one that was retrieved, and numbers not present in the evidence are flagged.
 * Each answer shows how it was produced so it can be checked. Questions are answered
 * independently; there is no conversation memory.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Download, Loader2, Search, ShieldCheck } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TICKET_ID = /\[([A-Z]{2,6}\d{4,})\]/g;

const SUGGESTIONS = [
  "Which team has the longest average resolution time?",
  "What share of P1 tickets breached their SLA?",
  "How are disk space alerts usually fixed?",
  "Why do App Support L3 tickets take so long?",
  "How many tickets came in each month?",
];

type Ticket = {
  id: number; number: string; short_description: string; close_notes: string | null;
  assignment_group: string | null; priority: string | null; resolved_by: string | null;
  mttr_hours: number | null; automation_status: string | null; category: string | null;
  opened: string | null; score: number | null;
};
type DataResult = {
  description: string; metric_label: string; baseline: number | null;
  query: { metric: string; group_by: string | null };
  rows: { key?: string; value: number | null; tickets?: number; avg_hours?: number | null }[];
};
type Answer = {
  answer: string;
  plan: { aggregate: any; search_query: string | null; error: string | null; repaired?: boolean; linked_filters?: string[] };
  data: DataResult | null;
  citations: Ticket[];
  retrieved?: Ticket[];
  verification: { cited: string[]; invalid: string[]; unsupported_numbers?: string[]; revised?: boolean;
                  unsupported_before_revision?: string[]; blocked?: boolean };
  timings: Record<string, number>;
};
type Turn = { question: string; result?: Answer; error?: string };

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json" };
}

const isShare = (metric: string) => metric === "sla_breach_rate" || metric === "automatable_rate";
function formatValue(v: number | null, metric: string) {
  if (v == null) return "—";
  if (isShare(metric)) return `${(v * 100).toFixed(1)}%`;
  if (metric === "count") return v.toLocaleString();
  return v.toFixed(2);
}

export default function Copilot({ uploadId }: { uploadId: number }) {
  const [indexed, setIndexed] = useState<boolean | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [exports, setExports] = useState<{ key: string; label: string }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const checkIndex = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/rag/status/${uploadId}`, { headers: authHeaders() });
      const j = await r.json();
      setIndexed(!!j.indexed);
      return !!j.indexed;
    } catch {
      setIndexed(false);
      return false;
    }
  }, [uploadId]);

  useEffect(() => {
    setTurns([]);
    setSelected(null);
    checkIndex();
    fetch(`${API}/api/copilot/export/available`, { headers: authHeaders() })
      .then((r) => r.json()).then((j) => setExports(j.exports || [])).catch(() => setExports([]));
  }, [uploadId, checkIndex]);

  useEffect(() => {
    if (!indexing) return;
    const t = setInterval(async () => { if (await checkIndex()) setIndexing(false); }, 5000);
    return () => clearInterval(t);
  }, [indexing, checkIndex]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  async function buildIndex() {
    setIndexing(true);
    await fetch(`${API}/api/rag/index/${uploadId}`, { method: "POST", headers: authHeaders() }).catch(() => setIndexing(false));
  }

  async function ask(question: string) {
    const q = question.trim();
    if (q.length < 3 || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { question: q }]);
    let update: Turn;
    try {
      const r = await fetch(`${API}/api/rag/ask`, {
        method: "POST", headers: authHeaders(), body: JSON.stringify({ upload_id: uploadId, question: q }),
      });
      const j = await r.json();
      update = r.ok ? { question: q, result: j } : { question: q, error: j.detail || `${r.status} ${r.statusText}` };
    } catch (e: any) {
      update = { question: q, error: e.message };
    }
    setTurns((t) => [...t.slice(0, -1), update]);
    if (update.result?.citations?.length) setSelected(update.result.citations[0]);
    setBusy(false);
  }

  function openTicket(number: string, result: Answer) {
    const t = (result.retrieved || result.citations).find((x) => x.number === number);
    if (t) setSelected(t);
  }

  if (indexed === false) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-xl">
        <h2 className="text-sm font-semibold text-gray-900">Search index not built</h2>
        <p className="text-sm text-gray-600 mt-1">
          The copilot searches ticket descriptions and closure notes. This dataset was uploaded before the index existed,
          so it needs to be built once (about 8 seconds per 1,000 tickets).
        </p>
        <button onClick={buildIndex} disabled={indexing} className="btn-primary mt-4 inline-flex items-center gap-2">
          {indexing && <Loader2 className="w-4 h-4 animate-spin" />}
          {indexing ? "Building index" : "Build search index"}
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-4">
      <div className="bg-white border border-gray-200 rounded-lg flex flex-col min-h-[640px]">
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {turns.length === 0 && (
            <div className="text-sm text-gray-600">
              <p>
                Ask about counts, rates and resolution times across all tickets, or about how and why issues were resolved.
                Numbers come from a database query; explanations come from the tickets themselves, which are cited.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => ask(s)}
                    className="px-3 py-1.5 rounded-md border border-gray-200 text-xs text-gray-700 hover:border-blue-500 hover:bg-blue-50">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className="space-y-2">
              <div className="text-sm font-medium text-gray-900">{t.question}</div>
              {!t.result && !t.error && (
                <div className="flex items-center gap-2 text-sm text-gray-500"><Loader2 className="w-4 h-4 animate-spin" />Working</div>
              )}
              {t.error && <div className="text-sm text-red-700">{t.error}</div>}
              {t.result && <AnswerView result={t.result} onCite={(n) => openTicket(n, t.result!)} />}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); ask(input); }} className="border-t border-gray-100 p-3 flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy || indexed === null}
            placeholder="Ask a question about this dataset" maxLength={1000}
            className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          <button type="submit" disabled={busy || input.trim().length < 3} className="btn-primary">Ask</button>
        </form>
      </div>

      <aside className="space-y-4">
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-gray-900">Source ticket</h2>
          {selected ? <TicketCard t={selected} /> : (
            <p className="text-xs text-gray-500 mt-2">Select a cited ticket number in an answer to see the ticket here.</p>
          )}
        </section>
        {exports.length > 0 && (
          <section className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-900">Exports</h2>
            <div className="mt-2 divide-y divide-gray-100">
              {exports.map((x) => (
                <div key={x.key} className="flex items-center justify-between py-1.5 text-xs">
                  <span className="text-gray-700">{x.label}</span>
                  <span className="flex gap-3">
                    {(["csv", "excel"] as const).map((fmt) => (
                      <a key={fmt} target="_blank" rel="noreferrer"
                        href={`${API}/api/copilot/export/${fmt}/${x.key}?upload_id=${uploadId}&token=${encodeURIComponent(localStorage.getItem("token") || "")}`}
                        className="inline-flex items-center gap-1 text-blue-700 hover:underline">
                        <Download className="w-3 h-3" />{fmt === "csv" ? "CSV" : "XLSX"}
                      </a>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}
        <section className="bg-white border border-gray-200 rounded-lg p-4 text-xs text-gray-600 space-y-1.5">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">How answers are produced</h2>
          <div className="flex justify-between"><span>Language model</span><span>Qwen 2.5 7B, local (Ollama)</span></div>
          <div className="flex justify-between"><span>Ticket search</span><span>Embeddings + full text, fused</span></div>
          <div className="flex justify-between"><span>Numbers</span><span>Whitelisted database query</span></div>
          <div className="flex justify-between"><span>Data leaves this server</span><span>No</span></div>
        </section>
      </aside>
    </div>
  );
}

function AnswerView({ result, onCite }: { result: Answer; onCite: (n: string) => void }) {
  const [open, setOpen] = useState(false);
  const v = result.verification;
  const flagged = v.unsupported_numbers?.length ? v.unsupported_numbers : null;
  return (
    <div className="space-y-2">
      <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{renderWithCitations(result.answer, onCite)}</div>
      {result.data && <DataTable data={result.data} />}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {v.blocked ? (
          <span className="inline-flex items-center gap-1 text-amber-700">
            <AlertTriangle className="w-3.5 h-3.5" />Answer withheld: it contained numbers that are not in the data
          </span>
        ) : flagged ? (
          <span className="inline-flex items-center gap-1 text-amber-700">
            <AlertTriangle className="w-3.5 h-3.5" />Not found in the evidence: {flagged.join(", ")}. Check before using.
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <ShieldCheck className="w-3.5 h-3.5" />
            {v.cited.length ? `${v.cited.length - v.invalid.length} citations checked, ` : ""}all numbers found in the evidence
          </span>
        )}
        <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-0.5 text-gray-500 hover:text-gray-800">
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}How this was answered
        </button>
      </div>
      {open && (
        <div className="bg-gray-50 rounded-md p-3 text-xs text-gray-700 space-y-1.5">
          <div><span className="text-gray-500">Data query: </span>{result.data ? result.data.description : "none"}</div>
          <div className="flex items-center gap-1">
            <Search className="w-3 h-3 text-gray-400" /><span className="text-gray-500">Ticket search: </span>
            {result.plan.search_query ? `"${result.plan.search_query}" (${result.retrieved?.length ?? 0} tickets retrieved)` : "none"}
          </div>
          {!!result.plan.linked_filters?.length && (
            <div>Filter added from names in the question: {result.plan.linked_filters.join(", ")}</div>
          )}
          {result.plan.repaired && !result.plan.error && <div>The first plan was invalid; the model corrected it after seeing the error.</div>}
          {result.plan.error && <div className="text-amber-700">Planner output rejected: {result.plan.error}. Fell back to ticket search only.</div>}
          {v.invalid.length > 0 && <div className="text-amber-700">Removed citations to tickets that were not retrieved: {v.invalid.join(", ")}</div>}
          {v.revised && (
            <div>First draft contained numbers not in the evidence ({v.unsupported_before_revision?.join(", ")}); the answer was regenerated.</div>
          )}
          <div className="text-gray-500">
            Planning {fmtMs(result.timings.plan_ms)} · retrieval {fmtMs(result.timings.retrieve_ms)} · answer {fmtMs(result.timings.answer_ms)}
          </div>
        </div>
      )}
    </div>
  );
}

function DataTable({ data }: { data: DataResult }) {
  const m = data.query.metric;
  const grouped = data.rows.length > 0 && data.rows[0].key !== undefined;
  return (
    <div className="border border-gray-200 rounded-md overflow-hidden max-w-lg">
      <div className="px-3 py-1.5 bg-gray-50 text-[11px] text-gray-500">{data.description}</div>
      {data.rows.length === 0 ? (
        <div className="px-3 py-2 text-xs text-gray-500">No matching tickets</div>
      ) : grouped ? (
        <table className="w-full text-xs">
          <tbody className="divide-y divide-gray-100">
            {data.rows.map((r) => (
              <tr key={r.key}>
                <td className="px-3 py-1 text-gray-800">{r.key}</td>
                <td className="px-3 py-1 text-right tabular-nums font-medium">{formatValue(r.value, m)}</td>
                {m !== "count" && <td className="px-3 py-1 text-right tabular-nums text-gray-500">{r.tickets?.toLocaleString()} tickets</td>}
                {m !== "avg_resolution_hours" && r.avg_hours != null && (
                  <td className="px-3 py-1 text-right tabular-nums text-gray-500">MTTR {r.avg_hours.toFixed(2)} h</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="px-3 py-2 text-sm font-medium tabular-nums">{formatValue(data.rows[0].value, m)}</div>
      )}
      {data.baseline != null && (
        <div className="px-3 py-1.5 border-t border-gray-100 text-[11px] text-gray-500">All tickets: {formatValue(data.baseline, m)}</div>
      )}
    </div>
  );
}

function TicketCard({ t }: { t: Ticket }) {
  return (
    <div className="mt-2 space-y-2 text-xs">
      <div className="flex flex-wrap gap-x-3 text-gray-500">
        <span className="font-mono text-gray-900">{t.number}</span>
        {t.priority && <span>{t.priority}</span>}
        {t.assignment_group && <span>{t.assignment_group}</span>}
      </div>
      <div><div className="text-[11px] text-gray-500">Short description</div><div className="text-gray-900">{t.short_description}</div></div>
      <div><div className="text-[11px] text-gray-500">Closure notes</div><div className="text-gray-900">{t.close_notes || "None"}</div></div>
      <div className="grid grid-cols-2 gap-2">
        <Fact label="Resolved by" value={t.resolved_by || "—"} />
        <Fact label="Resolution time" value={t.mttr_hours != null ? `${t.mttr_hours} h` : "—"} />
        <Fact label="Category" value={t.category || "—"} />
        <Fact label="Automation" value={t.automation_status || "—"} />
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-gray-50 rounded-md px-2 py-1.5">
      <div className="text-gray-500">{label}</div>
      <div className="text-gray-900 font-medium mt-0.5 break-words">{value}</div>
    </div>
  );
}

function renderWithCitations(text: string, onCite: (n: string) => void) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(TICKET_ID)) {
    parts.push(text.slice(last, m.index));
    const n = m[1];
    parts.push(
      <button key={`${n}-${m.index}`} onClick={() => onCite(n)}
        className="font-mono text-[12px] text-blue-700 bg-blue-50 rounded px-1 hover:bg-blue-100">{n}</button>
    );
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

const fmtMs = (ms?: number) => (ms == null ? "—" : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);
