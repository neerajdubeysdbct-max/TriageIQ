"use client";

import React, { useState, useEffect, useMemo } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ─────────────────────────────────────────────────────
interface TicketBreakdown {
  simple: number;
  medium: number;
  complex: number;
  automated: number;
  total: number;
}

interface WasteMetrics {
  avg_reassignments: number;
  avg_reopens: number;
  total_reassignment_waste: number;
  total_reopen_waste: number;
}

// ─── Defaults ──────────────────────────────────────────────────
const DEFAULTS = {
  cost_simple: 500,
  cost_medium: 900,
  cost_complex: 2500,
  cost_automated: 100,
  cost_reassignment: 700,
  cost_reopen: 900,
  post_auto_cost: 120,
  implementation_cost_lakhs: 25,
  automation_target_pct: 40,
};

// ─── Helpers ───────────────────────────────────────────────────
function formatINR(val: number): string {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
  if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
  if (val >= 1000) return `₹${(val / 1000).toFixed(1)}K`;
  return `₹${val.toFixed(0)}`;
}

function formatNum(val: number): string {
  return val.toLocaleString("en-IN");
}

// ─── Slider ────────────────────────────────────────────────────
function ParamSlider({
  label, value, onChange, min, max, step, unit, hint,
}: {
  label: string; value: number; onChange: (v: number) => void;
  min: number; max: number; step: number; unit: string; hint?: string;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="number"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            style={{
              width: 72, background: "#1e293b", border: "1px solid #334155",
              borderRadius: 6, padding: "4px 8px", textAlign: "right",
              fontSize: 13, color: "#4ade80", fontFamily: "monospace",
              outline: "none",
            }}
          />
          <span style={{ fontSize: 11, color: "#64748b", width: 20 }}>{unit}</span>
        </div>
      </div>
      <div style={{ position: "relative", height: 6, background: "#1e293b", borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", borderRadius: 3, width: `${pct}%`,
          background: "linear-gradient(90deg, #059669, #34d399)",
          transition: "width 0.15s ease",
        }} />
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", marginTop: -4, opacity: 0, height: 20, cursor: "pointer", position: "relative", zIndex: 2 }}
      />
      {hint && <p style={{ fontSize: 10, color: "#475569", marginTop: -4 }}>{hint}</p>}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────
export default function ROICalculator({ uploadId }: { uploadId: number }) {
  const [ticketData, setTicketData] = useState<TicketBreakdown | null>(null);
  const [wasteData, setWasteData] = useState<WasteMetrics | null>(null);
  const [annFactor, setAnnFactor] = useState(2.0);
  const [totalTickets, setTotalTickets] = useState(0);
  const [loading, setLoading] = useState(true);

  const [costSimple, setCostSimple] = useState(DEFAULTS.cost_simple);
  const [costMedium, setCostMedium] = useState(DEFAULTS.cost_medium);
  const [costComplex, setCostComplex] = useState(DEFAULTS.cost_complex);
  const [costAutomated, setCostAutomated] = useState(DEFAULTS.cost_automated);
  const [costReassignment, setCostReassignment] = useState(DEFAULTS.cost_reassignment);
  const [costReopen, setCostReopen] = useState(DEFAULTS.cost_reopen);
  const [postAutoCost, setPostAutoCost] = useState(DEFAULTS.post_auto_cost);
  const [implCost, setImplCost] = useState(DEFAULTS.implementation_cost_lakhs);
  const [autoTarget, setAutoTarget] = useState(DEFAULTS.automation_target_pct);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ─── Fetch ───────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${API}/api/roi-calculator/breakdown?upload_id=${uploadId}`, { headers });
        if (res.ok) {
          const d = await res.json();
          if (d.breakdown) {
            setTicketData(d.breakdown);
            setWasteData(d.waste);
            setAnnFactor(d.annualization_factor || 2.0);
            setTotalTickets(d.total_tickets || 0);
          }
        }
      } catch (e) {
        console.error("ROI fetch error", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [uploadId]);

  // ─── Calculate ───────────────────────────────────────────────
  const roi = useMemo(() => {
    if (!ticketData || !wasteData) return null;

    const periodTicketCost =
      ticketData.simple * costSimple +
      ticketData.medium * costMedium +
      ticketData.complex * costComplex +
      ticketData.automated * costAutomated;

    const periodWaste =
      wasteData.total_reassignment_waste * (costReassignment / 700) +
      wasteData.total_reopen_waste * (costReopen / 900);

    const currentAnnual = Math.round((periodTicketCost + periodWaste) * annFactor);

    const nonAuto = ticketData.simple + ticketData.medium + ticketData.complex;
    const toAutomate = Math.round(nonAuto * (autoTarget / 100));
    const remainSimple = Math.max(0, ticketData.simple - Math.round(toAutomate * (ticketData.simple / nonAuto)));
    const remainMedium = Math.max(0, ticketData.medium - Math.round(toAutomate * (ticketData.medium / nonAuto)));
    const remainComplex = Math.max(0, ticketData.complex - Math.round(toAutomate * (ticketData.complex / nonAuto)));

    const postTicketCost =
      remainSimple * costSimple +
      remainMedium * costMedium +
      remainComplex * costComplex +
      (ticketData.automated + toAutomate) * postAutoCost;

    const wasteReduction = (autoTarget / 100) * 0.7;
    const postWaste = periodWaste * (1 - wasteReduction);
    const postAnnual = Math.round((postTicketCost + postWaste) * annFactor);
    const savings = currentAnnual - postAnnual;
    const implINR = implCost * 100000;
    const roiPct = implINR > 0 ? Math.round(((savings - implINR) / implINR) * 100) : 0;
    const payback = savings > 0 ? Math.round((implINR / savings) * 12) : 0;

    return { currentAnnual, postAnnual, savings, roiPct, payback, toAutomate };
  }, [ticketData, wasteData, costSimple, costMedium, costComplex, costAutomated, costReassignment, costReopen, postAutoCost, implCost, autoTarget, annFactor]);

  // ─── Loading ─────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 400, color: "#64748b" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 40, height: 40, border: "3px solid #1e293b", borderTopColor: "#4ade80",
            borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px",
          }} />
          Loading ticket data...
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      </div>
    );
  }

  if (!roi || !ticketData || !wasteData) {
    return (
      <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
        <p style={{ fontSize: 48, marginBottom: 16 }}></p>
        <p>No data available. Ensure the dataset is fully processed.</p>
      </div>
    );
  }

  // ─── Render ──────────────────────────────────────────────────
  return (
    <div style={{ padding: "0 4px", color: "#e2e8f0", fontFamily: "'DM Sans', -apple-system, sans-serif" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 700, color: "#166129", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            ROI Calculator
          </h2>
          <p style={{ fontSize: 14, color: "#64748b", marginTop: 4 }}>
            Adjust parameters to match your cost structure • <span style={{ color: "#4ade80", fontWeight: 600 }}>{formatNum(totalTickets)} tickets</span> from ML analysis
          </p>
        </div>
        <button
          onClick={() => {
            setCostSimple(DEFAULTS.cost_simple); setCostMedium(DEFAULTS.cost_medium);
            setCostComplex(DEFAULTS.cost_complex); setCostAutomated(DEFAULTS.cost_automated);
            setCostReassignment(DEFAULTS.cost_reassignment); setCostReopen(DEFAULTS.cost_reopen);
            setPostAutoCost(DEFAULTS.post_auto_cost); setImplCost(DEFAULTS.implementation_cost_lakhs);
            setAutoTarget(DEFAULTS.automation_target_pct);
          }}
          style={{
            padding: "8px 16px", fontSize: 12, background: "#1e293b", border: "1px solid #334155",
            borderRadius: 8, color: "#94a3b8", cursor: "pointer",
          }}
        >
          ↺ Reset Defaults
        </button>
      </div>

      {/* KPI Row */}
      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Current Annual Cost", val: formatINR(roi.currentAnnual), sub: "Before automation", color: "#f87171", bg: "rgba(239,68,68,0.06)", border: "rgba(239,68,68,0.15)" },
          { label: "Post-Automation Cost", val: formatINR(roi.postAnnual), sub: `After ${autoTarget}% automation`, color: "#60a5fa", bg: "rgba(59,130,246,0.06)", border: "rgba(59,130,246,0.15)" },
          { label: "Annual Savings", val: formatINR(roi.savings), sub: `${roi.roiPct}% ROI`, color: "#4ade80", bg: "rgba(52,211,153,0.08)", border: "rgba(52,211,153,0.18)" },
          { label: "Payback Period", val: `${roi.payback} mo`, sub: `On ₹${implCost}L investment`, color: "#fbbf24", bg: "rgba(251,191,36,0.06)", border: "rgba(251,191,36,0.15)" },
        ].map((c) => (
          <div key={c.label} style={{
            flex: 1, background: c.bg, border: `1px solid ${c.border}`,
            borderRadius: 12, padding: "18px 22px",
          }}>
            <p style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 1.2, fontWeight: 600 }}>{c.label}</p>
            <p style={{ fontSize: 30, fontWeight: 800, color: c.color, fontFamily: "'DM Sans', monospace", lineHeight: 1.1, marginTop: 8 }}>{c.val}</p>
            <p style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>{c.sub}</p>
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "5fr 7fr", gap: 20 }}>
        {/* LEFT: Parameters */}
        <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 14, padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>Cost Parameters</h3>
            <span style={{ fontSize: 9, color: "#475569", background: "#1e293b", padding: "3px 8px", borderRadius: 10, border: "1px solid #334155" }}>
              Industry benchmarks
            </span>
          </div>

          <ParamSlider label="L1 Simple Ticket" value={costSimple} onChange={setCostSimple}
            min={100} max={2000} step={50} unit="₹" hint="No reassignment, quick fix" />
          <ParamSlider label="L2 Medium Ticket" value={costMedium} onChange={setCostMedium}
            min={300} max={3000} step={50} unit="₹" hint="1 reassignment, moderate effort" />
          <ParamSlider label="L3 Complex Ticket" value={costComplex} onChange={setCostComplex}
            min={1000} max={8000} step={100} unit="₹" hint="Multi-team, rework needed" />
          <ParamSlider label="Auto-Resolved" value={costAutomated} onChange={setCostAutomated}
            min={10} max={500} step={10} unit="₹" hint="Self-service / auto-remediation" />

          <div style={{ borderTop: "1px solid #1e293b", paddingTop: 16, marginTop: 8 }}>
            <ParamSlider label="Automation Target" value={autoTarget} onChange={setAutoTarget}
              min={10} max={80} step={5} unit="%" hint="% of manual tickets to automate" />
          </div>

          <button onClick={() => setShowAdvanced(!showAdvanced)}
            style={{ fontSize: 11, color: "#64748b", background: "none", border: "none", cursor: "pointer", padding: 0, marginTop: 4 }}>
            {showAdvanced ? "▾ Hide" : "▸ Show"} advanced parameters
          </button>

          {showAdvanced && (
            <div style={{ borderTop: "1px solid #1e293b", paddingTop: 14, marginTop: 10 }}>
              <ParamSlider label="Reassignment Waste" value={costReassignment} onChange={setCostReassignment}
                min={100} max={2000} step={50} unit="₹" hint="Per bounce between teams" />
              <ParamSlider label="Reopen Waste" value={costReopen} onChange={setCostReopen}
                min={200} max={3000} step={50} unit="₹" hint="Per failed fix cycle" />
              <ParamSlider label="Post-Auto Cost" value={postAutoCost} onChange={setPostAutoCost}
                min={20} max={500} step={10} unit="₹" hint="Per auto ticket (monitoring)" />
              <ParamSlider label="Implementation" value={implCost} onChange={setImplCost}
                min={5} max={200} step={5} unit="₹L" hint="One-time setup cost" />
            </div>
          )}
        </div>

        {/* RIGHT */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Breakdown */}
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 14, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", margin: "0 0 16px" }}>Ticket Complexity</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                { label: "Simple (L1)", count: ticketData.simple, cost: costSimple, color: "#4ade80" },
                { label: "Medium (L2)", count: ticketData.medium, cost: costMedium, color: "#60a5fa" },
                { label: "Complex (L3+)", count: ticketData.complex, cost: costComplex, color: "#fb923c" },
                { label: "Automated", count: ticketData.automated, cost: costAutomated, color: "#c084fc" },
              ].map((r) => {
                const pct = ((r.count / ticketData.total) * 100).toFixed(1);
                return (
                  <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: r.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 13, color: "#94a3b8", width: 110, flexShrink: 0 }}>{r.label}</span>
                    <div style={{ flex: 1, background: "#1e293b", borderRadius: 4, height: 24, overflow: "hidden", position: "relative" }}>
                      <div style={{ height: "100%", borderRadius: 4, width: `${Math.max(Number(pct), 2)}%`, background: r.color, opacity: 0.5 }} />
                      <span style={{ position: "absolute", top: "50%", left: 8, transform: "translateY(-50%)", fontSize: 11, color: "#f8fafc", fontWeight: 600 }}>{pct}%</span>
                    </div>
                    <span style={{ fontSize: 12, color: "#94a3b8", width: 52, textAlign: "right", fontFamily: "monospace" }}>{formatNum(r.count)}</span>
                    <span style={{ fontSize: 12, color: "#64748b", width: 60, textAlign: "right", fontFamily: "monospace" }}>{formatINR(r.count * r.cost)}</span>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 14, display: "flex", borderRadius: 6, overflow: "hidden", height: 8 }}>
              <div style={{ width: `${(ticketData.simple / ticketData.total) * 100}%`, background: "#4ade80" }} />
              <div style={{ width: `${(ticketData.medium / ticketData.total) * 100}%`, background: "#60a5fa" }} />
              <div style={{ width: `${(ticketData.complex / ticketData.total) * 100}%`, background: "#fb923c" }} />
              <div style={{ width: `${(ticketData.automated / ticketData.total) * 100}%`, background: "#c084fc" }} />
            </div>
          </div>

          {/* Waste */}
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 14, padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>Operational Waste</h3>
              <span style={{ fontSize: 9, color: "#f87171", background: "rgba(239,68,68,0.1)", padding: "3px 8px", borderRadius: 10, border: "1px solid rgba(239,68,68,0.2)" }}>
                Hidden costs
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.12)", borderRadius: 10, padding: 16 }}>
                <p style={{ fontSize: 10, color: "#f87171", textTransform: "uppercase", letterSpacing: 1, fontWeight: 600, marginBottom: 6 }}>Reassignment</p>
                <p style={{ fontSize: 22, fontWeight: 800, color: "#f87171", fontFamily: "monospace" }}>
                  {formatINR(wasteData.total_reassignment_waste * (costReassignment / 700) * annFactor)}
                  <span style={{ fontSize: 11, opacity: 0.5 }}>/yr</span>
                </p>
                <p style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>{wasteData.avg_reassignments} avg bounces/ticket</p>
              </div>
              <div style={{ background: "rgba(251,146,60,0.05)", border: "1px solid rgba(251,146,60,0.12)", borderRadius: 10, padding: 16 }}>
                <p style={{ fontSize: 10, color: "#fb923c", textTransform: "uppercase", letterSpacing: 1, fontWeight: 600, marginBottom: 6 }}>Rework</p>
                <p style={{ fontSize: 22, fontWeight: 800, color: "#fb923c", fontFamily: "monospace" }}>
                  {formatINR(wasteData.total_reopen_waste * (costReopen / 900) * annFactor)}
                  <span style={{ fontSize: 11, opacity: 0.5 }}>/yr</span>
                </p>
                <p style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>{wasteData.avg_reopens} avg reopens/ticket</p>
              </div>
            </div>
          </div>

          {/* Impact */}
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 14, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9", margin: "0 0 16px" }}>Automation Impact</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
              {[
                { label: "Tickets Automated", val: formatNum(roi.toAutomate), sub: `${autoTarget}% of manual` },
                { label: "Monthly Savings", val: formatINR(Math.round(roi.savings / 12)), sub: "per month" },
                { label: "Cost Reduction", val: `${roi.currentAnnual > 0 ? Math.round((roi.savings / roi.currentAnnual) * 100) : 0}%`, sub: "annual reduction" },
              ].map((c) => (
                <div key={c.label} style={{ textAlign: "center", padding: 16, background: "#1e293b", borderRadius: 10 }}>
                  <p style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 1 }}>{c.label}</p>
                  <p style={{ fontSize: 26, fontWeight: 800, color: "#4ade80", fontFamily: "monospace", marginTop: 6 }}>{c.val}</p>
                  <p style={{ fontSize: 11, color: "#475569" }}>{c.sub}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Methodology */}
      <div style={{
        marginTop: 20, padding: "12px 18px", background: "rgba(15,23,42,0.5)",
        border: "1px solid #1e293b", borderRadius: 10, fontSize: 11, color: "#475569", lineHeight: 1.6,
      }}>
        <strong style={{ color: "#64748b" }}>Methodology:</strong>{" "}
        Cost Per Ticket model (Gartner, HDI, MetricNet). Complexity from reassignment count, reopen count &amp; resolution time.
        Waste from HappySignals research (440K+ responses). Annualized from {annFactor > 1 ? `${Math.round(365 / annFactor)}-day` : "full-year"} data.
        <span style={{ color: "#4ade80" }}> Adjust sliders to match your rates.</span>
      </div>
    </div>
  );
}