"use client";
/**
 * Application shell: one sidebar, one header, one content area.
 * The active view and dataset are kept in the URL (?view=…&upload_id=…).
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, FileText, Loader2, PanelLeftClose, PanelLeftOpen, Presentation } from "lucide-react";

import AppSidebar, { NAV_ITEMS, View } from "./components/AppSidebar";
import KpiCards from "./components/KpiCards";
import ClusterMap from "./components/ClusterMap";
import AutomationDonut from "./components/AutomationDonut";
import TicketTable from "./components/TicketTable";
import ClustersTab from "./components/ClustersTab";
import AutomationOpportunitiesTab from "./components/AutomationOpportunitiesTab";
import ROICalculator from "./components/ROICalculator";
import TicketIntelligenceTab from "./components/TicketIntelligenceTab";
import Copilot from "./components/Copilot";
import Architecture from "./architecture/Architecture";
import ModelEvaluation from "./components/ModelEvaluation";
import ReviewQueue from "./components/ReviewQueue";
import { ActivityLog, SettingsPanel } from "./components/SystemPanels";
import CommandCenter from "./advanced/CommandCenter";
import PredictionsRisk from "./advanced/PredictionsRisk";
import AnomalyDetection from "./advanced/AnomalyDetection";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const VIEWS: View[] = NAV_ITEMS.map((i) => i.view);
const EXPORT_VIEWS: View[] = ["overview", "tickets", "automation"];

// Names used by older components when they ask to switch tabs
const LEGACY_TABS: Record<string, View> = {
  Overview: "overview", Clusters: "clusters", AutomationOpportunities: "automation",
  "Automation Opportunities": "automation", "Ticket Intelligence": "tickets", "ROI Calculator": "roi",
};

const SUBTITLES: Partial<Record<View, string>> = {
  tickets: "Every ticket with its predicted category, automation status and evidence",
  automation: "Tickets that can be automated, grouped by solution and ticket type",
  clusters: "Recurring ticket themes found by clustering ticket descriptions",
  sla: "Historical SLA consumption and a backtested volume forecast",
  anomalies: "Tickets that behave unusually for their type",
  roi: "Savings estimate from the automation opportunities in this dataset",
  copilot: "Ask questions about this dataset",
  architecture: "How TriageIQ works and why: for presenting to clients, leadership and interviewers",
  review: "Label tickets to measure accuracy on this dataset and to train the models",
  evaluation: "How each model was tested and how it performs",
  health: "Which models ran on this dataset and what they produced",
  activity: "Uploads, processing outcomes and model training runs",
  settings: "Pipeline configuration",
};

function token() {
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}

export default function DashboardPage() {
  const router = useRouter();
  const [view, setView] = useState<View>("overview");
  // The navigation can be hidden to present a single view full width; remembered per browser
  const [navHidden, setNavHidden] = useState(false);
  useEffect(() => {
    try { setNavHidden(localStorage.getItem("triageiq.navHidden") === "1"); } catch {}
  }, []);
  function toggleNav() {
    const next = !navHidden;
    setNavHidden(next);
    try { localStorage.setItem("triageiq.navHidden", next ? "1" : "0"); } catch {}
  }
  const [uploads, setUploads] = useState<any[]>([]);
  const [upload, setUpload] = useState<any>(null);
  const [kpis, setKpis] = useState<any>(null);
  const [tickets, setTickets] = useState<any[]>([]);
  const [me, setMe] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState<"excel" | "ppt" | null>(null);

  useEffect(() => {
    const t = token();
    if (!t) return router.push("/login");
    const params = new URLSearchParams(window.location.search);
    const v = params.get("view") as View | null;
    if (v && VIEWS.includes(v)) setView(v);
    load(t, params.get("upload_id") ? Number(params.get("upload_id")) : undefined);
  }, []);

  function syncUrl(nextView: View, uploadId?: number) {
    const params = new URLSearchParams();
    params.set("view", nextView);
    if (uploadId) params.set("upload_id", String(uploadId));
    window.history.replaceState({}, "", `?${params}`);
  }

  function changeView(next: View | string) {
    const v = (VIEWS.includes(next as View) ? next : LEGACY_TABS[next as string]) as View | undefined;
    if (!v) return;
    setView(v);
    syncUrl(v, upload?.id);
  }

  async function load(t: string, uploadId?: number) {
    setLoading(true);
    setError("");
    try {
      const headers = { Authorization: `Bearer ${t}` };
      const [meRes, upRes] = await Promise.all([fetch(`${API}/api/me`, { headers }), fetch(`${API}/api/uploads`, { headers })]);
      if (upRes.status === 401) return router.push("/login");
      if (meRes.ok) setMe(await meRes.json());
      const list = await upRes.json();
      setUploads(list);
      if (!list.length) {
        setError("No datasets yet. Upload a ticket export to begin.");
        return;
      }
      const chosen = list.find((u: any) => u.id === uploadId)
        ?? list.find((u: any) => u.status === "completed" && u.total_tickets > 0) ?? list[0];
      setUpload(chosen);
      syncUrl((new URLSearchParams(window.location.search).get("view") as View) || "overview", chosen.id);
      if (chosen.status === "saving" || chosen.status === "processing") {
        setTimeout(() => load(t, chosen.id), 4000);
        return;
      }
      const [kRes, tRes] = await Promise.all([
        fetch(`${API}/api/dashboard-kpis/${chosen.id}`, { headers }),
        fetch(`${API}/api/tickets/${chosen.id}?limit=50`, { headers }),
      ]);
      setKpis(kRes.ok ? await kRes.json() : null);
      setTickets(tRes.ok ? await tRes.json() : []);
    } catch (e: any) {
      setError(e.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  async function downloadExport(kind: "excel" | "ppt") {
    if (!upload?.id) return;
    setExporting(kind);
    try {
      const base = `${API}/api/ticket-intelligence/${upload.id}/export`;
      const name = (upload.filename || "dataset").replace(/\.(csv|xlsx?)$/i, "");
      const headers = { Authorization: `Bearer ${token()}` };
      const res = kind === "excel"
        ? await fetch(`${base}/excel`, { headers })
        : await fetch(`${base}/ppt`, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ client_name: name }) });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name}_${kind === "excel" ? "analysis.xlsx" : "deck.pptx"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Export failed: ${err}`);
    } finally {
      setExporting(null);
    }
  }

  const label = NAV_ITEMS.find((i) => i.view === view)?.label ?? "";
  const processing = upload && (upload.status === "saving" || upload.status === "processing");
  const dumpType = kpis?.record_type;

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50 text-zinc-900">
      {!navHidden && <AppSidebar
        view={view}
        onViewChange={changeView}
        uploads={uploads}
        selectedUploadId={upload?.id}
        onDatasetChange={(id) => { const t = token(); if (t) load(t, id); }}
        user={me}
      />}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 shrink-0 bg-white/80 backdrop-blur border-b border-zinc-200 px-8 flex items-center justify-between">
          <div className="min-w-0 flex items-center gap-3">
            <button onClick={toggleNav} className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-800"
              title={navHidden ? "Show navigation" : "Hide navigation"} aria-label={navHidden ? "Show navigation" : "Hide navigation"}>
              {navHidden ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
            <div className="min-w-0">
            <h1 className="text-[15px] font-semibold tracking-tight text-gray-900">{label}</h1>
            <p className="text-xs text-gray-500 truncate">
              {view === "overview" && upload
                ? [upload.filename, `${upload.total_tickets?.toLocaleString()} tickets`, dumpType?.label && `${dumpType.label} export`]
                    .filter(Boolean).join(" · ")
                : SUBTITLES[view] ?? ""}
            </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {upload?.status === "failed" && (
              <span className="text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">Processing failed</span>
            )}
            {EXPORT_VIEWS.includes(view) && upload?.status === "completed" && (
              <>
                <button className="btn-secondary" disabled={!!exporting} onClick={() => downloadExport("excel")}>
                  {exporting === "excel" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                  Excel
                </button>
                <button className="btn-secondary" disabled={!!exporting} onClick={() => downloadExport("ppt")}>
                  {exporting === "ppt" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Presentation className="w-3.5 h-3.5" />}
                  PowerPoint
                </button>
              </>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-8 py-7">
          {view === "architecture" ? (
            <Architecture />
          ) : loading && !processing ? (
            <Centered><Loader2 className="w-6 h-6 animate-spin text-gray-400" /><p className="text-sm text-gray-500">Loading</p></Centered>
          ) : error ? (
            <Centered>
              <FileText className="w-8 h-8 text-gray-300" />
              <p className="text-sm text-gray-600">{error}</p>
              <a href="/upload" className="btn-primary">Upload dataset</a>
            </Centered>
          ) : processing ? (
            <Centered>
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              <p className="text-sm font-medium text-gray-800">Processing {upload.filename}</p>
              <p className="text-xs text-gray-500">
                {upload.status === "saving" ? "Saving tickets" : "Running models: embeddings, clustering, classification, scoring"}. This page refreshes automatically.
              </p>
            </Centered>
          ) : (
            <Content view={view} upload={upload} kpis={kpis} tickets={tickets} changeView={changeView} />
          )}
        </main>
      </div>

      <style jsx global>{`
        .btn-secondary { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: 8px;
          font-size: 12px; font-weight: 500; color: #3f3f46; background: white; border: 1px solid #e4e4e7;
          box-shadow: 0 1px 2px rgb(24 24 27 / 0.04); transition: background .15s, border-color .15s; }
        .btn-secondary:hover { background: #fafafa; border-color: #d4d4d8; }
        .btn-secondary:disabled { opacity: .6; }
        .btn-primary { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 10px;
          font-size: 13px; font-weight: 500; color: white; background: #18181b; }
        .btn-primary:hover { background: #27272a; }
      `}</style>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="h-full min-h-[400px] flex flex-col items-center justify-center gap-3 text-center">{children}</div>;
}

function Content({ view, upload, kpis, tickets, changeView }: {
  view: View; upload: any; kpis: any; tickets: any[]; changeView: (v: string) => void;
}) {
  const id = upload?.id;
  switch (view) {
    case "overview":
      return kpis ? (
        <div className="space-y-5">
          <KpiCards data={kpis} onTabChange={changeView} />
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
            <section className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">Largest automation opportunities</h2>
                  <p className="text-xs text-gray-500 mt-0.5">Ticket themes ranked by automatable volume</p>
                </div>
                <button onClick={() => changeView("clusters")} className="text-xs font-medium text-blue-700 hover:underline">
                  All {kpis?.ml_patterns?.cluster_count} themes
                </button>
              </div>
              <ClusterMap onClusterClick={() => changeView("clusters")} uploadId={id} />
            </section>
            <section className="bg-white border border-gray-200 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-900">Automation status</h2>
              <p className="text-xs text-gray-500 mt-0.5 mb-4">Share of tickets by predicted status</p>
              <AutomationDonut
                alreadyAutomated={kpis?.automation_value?.already_automated_pct ?? 0}
                canAutomate={kpis?.automation_value?.can_automate_pct ?? 0}
              />
            </section>
          </div>
          <TicketTable tickets={tickets} />
        </div>
      ) : null;
    case "tickets": return <TicketIntelligenceTab uploadId={id} />;
    case "automation": return <AutomationOpportunitiesTab uploadId={id} datasetName={upload?.filename} />;
    case "clusters": return <ClustersTab uploadId={id} datasetName={upload?.filename} />;
    case "sla": return <PredictionsRisk uploadId={id} />;
    case "anomalies": return <AnomalyDetection uploadId={id} />;
    case "roi": return <ROICalculator uploadId={id} />;
    case "copilot": return <Copilot uploadId={id} />;
    case "evaluation": return <ModelEvaluation uploadId={id} />;
    case "review": return <ReviewQueue uploadId={id} />;
    case "health": return <CommandCenter uploadId={id} onNavigate={changeView} />;
    case "activity": return <ActivityLog />;
    case "settings": return <SettingsPanel />;
  }
}
