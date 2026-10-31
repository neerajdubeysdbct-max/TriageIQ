"use client";
/**
 * Architecture: how TriageIQ works and why, for presenting to a client, a
 * leadership audience or an interviewer. Arrow keys move between sections;
 * Present switches to full screen. Works without a dataset loaded.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Maximize2, Minimize2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Diagram from "./Diagram";
import { dataflow, deployment, functional, mlops, mlPipeline, rag, security, technical, type DiagramSpec } from "./diagrams";
import Rationale from "./Rationale";

export type SectionId =
  | "summary" | "functional" | "dataflow" | "technical" | "pipeline" | "ml" | "rag" | "mlops"
  | "security" | "deploy" | "rationale" | "industries";

const SECTIONS: { id: SectionId; title: string; group: string; line: string }[] = [
  { id: "summary", group: "Business", title: "Executive summary",
    line: "Every ticket dump becomes an automation roadmap in minutes, with numbers that are measured, explained and kept inside the client's network." },
  { id: "functional", group: "Business", title: "Functional architecture",
    line: "Three kinds of users, five things they do, five things they get back." },
  { id: "dataflow", group: "Architecture", title: "Data flow",
    line: "From raw export to dashboards in twelve stages; every stage stores its result so pages never recompute." },
  { id: "technical", group: "Architecture", title: "Technical architecture",
    line: "One API service, a background pipeline, a model layer, Postgres for everything, and a local LLM." },
  { id: "pipeline", group: "Architecture", title: "Data pipeline in detail",
    line: "What each stage takes in, gives out, how it behaves at scale and what happens when it fails." },
  { id: "ml", group: "Architecture", title: "ML architecture",
    line: "Seven models, each chosen against a baseline, each with its limitation written down." },
  { id: "rag", group: "Architecture", title: "RAG architecture",
    line: "Numbers come from the database, explanations from cited tickets, and nothing unverified is shown." },
  { id: "mlops", group: "Architecture", title: "MLOps and learning loop",
    line: "The model improves on a new customer through labels and a gate, never by training on its own guesses." },
  { id: "security", group: "Architecture", title: "Security and privacy",
    line: "Every request is authenticated, every dataset belongs to one team, and ticket text never leaves the network." },
  { id: "deploy", group: "Architecture", title: "Deployment and scale",
    line: "One command brings up the whole stack; here is what is measured today and what changes at a million tickets." },
  { id: "rationale", group: "Reasoning", title: "Design rationale",
    line: "Fifty decisions, each with the problem, the options compared, the evidence and the trade-off." },
  { id: "industries", group: "Reasoning", title: "Other industries",
    line: "The same architecture works wherever people resolve records: complaints, claims, work orders." },
];

export default function Architecture({ initial = "summary" }: { initial?: SectionId }) {
  const [active, setActive] = useState<SectionId>(initial);
  const [full, setFull] = useState(false);
  const [navHidden, setNavHidden] = useState(false);
  useEffect(() => {
    try { setNavHidden(localStorage.getItem("triageiq.archNavHidden") === "1"); } catch {}
  }, []);
  function toggleNav() {
    const next = !navHidden;
    setNavHidden(next);
    try { localStorage.setItem("triageiq.archNavHidden", next ? "1" : "0"); } catch {}
  }
  const root = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const index = SECTIONS.findIndex((s) => s.id === active);

  const go = useCallback((i: number) => {
    const s = SECTIONS[Math.max(0, Math.min(SECTIONS.length - 1, i))];
    setActive(s.id);
    body.current?.scrollTo({ top: 0 });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); go(index + 1); }
      if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(index - 1); }
    };
    const onFs = () => setFull(!!document.fullscreenElement);
    window.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onFs);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("fullscreenchange", onFs); };
  }, [index, go]);

  function togglePresent() {
    if (document.fullscreenElement) document.exitFullscreen();
    else root.current?.requestFullscreen?.();
  }

  const section = SECTIONS[index];
  const groups = Array.from(new Set(SECTIONS.map((s) => s.group)));

  return (
    <div ref={root} className={`flex gap-5 ${full ? "bg-gray-50 p-6 h-screen" : "min-h-[calc(100vh-8rem)]"}`}>
      {!navHidden && <nav className="w-52 shrink-0 text-sm">
        {groups.map((g) => (
          <div key={g} className="mb-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1 px-2">{g}</div>
            {SECTIONS.filter((s) => s.group === g).map((s) => {
              const n = SECTIONS.indexOf(s) + 1;
              return (
                <button key={s.id} onClick={() => go(n - 1)}
                  className={`w-full text-left px-2 py-1.5 rounded-md flex gap-2 ${active === s.id ? "bg-blue-50 text-blue-800 font-medium" : "text-gray-700 hover:bg-gray-100"}`}>
                  <span className="w-4 text-right tabular-nums text-gray-400">{n}</span>{s.title}
                </button>
              );
            })}
          </div>
        ))}
        <p className="px-2 text-[11px] text-gray-400 leading-relaxed">Use the arrow keys to move between sections.</p>
      </nav>}

      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="text-xs text-gray-500">{index + 1} / {SECTIONS.length} · {section.group}</div>
            <h2 className="text-xl font-semibold text-gray-900">{section.title}</h2>
            <p className="text-sm text-gray-600 mt-1 max-w-3xl">{section.line}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={toggleNav} className="mr-1 inline-flex items-center gap-1.5 px-2.5 py-2 rounded-md border border-gray-200 bg-white text-xs text-gray-700"
              title={navHidden ? "Show the section list" : "Hide the section list"}>
              {navHidden ? <PanelLeftOpen className="w-3.5 h-3.5" /> : <PanelLeftClose className="w-3.5 h-3.5" />}Sections
            </button>
            <button onClick={() => go(index - 1)} disabled={index === 0} className="p-2 rounded-md border border-gray-200 bg-white disabled:opacity-40" title="Previous (left arrow)"><ChevronLeft className="w-4 h-4" /></button>
            <button onClick={() => go(index + 1)} disabled={index === SECTIONS.length - 1} className="p-2 rounded-md border border-gray-200 bg-white disabled:opacity-40" title="Next (right arrow)"><ChevronRight className="w-4 h-4" /></button>
            <button onClick={togglePresent} className="ml-1 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-gray-900 text-white text-xs font-medium hover:bg-gray-800">
              {full ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}{full ? "Exit" : "Present"}
            </button>
          </div>
        </div>
        <div ref={body} className={`flex-1 ${full ? "overflow-y-auto pr-2" : ""}`}>
          <SectionBody id={active} />
        </div>
      </div>
    </div>
  );
}

function SectionBody({ id }: { id: SectionId }) {
  switch (id) {
    case "summary": return <Summary />;
    case "functional": return <D spec={functional} />;
    case "dataflow": return <><D spec={dataflow} /><Note>Press Play to walk through the stages; select any box for the technology, the reason and the measured numbers.</Note></>;
    case "technical": return <D spec={technical} />;
    case "pipeline": return <Pipeline />;
    case "ml": return <ML />;
    case "rag": return <Rag />;
    case "mlops": return <Mlops />;
    case "security": return <Security />;
    case "deploy": return <Deploy />;
    case "rationale": return <Rationale />;
    case "industries": return <Industries />;
  }
}

const D = ({ spec }: { spec: DiagramSpec }) => <Diagram {...spec} />;

// ---------------------------------------------------------------- building blocks

function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`bg-white border border-gray-200 rounded-lg p-4 ${className}`}>
      {title && <h3 className="text-sm font-semibold text-gray-900 mb-2">{title}</h3>}
      <div className="text-sm text-gray-700 leading-relaxed">{children}</div>
    </section>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-gray-500 mt-3">{children}</p>;
}

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500">
          <tr>{head.map((h) => <th key={h} className="text-left font-medium px-3 py-2 whitespace-nowrap">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-gray-100 align-top">
          {rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={`px-3 py-2 ${j === 0 ? "font-medium text-gray-900 whitespace-nowrap" : "text-gray-700"}`}>{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ value, label, base }: { value: string; label: string; base?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="text-2xl font-semibold text-gray-900 tabular-nums">{value}</div>
      <div className="text-sm text-gray-700 mt-0.5">{label}</div>
      {base && <div className="text-xs text-gray-500 mt-1">{base}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- 1. executive summary

function Summary() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="The problem">
          <ul className="list-disc pl-4 space-y-1">
            <li>Service desks resolve millions of tickets; a large share is repetitive work that could be automated.</li>
            <li>Finding it means analysts reading ticket dumps for days, so proposal estimates are often guesswork.</li>
            <li>Client ticket data contains names, hosts and incidents; it cannot be sent to cloud AI services.</li>
          </ul>
        </Card>
        <Card title="What TriageIQ does">
          <ul className="list-disc pl-4 space-y-1">
            <li>Reads any ServiceNow-style export and recognises what it contains.</li>
            <li>Classifies every ticket as already automated, automatable or manual, with a calibrated score.</li>
            <li>Finds themes, anomalies, SLA risk and future volume.</li>
            <li>Answers questions in plain English with cited evidence.</li>
          </ul>
        </Card>
        <Card title="Why it is different">
          <ul className="list-disc pl-4 space-y-1">
            <li><b>Measured:</b> every model is compared with a baseline on held-out data.</li>
            <li><b>Private:</b> the language model runs inside the network.</li>
            <li><b>Adapts:</b> labels from analysts improve it per client, behind a quality gate.</li>
            <li><b>Explained:</b> scores come with reasons and stated assumptions.</li>
          </ul>
        </Card>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        <Stat value="95.0%" label="Automation status accuracy" base="bot-resolver rule: 70.2%" />
        <Stat value="93.7%" label="Ticket routing (tower)" base="ticket's own field: 70.3%" />
        <Stat value="0.75" label="Anomaly precision (AP)" base="previous rules: 0.32" />
        <Stat value="73 → 93%" label="New client, 300 labels" base="drift detected first" />
        <Stat value="100%" label="Copilot numeric answers" base="previous copilot: 53%" />
        <Stat value="0" label="Ticket text sent outside" base="local Qwen 2.5 7B" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="How value is calculated">
          <p>Each automatable ticket removes about <b>15 minutes</b> of analyst effort, valued at <b>₹850 per hour</b>, averaged over
            the months the dump covers. The same rule is used on every page and the assumptions are shown next to every figure.</p>
          <p className="mt-2 text-gray-600"><i>Illustration, not a measured result:</i> a client with 1,000,000 tickets a year of which 40% are
            automatable: 400,000 × 15 minutes = 100,000 analyst hours, about <b>₹8.5 crore a year</b>.</p>
        </Card>
        <Card title="Status and next steps">
          <ul className="list-disc pl-4 space-y-1">
            <li>Validated end to end on synthetic data with ground truth; reproducible from a clean Docker install.</li>
            <li>Tested on a real 37,809-ticket dump: drift was significant, so a labelled sample comes before trusting predictions there.</li>
            <li>Next: a 1-million-ticket scale test, a causal estimate of automation's effect on resolution time, a fine-tuned model comparison.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 5. pipeline table

function Pipeline() {
  return (
    <div className="space-y-4">
      <Table head={["Stage", "Input → output", "Technology", "At scale", "On failure"]} rows={[
        ["1 Upload", "File → stored file, upload record", "FastAPI, background task", "Returns immediately; dashboard polls status", "Error shown to the user"],
        ["2 Detect type", "Rows → type, mix, evidence", "Ticket-number prefixes over every row + type-specific columns", "Vectorised pandas", "Reported as 'unknown'; processing continues"],
        ["3 Map and clean", "Customer columns → one schema", "Column map, ISO / day-first date parsing, priority patterns", "Vectorised pandas", "Unparseable dates become empty and are left out of MTTR"],
        ["4 Save", "Rows → tickets table", "SQLAlchemy, chunks of 5,000", "Flat memory per chunk", "Logged; rows saved so far are counted"],
        ["5 Embed and cluster", "Text → 384-d vectors → theme, map position", "MiniLM, KMeans (k 10-30 by silhouette), t-SNE on 5,000", "Up to 100,000 tickets embedded; above that only a sample gets themes (fix planned)", "Upload marked failed"],
        ["6 Taxonomy", "Tickets → tower, category, summary", "Local LLM labels 5 sample tickets per cluster, label copied to the whole cluster; rules as fallback", "Per cluster, not per ticket", "Skipped with a log; upload continues"],
        ["7 Category model", "Creation-time text → L1/L2 + confidence", "Logistic regression, TF-IDF words and characters", "Linear, fast", "Skipped with a log"],
        ["8 Automation model", "Features → status, score, lever", "XGBoost + isotonic calibration; SHAP on 1,000", "Batched scoring", "No model: heuristic labels, clearly marked"],
        ["9 Drift check", "Features → drift report", "PSI, known-word share, unseen values, unsure rate", "Per upload", "Report missing; dashboard says so"],
        ["10 Search index", "Description + closure notes → vectors", "MiniLM; numpy or pgvector HNSW", "37,809 tickets in 284 s on CPU", "Skipped; copilot offers to build it"],
        ["11 Surrogate", "Classifier decisions → operational explanation", "XGBoost on operational fields only (no text), trained to imitate the classifier; SHAP", "Per upload", "Non-critical; skipped"],
        ["12 Status", "→ completed or failed", "", "", "Any uncaught error marks the upload failed, never falsely completed"],
      ]} />
      <Card title="Design rules">
        <ul className="list-disc pl-4 space-y-1">
          <li><b>Compute once, read many times:</b> every stage stores its output; dashboards only read.</li>
          <li><b>Fail honestly:</b> an earlier version marked uploads 'completed' after a crash; now they are marked failed.</li>
          <li><b>One definition per metric:</b> MTTR, SLA breach and savings each come from one shared function; tests check pages agree.</li>
          <li><b>Content over metadata:</b> dump type, priority and dates are read from the data, not from file names or assumptions.</li>
        </ul>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- 6. ML

const MODELS = [
  ["Automation status", "XGBoost on TF-IDF + fields, isotonic calibration", "95.0% acc, macro F1 0.950", "rule 70.2% / F1 0.575; logistic regression F1 0.949", "Logistic regression matches it on this data; validated on synthetic data only"],
  ["Category routing", "Logistic regression, word + character n-grams, creation-time only", "L1 93.7%, L2 92.0%", "ticket's own field 70.3% / 76.3%", "Confuses account unlock vs password reset ('unable to login')"],
  ["Ticket themes", "MiniLM embeddings + KMeans, k by silhouette", "ARI ≈ 0.5 vs true subcategories", "HDBSCAN ARI 0.25", "No label-free criterion picks the 'true' k on templated text"],
  ["Anomalies", "IsolationForest on features relative to ticket type", "Average precision 0.75 (unseen dump)", "previous rules 0.32; global z-score 0.26", "Live: precision 60%, recall 73% at a 2.5% base rate"],
  ["Volume forecast", "Weekday mean, chosen by rolling-origin backtest", "MAE 2.34 tickets/day (unseen)", "seasonal naive 3.18; LSTM 2.31", "LSTM within noise, so the simpler model is kept (3% rule)"],
  ["X-Ray surrogate", "XGBoost on operational fields (time, reassignments, timing), trained on the classifier's decisions", "Fidelity 94.3%", "", "Explains the classifier's behaviour, not the ground truth"],
  ["Copilot", "Qwen 2.5 7B + whitelisted tool + hybrid retrieval + verifier", "15/15 numeric answers; P@8 0.953", "previous copilot 53%", "36-question set written by the author: a regression suite"],
];

function ML() {
  return (
    <div className="space-y-4">
      <Table head={["Model", "Approach", "Result", "Baseline", "Limitation"]} rows={MODELS} />
      <h3 className="text-sm font-semibold text-gray-900 pt-2">Automation classifier, feature to prediction</h3>
      <D spec={mlPipeline} />
      <Card title="Evaluation protocol used for every model">
        Stratified train / validation / test split, test scored once; at least one simple baseline and one rule baseline on the same split;
        cross-validation for variance; then an end-to-end check through the app on a dump the model has never seen. Numbers live in
        docs/MODEL_CARD.md and are reproduced by CI on every push.
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- 7. RAG

function Rag() {
  return (
    <div className="space-y-4">
      <D spec={rag} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Evaluation (3 runs)">
          <ul className="space-y-1">
            <li>Numeric questions: <b>15/15</b> (previous copilot 53%)</li>
            <li>Out-of-scope questions declined: <b>100%</b></li>
            <li>Invalid citations: <b>0%</b>; unsupported numbers after verification: <b>0%</b></li>
            <li>Retrieval precision@8: vector 0.906, keyword 0.867, <b>hybrid 0.953</b></li>
            <li>Latency p50 about 6 s (two local LLM calls); retrieval under 0.2 s</li>
          </ul>
        </Card>
        <Card title="Why not plain RAG">
          A question like 'what is MTTR' is about all 37,000 tickets, not the 8 that retrieval returns, and language models count and
          average badly. So numbers come from a database tool and retrieval is used only for explanations and examples.
        </Card>
        <Card title="A failure that shaped the design">
          Asked just 'MTTR', the first version answered 22.62 hours from 7 sample tickets: the planner returned empty filters, the plan
          was rejected, search took over, and the verifier only warned. Now: tolerant validation, a glossary, one repair attempt, entity
          linking in code and fail closed. The question is a regression test.
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 8. MLOps

function Mlops() {
  return (
    <div className="space-y-4">
      <D spec={mlops} />
      <Table head={["Rule", "Value", "Reason"]} rows={[
        ["Minimum gain to promote", "+0.005 macro F1 (+0.01 on analyst gold)", "Smaller differences are within noise"],
        ["Maximum loss on the base customer", "0.01 macro F1", "Improving one client must not break another"],
        ["Analyst gold labels needed", "30", "Fewer gives too wide an interval to judge"],
        ["Gold set assignment", "1 in 5 random-sample labels, by hash of ticket id", "Stable and never trained on"],
        ["Training data", "Base data + analyst labels only", "No pseudo-labels: no feedback loop"],
        ["Drift: PSI", "0.1 moderate, 0.25 significant", "Industry convention for distribution shift"],
        ["Drift: unseen teams/categories", "Warn above 30% of tickets", "The model has never seen how those teams work"],
      ]} />
    </div>
  );
}

// ---------------------------------------------------------------- 9. security

function Security() {
  return (
    <div className="space-y-4">
      <D spec={security} />
      <Table head={["Control", "How", "Verified by"]} rows={[
        ["Authentication", "bcrypt passwords; signed JWT (HS256, 24 h); key from environment", "Tests: missing and forged tokens rejected"],
        ["Team isolation", "Ownership check on every endpoint with an upload id; 404 for other teams", "Tests on 6 endpoints, each with an allowed case"],
        ["Privileged actions", "Admin role read from the database for retraining, activation, account creation", "Tests: non-admin gets 403"],
        ["Account creation", "Admin-only (public signup accepted any team id: fixed)", "Regression test"],
        ["Downloads", "Authenticated; file name cannot leave the export folder", "Tests with path-traversal names"],
        ["Copilot data tool", "Whitelisted metrics and dimensions, bound parameters; no generated SQL", "Validation tests"],
        ["Prompt injection", "Ticket text passed as quoted data; no write tools; output verified", "Planted-ticket test planned"],
        ["Data residency", "Local LLM; uploads, outputs and models excluded from the repository", "Repository scan before every push"],
      ]} />
    </div>
  );
}

// ---------------------------------------------------------------- 10. deployment and scale

function Deploy() {
  return (
    <div className="space-y-4">
      <D spec={deployment} />
      <Table head={["Concern", "Today (measured)", "At 1M+ tickets (plan)"]} rows={[
        ["Pipeline execution", "Background task inside the API process", "Job queue with separate workers, retries and progress per stage"],
        ["Ingestion", "Whole file read with pandas, written in chunks of 5,000", "Stream the file in chunks"],
        ["Embeddings", "CPU; 37,809 tickets in 284 s", "GPU batches; embed only new tickets"],
        ["Clustering", "Up to 100,000 tickets; above that only a sample gets themes", "Mini-batch KMeans and nearest-centroid assignment for every ticket"],
        ["Vector search", "Exact 0.24 ms vs pgvector HNSW 4.4 ms at 1,500 tickets", "pgvector HNSW; recall and latency re-measured at 1M"],
        ["Dashboards", "SQL aggregates per request", "Precomputed summary tables per upload"],
        ["Copilot", "One Ollama server, about 6 s per question", "GPU server, streamed answers, fast path for simple metrics"],
        ["End-to-end time", "7 minutes for 1,500 tickets in Docker on CPU", "Target set after the 1M measurement"],
      ]} />
      <Note>The 1-million-ticket test has not been run yet: the right-hand column is the plan, not a result.</Note>
    </div>
  );
}

// ---------------------------------------------------------------- 12. industries

const INDUSTRIES: [string, string, string, string][] = [
  ["Banking and financial services", "Customer complaints, card disputes, ATM and branch incidents", "Standard disputes and refunds resolved without an agent",
    "Regulatory turnaround times replace SLAs; account numbers masked like names; every model decision kept for audit"],
  ["Telecom", "Network trouble tickets, alarms, customer faults", "Alarm auto-remediation; self-service for common faults",
    "Alarm storms make volume spiky, so anomaly detection and forecasting matter most; tower or site becomes a dimension"],
  ["Healthcare", "IT service desk, patient service requests, device faults", "Password resets, scheduling and record requests",
    "Patient data makes the local LLM mandatory; compliance with health-data and India's DPDP rules"],
  ["E-commerce and retail", "Customer support: refunds, delivery, payments", "Rule-based refunds and chatbot deflection",
    "Sale events drive seasonality in the forecast; customer sentiment becomes a feature"],
  ["Insurance", "Claims and policy service requests", "Straight-through processing of simple claims",
    "Fraud signals feed the anomaly model; claim documents become an extra retrieval source"],
  ["Manufacturing and utilities", "Maintenance work orders, IoT alerts", "Auto-dispatch and predictive maintenance",
    "Asset and sensor ids become dimensions; forecasting drives spare-part planning"],
  ["HR and shared services", "Employee queries, onboarding and access requests", "Self-service answers and automated access workflows",
    "Policy documents and knowledge articles join the copilot's retrieval"],
];

function Industries() {
  return (
    <div className="space-y-4">
      <Table head={["Industry", "Records", "'Can be automated' means", "What changes"]} rows={INDUSTRIES.map((r) => [...r])} />
      <Card title="What stays the same everywhere">
        <ol className="list-decimal pl-4 space-y-1">
          <li>Ingestion with content-based type detection; only the column map is new.</li>
          <li>The status classifier, relabelled for the domain's notion of automation.</li>
          <li>The learning loop: drift check, labelled sample, gated retraining per client.</li>
          <li>The copilot: same planner, tools and verifier over the domain's records and knowledge base.</li>
          <li>Security model: team isolation, local LLM, no generated SQL.</li>
        </ol>
      </Card>
    </div>
  );
}
