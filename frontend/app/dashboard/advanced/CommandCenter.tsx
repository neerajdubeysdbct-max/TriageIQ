"use client";
/**
 * Model Health: which models ran on this dataset, what they produced, how they
 * were trained, and the registry of trained versions. Data: /api/ml-models.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowUpRight, Bot, Loader2, Network, RefreshCw, Tags, Workflow, type LucideIcon } from "lucide-react";
import BERTDrillDown from "./BERTDrillDown";
import XGBoostDrillDown from "./XGBoostDrillDown";
import CategoryDrillDown from "./CategoryDrillDown";
import ModelLifecycle from "../components/ModelLifecycle";
import { IconTile, Meter, Panel, Pill, card } from "../components/Kit";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const hours = (h: number | null | undefined) => (h == null ? "—" : h >= 100 ? `${Math.round(h)}h` : `${h.toFixed(1)}h`);

const STATUS_TONE: Record<string, "green" | "amber" | "indigo" | "zinc"> = {
  trained: "green", rules: "amber", pretrained: "indigo", not_run: "zinc",
};
const STATUS_LABEL: Record<string, string> = { trained: "Trained model", rules: "Rule-based", pretrained: "Pretrained LLM", not_run: "Not run" };

function ModelCard({ title, icon, status, hero, rows, onOpen, note }: {
  title: string; icon: LucideIcon; status: string; hero: [string, string]; rows: [string, string][]; onOpen?: () => void; note?: string;
}) {
  return (
    <button
      type="button"
      disabled={!onOpen}
      onClick={onOpen}
      className={`group flex flex-col text-left ${card} p-5 transition enabled:hover:-translate-y-0.5 enabled:hover:border-indigo-200 enabled:hover:shadow-md enabled:hover:shadow-indigo-500/10 disabled:cursor-default`}
    >
      <div className="flex items-start justify-between gap-2">
        <IconTile icon={icon} tone={status === "rules" ? "amber" : status === "not_run" ? "zinc" : "indigo"} />
        <Pill tone={STATUS_TONE[status] ?? "zinc"}>{STATUS_LABEL[status] ?? status}</Pill>
      </div>
      <h3 className="mt-4 text-sm font-semibold text-zinc-900">{title}</h3>
      <div className="mt-3">
        <div className="text-[28px] font-semibold leading-none tracking-tight text-zinc-900 tabular-nums">{hero[1]}</div>
        <div className="mt-1.5 text-xs text-zinc-500">{hero[0]}</div>
      </div>
      <dl className="mt-4 space-y-2 border-t border-zinc-100 pt-4">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3 text-[13px]">
            <dt className="text-zinc-500">{k}</dt>
            <dd className="font-medium text-zinc-900 tabular-nums text-right">{v}</dd>
          </div>
        ))}
      </dl>
      {note && <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-snug text-amber-800">{note}</p>}
      {onOpen && (
        <div className="mt-auto flex items-center gap-1 pt-4 text-xs font-medium text-indigo-600 opacity-0 transition group-hover:opacity-100">
          View details <ArrowUpRight className="h-3.5 w-3.5" />
        </div>
      )}
    </button>
  );
}

function trainedOn(model: any): string {
  return model?.training_data ? model.training_data.replace(/\.(csv|xlsx?)$/i, "") : "training";
}

export default function CommandCenter({ uploadId, onNavigate }: { uploadId: number; onNavigate?: (view: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drill, setDrill] = useState<"bert" | "xgboost" | "category" | null>(null);
  const [me, setMe] = useState<{ role?: string } | null>(null);

  useEffect(() => {
    fetch(`${API}/api/me`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } })
      .then((r) => (r.ok ? r.json() : null)).then(setMe).catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/ml-models/${uploadId}`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (uploadId) load();
  }, [uploadId]);

  if (loading) return <div className="flex justify-center py-24"><Loader2 className="h-5 w-5 animate-spin text-indigo-500" /></div>;
  if (error || !data) return <p className="text-sm text-red-600">Could not load model status: {error}</p>;

  const { bert_clustering: emb, xgboost_scorer: auto, category_classifier: cat, aiops_classifier: llm } = data.models;
  const m = data.mttr_analysis.by_status;
  const tr = data.training_data;
  const total = data.total_tickets;
  const b = auto.automation_breakdown;

  const statusRows: [string, number, "indigo" | "green" | "zinc"][] = [
    ["Already automated", b.already_automated, "green"],
    ["Can be automated", b.can_automate, "indigo"],
    ["Manual only", b.manual_only, "zinc"],
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        {!auto.validated_on_dataset ? (
          <div className="flex flex-1 items-center justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50/70 px-5 py-3.5">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <p className="text-[13px] leading-relaxed text-amber-900">
                Model accuracy has not been measured on this dataset. Labelling a random sample of tickets measures it and adds training data.
              </p>
            </div>
            <button onClick={() => onNavigate?.("review")} className="btn-primary shrink-0">Label tickets</button>
          </div>
        ) : <div />}
        <button onClick={load} className="btn-secondary shrink-0"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ModelCard
          title={auto.name}
          icon={Workflow}
          status={auto.status}
          onOpen={() => setDrill("xgboost")}
          hero={["Test accuracy", pct(auto.test_metrics?.accuracy)]}
          rows={[
            ["Test macro F1", auto.test_metrics ? auto.test_metrics.macro_f1.toFixed(3) : "—"],
            ["Agrees with rule detector", pct(auto.rule_detector_agreement)],
            ["Tickets scored", auto.tickets_scored.toLocaleString()],
          ]}
          note={auto.validated_on_dataset ? undefined : `Test scores are from the ${trainedOn(tr.automation_model)} held-out test set. Accuracy on this dataset is not yet measured.`}
        />
        <ModelCard
          title={cat.name}
          icon={Tags}
          status={cat.status}
          onOpen={() => setDrill("category")}
          hero={["Test accuracy, L1 tower", pct(cat.test_accuracy?.l1)]}
          rows={[
            ["Test accuracy L2", pct(cat.test_accuracy?.l2)],
            ["Auto-routable", cat.auto_routable_share != null ? `${pct(cat.auto_routable_share, 0)} at ≥${cat.auto_route_threshold}` : "—"],
            ["Tickets classified", cat.tickets_labelled.toLocaleString()],
          ]}
          note={cat.validated_on_dataset ? undefined : `Test scores are from the ${trainedOn(tr.category_model)} held-out test set. Accuracy on this dataset is not yet measured.`}
        />
        <ModelCard
          title={emb.name}
          icon={Network}
          status={emb.status}
          onOpen={() => setDrill("bert")}
          hero={["Clusters found", String(emb.clusters_found)]}
          rows={[
            ["Silhouette", emb.silhouette != null ? emb.silhouette.toFixed(3) : "—"],
            ["Embedding size", emb.dimensions ? `${emb.dimensions}-d` : "—"],
            ["Tickets", emb.tickets_processed.toLocaleString()],
          ]}
        />
        <ModelCard
          title={llm.name}
          icon={Bot}
          status={llm.status}
          hero={["Tickets categorised", llm.tickets_classified.toLocaleString()]}
          rows={[
            ["Towers found", String(llm.towers_found)],
            ["Sample agreement", pct(llm.mean_sample_agreement)],
            ["Calls", "Sampled per cluster"],
          ]}
          note="Qwen 2.5 7B labels a few sample tickets per cluster; the majority answer is applied to the whole cluster. Sample agreement = share of samples that agreed."
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Automation status" note="Predicted by the automation classifier">
          <div className="space-y-4">
            {statusRows.map(([k, v, tone]) => (
              <div key={k}>
                <div className="mb-1.5 flex items-baseline justify-between text-[13px]">
                  <span className="text-zinc-700">{k}</span>
                  <span className="tabular-nums text-zinc-900">
                    <span className="font-medium">{v.toLocaleString()}</span>
                    <span className="ml-1.5 text-zinc-400">{((v / total) * 100).toFixed(1)}%</span>
                  </span>
                </div>
                <Meter pct={(v / total) * 100} tone={tone} />
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Resolution time" note="By automation status. Different ticket populations: a comparison, not a measured saving.">
          <ul className="divide-y divide-zinc-100">
            {[["All tickets", m.overall], ["Automated", m.automated], ["Can be automated", m.can_automate], ["Manual only", m.manual_only]].map(([k, v]: any) => (
              <li key={k} className="flex items-center justify-between py-2.5 text-[13px] first:pt-0 last:pb-0">
                <span className="text-zinc-700">{k}</span>
                <span className="flex items-baseline gap-3">
                  <span className="text-xs text-zinc-400 tabular-nums">{v.tickets.toLocaleString()} tickets</span>
                  <span className="w-14 text-right font-semibold tabular-nums text-zinc-900">{hours(v.avg_hours)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Training provenance" note="What the models applied to this dataset were trained on">
          <dl className="space-y-4 text-[13px]">
            {[["Automation classifier", tr.automation_model], ["Category classifier", tr.category_model]].map(([k, v]: any) => (
              <div key={k} className="border-l-2 border-indigo-200 pl-3">
                <dt className="text-xs font-medium text-zinc-500">{k}</dt>
                <dd className="mt-0.5 leading-snug text-zinc-900">
                  {v ? `${v.n_train?.toLocaleString()} labelled tickets from ${v.training_data}, trained ${String(v.trained_at).replace("T", " ")}` : "Not trained"}
                </dd>
              </div>
            ))}
            <div className="border-l-2 border-indigo-200 pl-3">
              <dt className="text-xs font-medium text-zinc-500">Analyst corrections on this dataset</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-zinc-900">{tr.analyst_corrections.toLocaleString()}</dd>
            </div>
          </dl>
        </Panel>
      </div>

      <ModelLifecycle uploadId={uploadId} isAdmin={me?.role === "admin"} onRescored={() => setTimeout(load, 60000)} />

      <CategoryDrillDown uploadId={uploadId} isOpen={drill === "category"} onClose={() => setDrill(null)} />
      <BERTDrillDown uploadId={uploadId} isOpen={drill === "bert"} onClose={() => setDrill(null)} />
      <XGBoostDrillDown uploadId={uploadId} isOpen={drill === "xgboost"} onClose={() => setDrill(null)} />
    </div>
  );
}
