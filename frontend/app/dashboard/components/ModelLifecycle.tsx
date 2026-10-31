"use client";
/**
 * Model lifecycle: drift for this dataset, retraining from analyst labels with
 * an evaluation gate, version history with rollback, and re-scoring.
 * Data: /api/models/*
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";
import { Pill, card } from "./Kit";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const f1 = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(3));

async function call(path: string, method = "GET") {
  const r = await fetch(`${API}${path}`, { method, headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `${r.status} ${r.statusText}`);
  return body;
}

const DRIFT_TONE: Record<string, "green" | "amber" | "red" | "zinc"> = {
  stable: "green", moderate: "amber", significant: "red", unknown: "zinc",
};

export default function ModelLifecycle({ uploadId, isAdmin, onRescored }: {
  uploadId: number; isAdmin: boolean; onRescored?: () => void;
}) {
  const [drift, setDrift] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [d, s, v] = await Promise.all([
      call(`/api/models/drift/${uploadId}`).catch(() => null),
      call(`/api/models/automation/retrain-status`).catch(() => null),
      call(`/api/models/automation/versions`).catch(() => ({ versions: [] })),
    ]);
    setDrift(d);
    setStatus(s);
    setVersions(v.versions);
    return s;
  }, [uploadId]);

  useEffect(() => { refresh(); }, [refresh]);

  // poll while a retraining run is in progress
  useEffect(() => {
    if (status?.state !== "running") return;
    const t = setInterval(() => refresh(), 4000);
    return () => clearInterval(t);
  }, [status?.state, refresh]);

  async function act(kind: string, fn: () => Promise<any>, done: string) {
    setBusy(kind);
    setMessage(null);
    try {
      await fn();
      setMessage(done);
      await refresh();
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(null);
    }
  }

  const running = status?.state === "running";

  return (
    <section className={card}>
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-100 px-6 py-5">
        <div className="max-w-2xl">
          <h3 className="text-[15px] font-semibold tracking-tight text-zinc-900">Model lifecycle</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-zinc-500">
            Analyst labels from the Review Queue retrain the automation classifier. A new version is deployed only if it
            beats the active one on a frozen test set.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button className="btn-secondary" disabled={!!busy}
            onClick={() => act("rescore", () => call(`/api/models/rescore/${uploadId}`, "POST"),
              "Re-scoring this dataset with the active model. Refresh in a minute.").then(() => onRescored?.())}>
            {busy === "rescore" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Re-score dataset
          </button>
          {isAdmin && (
            <button className="btn-primary" disabled={!!busy || running}
              onClick={() => act("retrain", () => call(`/api/models/automation/retrain`, "POST"), "Retraining started.")}>
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {running ? "Retraining…" : "Retrain from labels"}
            </button>
          )}
        </div>
      </header>

      {message && (
        <p className="mx-6 mt-5 rounded-lg border border-indigo-100 bg-indigo-50 px-3.5 py-2.5 text-[13px] text-indigo-900">{message}</p>
      )}

      <div className="grid grid-cols-1 gap-8 p-6 xl:grid-cols-2">
        {/* Drift */}
        <div>
          <div className="flex items-center gap-2.5">
            <h4 className="text-sm font-semibold text-zinc-900">Drift on this dataset</h4>
            <Pill tone={DRIFT_TONE[drift?.status ?? "unknown"]}>{drift?.status ?? "unknown"}</Pill>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-zinc-600">{drift?.recommendation}</p>
          {drift?.findings?.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[13px] text-zinc-700 marker:text-zinc-300">
              {drift.findings.map((f: any, i: number) => <li key={i}>{f.message}</li>)}
            </ul>
          )}
          {drift?.psi && (
            <dl className="mt-4 grid grid-cols-3 gap-3">
              <Stat label="Known vocabulary" value={pct(drift.known_vocabulary_share)} />
              <Stat label="Unsure tickets" value={`${pct(drift.low_confidence_share)} vs ${pct(drift.validation_low_confidence_share)}`} />
              <Stat label="Max PSI" value={Math.max(...(Object.values(drift.psi) as number[])).toFixed(2)} />
            </dl>
          )}
        </div>

        {/* Last retraining */}
        <div>
          <h4 className="text-sm font-semibold text-zinc-900">Last retraining</h4>
          {!status || status.state === "never_run" ? (
            <p className="mt-2 text-[13px] text-zinc-500">No retraining run yet.</p>
          ) : status.state === "running" ? (
            <p className="mt-2 flex items-center gap-2 text-[13px] text-zinc-600"><Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" /> Running since {status.started_at}</p>
          ) : status.state === "failed" ? (
            <p className="mt-2 flex items-center gap-2 text-[13px] text-red-600"><XCircle className="h-4 w-4" /> Failed: {status.error}</p>
          ) : (
            <div className="mt-2 space-y-3 text-[13px]">
              <p className={`flex items-start gap-2 font-medium ${status.promoted ? "text-emerald-700" : "text-amber-700"}`}>
                {status.promoted ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
                <span>Version {status.version} {status.promoted ? "promoted" : "not promoted"}: {status.reason}</span>
              </p>
              <p className="leading-relaxed text-zinc-500">
                {status.training_rows?.toLocaleString()} training rows, {status.analyst_labels} analyst labels
                ({status.analyst_gold} held out in the frozen test set). Finished {status.finished_at}.
              </p>
              <div className="overflow-hidden rounded-xl border border-zinc-200">
                <table className="w-full">
                  <thead>
                    <tr className="bg-zinc-50/80 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
                      <th className="px-3.5 py-2">Frozen test set</th><th className="px-3.5 py-2 text-right">Active</th><th className="px-3.5 py-2 text-right">Candidate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {Object.keys(status.candidate || {}).map((part) => (
                      <tr key={part}>
                        <td className="px-3.5 py-2 text-zinc-700">{part === "all" ? "All" : part === "base" ? "Base data" : "Analyst labels"} <span className="text-zinc-400">({status.candidate[part].n})</span></td>
                        <td className="px-3.5 py-2 text-right tabular-nums text-zinc-600">{f1(status.active_before?.[part]?.macro_f1)}</td>
                        <td className="px-3.5 py-2 text-right font-medium tabular-nums text-zinc-900">{f1(status.candidate[part].macro_f1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-zinc-400">Macro F1. Experiment tracked in MLflow{status.mlflow_run_id ? ` (run ${status.mlflow_run_id.slice(0, 8)})` : ""}.</p>
            </div>
          )}
        </div>
      </div>

      {/* Versions */}
      <div className="border-t border-zinc-100 px-6 pb-6 pt-5">
        <h4 className="mb-3 text-sm font-semibold text-zinc-900">Versions</h4>
        <div className="overflow-x-auto rounded-xl border border-zinc-200">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="bg-zinc-50/80 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
                <th className="px-4 py-2.5">Version</th><th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Macro F1</th><th className="px-4 py-2.5 text-right">Accuracy</th>
                <th className="px-4 py-2.5">Training data</th><th className="px-4 py-2.5">Gate decision</th><th />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {versions.map((v) => (
                <tr key={v.version} className={v.status === "active" ? "bg-emerald-50/30" : "hover:bg-zinc-50/60"}>
                  <td className="px-4 py-2.5 font-mono text-zinc-900">{v.version}</td>
                  <td className="px-4 py-2.5"><VersionStatus status={v.status} /></td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{f1(v.macro_f1)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{pct(v.accuracy)}</td>
                  <td className="px-4 py-2.5 text-zinc-600">{v.training_data ?? "—"}</td>
                  <td className="max-w-xs truncate px-4 py-2.5 text-zinc-600" title={v.decision ?? ""}>{v.decision ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right">
                    {isAdmin && v.can_activate && (
                      <button className="font-medium text-indigo-600 hover:text-indigo-800" disabled={!!busy}
                        onClick={() => act("activate", () => call(`/api/models/automation/versions/${v.version}/activate`, "POST"),
                          `Version ${v.version} is now active. Re-score datasets to apply it.`)}>
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-zinc-50 px-3 py-2.5">
      <dt className="text-[11px] text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold tabular-nums text-zinc-900">{value}</dd>
    </div>
  );
}

function VersionStatus({ status }: { status: string }) {
  const tone = ({ active: "green", candidate: "indigo" } as const)[status as "active" | "candidate"] ?? "zinc";
  return <Pill tone={tone}>{status}</Pill>;
}
