"use client";
/**
 * Review queue. Analysts label tickets one at a time; labels from the random
 * sample measure the classifier's accuracy on this dataset, and every label
 * becomes training data. The model's answer is hidden until the analyst answers.
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const OPTIONS = [
  { key: "1", label: "Already Automated" },
  { key: "2", label: "Can Be Automated" },
  { key: "3", label: "Manual Only" },
];
type Mode = "random" | "uncertain";

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

function api(path: string, init?: RequestInit) {
  return fetch(`${API}/api/review/${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json", ...(init?.headers || {}) },
  }).then(async (r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  });
}

export default function ReviewQueue({ uploadId }: { uploadId: number }) {
  const [mode, setMode] = useState<Mode>("random");
  const [ticket, setTicket] = useState<any>(undefined);
  const [answer, setAnswer] = useState<string | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadNext = useCallback(async () => {
    setAnswer(null);
    setTicket(undefined);
    try {
      const [next, sum] = await Promise.all([api(`${uploadId}/next?mode=${mode}`), api(`${uploadId}/summary`)]);
      setTicket(next.ticket);
      setSummary(sum);
    } catch (e: any) {
      setError(e.message);
    }
  }, [uploadId, mode]);

  useEffect(() => { loadNext(); }, [loadNext]);

  async function submit(label: string) {
    if (!ticket || answer || busy) return;
    setBusy(true);
    try {
      await api(`${uploadId}/label`, { method: "POST", body: JSON.stringify({ ticket_id: ticket.id, label, mode }) });
      if (label === "Skipped") return loadNext();
      setAnswer(label);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      const opt = OPTIONS.find((o) => o.key === e.key);
      if (opt && !answer) submit(opt.label);
      else if (e.key.toLowerCase() === "s" && !answer) submit("Skipped");
      else if ((e.key === "Enter" || e.key === " ") && answer) { e.preventDefault(); loadNext(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const acc = summary?.accuracy;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-5 max-w-6xl">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="inline-flex rounded-md border border-gray-300 overflow-hidden text-xs">
            {([["random", "Random sample"], ["uncertain", "Least confident first"]] as [Mode, string][]).map(([m, label]) => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1.5 ${mode === m ? "bg-gray-900 text-white" : "bg-white text-gray-700 hover:bg-gray-50"}`}>
                {label}
              </button>
            ))}
          </div>
          <span className="text-xs text-gray-500">Keys: 1 · 2 · 3 to answer, S to skip, Enter for next</span>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {ticket === undefined ? (
          <div className="bg-white border border-gray-200 rounded-lg p-10 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
        ) : ticket === null ? (
          <div className="bg-white border border-gray-200 rounded-lg p-10 text-center text-sm text-gray-600">Every ticket in this dataset has been reviewed.</div>
        ) : (
          <article className="bg-white border border-gray-200 rounded-lg">
            <header className="px-5 py-3 border-b border-gray-100 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
              <span className="font-mono text-gray-900">{ticket.number}</span>
              {ticket.priority && <span>{ticket.priority}</span>}
              {ticket.channel && <span>{ticket.channel}</span>}
              {ticket.assignment_group && <span>{ticket.assignment_group}</span>}
              {ticket.category && <span>Category: {ticket.category}</span>}
            </header>
            <div className="px-5 py-4 space-y-3 text-sm">
              <Field label="Short description">{ticket.short_description}</Field>
              {ticket.description && ticket.description !== ticket.short_description && <Field label="Description">{ticket.description}</Field>}
              <Field label="Closure notes">{ticket.close_notes || <span className="text-gray-400">None</span>}</Field>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <Fact label="Resolved by" value={ticket.resolved_by || "—"} />
                <Fact label="Resolution time" value={ticket.mttr_hours != null ? `${ticket.mttr_hours} h` : "—"} />
                <Fact label="Reassignments" value={ticket.reassignment_count ?? "—"} />
              </div>
            </div>
            <footer className="px-5 py-4 border-t border-gray-100">
              {!answer ? (
                <div className="flex flex-wrap gap-2">
                  {OPTIONS.map((o) => (
                    <button key={o.key} disabled={busy} onClick={() => submit(o.label)}
                      className="px-3 py-2 rounded-md border border-gray-300 text-sm text-gray-800 hover:border-blue-500 hover:bg-blue-50">
                      <span className="text-gray-400 mr-2">{o.key}</span>{o.label}
                    </button>
                  ))}
                  <button disabled={busy} onClick={() => submit("Skipped")} className="px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-50">
                    <span className="text-gray-400 mr-2">S</span>Not sure
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    {ticket.model.status === answer
                      ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      : <XCircle className="w-4 h-4 text-amber-600" />}
                    <span className="text-gray-700">
                      You: <b>{answer}</b> · Model: <b>{ticket.model.status ?? "not scored"}</b>
                      {ticket.model.confidence != null && <> ({pct(ticket.model.confidence)} confident)</>}
                    </span>
                  </div>
                  <button onClick={loadNext} className="btn-primary">Next ticket</button>
                </div>
              )}
            </footer>
          </article>
        )}
      </div>

      <aside className="space-y-4">
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-gray-900">Accuracy on this dataset</h2>
          {acc?.reportable ? (
            <>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{pct(acc.accuracy)}</div>
              <p className="text-xs text-gray-500 mt-1">
                95% confidence interval {pct(acc.ci95[0])} to {pct(acc.ci95[1])}, from {acc.sample_size} randomly sampled tickets.
              </p>
              <table className="w-full text-xs mt-3">
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(acc.per_class).map(([k, v]: [string, any]) => (
                    <tr key={k}><td className="py-1 text-gray-700">{k}</td>
                      <td className="py-1 text-right tabular-nums">{v.labelled} labelled</td>
                      <td className="py-1 text-right tabular-nums">recall {pct(v.recall)}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="text-xs text-gray-500 mt-2">
              Not measured yet. Label at least {acc?.min_sample ?? 30} tickets from the random sample
              ({acc?.sample_size ?? 0} so far). Labels from the least-confident queue are excluded because that queue picks hard tickets on purpose.
            </p>
          )}
        </section>
        <section className="bg-white border border-gray-200 rounded-lg p-4 text-xs text-gray-600 space-y-1.5">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">Progress</h2>
          <div className="flex justify-between"><span>Labelled</span><span className="tabular-nums">{summary?.labelled ?? 0} of {summary?.total_tickets?.toLocaleString() ?? "—"}</span></div>
          <div className="flex justify-between"><span>Random sample</span><span className="tabular-nums">{summary?.by_source?.random_sample ?? 0}</span></div>
          <div className="flex justify-between"><span>Least confident queue</span><span className="tabular-nums">{summary?.by_source?.uncertainty_queue ?? 0}</span></div>
          <div className="flex justify-between"><span>Skipped</span><span className="tabular-nums">{summary?.skipped ?? 0}</span></div>
          <p className="pt-2 text-gray-500">Labels override the model on the dashboard and are used as training data when the classifier is retrained.</p>
        </section>
      </aside>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-medium text-gray-500">{label}</div>
      <div className="text-gray-900 mt-0.5 break-words">{children}</div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-gray-50 rounded-md px-3 py-2">
      <div className="text-gray-500">{label}</div>
      <div className="text-gray-900 font-medium mt-0.5 break-all">{value}</div>
    </div>
  );
}
