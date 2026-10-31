"use client";
import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

interface Summary {
  total: number;
  already_automated: number;
  already_automated_pct: number;
  can_automate: number;
  can_automate_pct: number;
  manual_only: number;
  manual_only_pct: number;
  by_solution: { solution: string; count: number; monthly_savings_inr: number }[];
  savings: {
    hours_saved_monthly: number;
    monthly_savings_inr: number;
    annual_savings_inr: number;
    assumptions: { effort_minutes_per_ticket: number; hourly_cost_inr: number; months_covered: number };
  };
}

// ₹ amounts in lakhs below 1 crore, crores above
function inr(v: number): string {
  return v >= 10000000 ? `₹${(v / 10000000).toFixed(2)}Cr` : `₹${(v / 100000).toFixed(1)}L`;
}

interface ExecutiveSummaryProps {
  uploadId: number;
  datasetName?: string;
}

const SOLUTION_DETAILS: Record<string, { effort: string; timeline: string; roi_multiplier: number }> = {
  "Self-Service Portal": { effort: "Medium", timeline: "Q2", roi_multiplier: 0.4 },
  "Automation Tuning": { effort: "Low", timeline: "Q1", roi_multiplier: 0.6 },
  "Auto-Remediation": { effort: "Low", timeline: "Q1", roi_multiplier: 0.5 },
  "Existing Automation": { effort: "Done", timeline: "-", roi_multiplier: 0 },
  "Manual Process": { effort: "N/A", timeline: "-", roi_multiplier: 0 },
  "Script/Runbook": { effort: "Low", timeline: "Q1", roi_multiplier: 0.5 },
  "RPA": { effort: "Medium", timeline: "Q2", roi_multiplier: 0.4 },
  "Auto-Close Script": { effort: "Low", timeline: "Q1", roi_multiplier: 0.5 },
  "Self-Healing": { effort: "Done", timeline: "-", roi_multiplier: 0 },
};

export default function ExecutiveSummary({ uploadId, datasetName }: ExecutiveSummaryProps) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!uploadId) return;
    const token = getToken();

    fetch(API + "/api/automation-summary/" + uploadId, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => r.json())
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [uploadId]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400, color: "#6B7280" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}></div>
          <p>Loading executive summary...</p>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  // Calculate metrics
  // Savings come from the backend, normalised by the months the dump covers
  const assumptions = summary.savings.assumptions;
  const monthlyHours = summary.savings.hours_saved_monthly;
  const monthlySavings = summary.savings.monthly_savings_inr;
  const annualSavings = summary.savings.annual_savings_inr;
  const manualReduction = Math.round((summary.can_automate / (summary.can_automate + summary.manual_only)) * 100);

  // Sort solutions by count (excluding existing automation and manual)
  const actionableSolutions = summary.by_solution
    .filter(s => !["Existing Automation", "Manual Process", "Self-Healing"].includes(s.solution))
    .sort((a, b) => b.count - a.count);

  // Quick wins (low effort, high count)
  const quickWins = actionableSolutions
    .filter(s => SOLUTION_DETAILS[s.solution]?.effort === "Low")
    .slice(0, 3);

  // Calculate ROI table
  const roiTable = actionableSolutions.map(sol => {
    const details = SOLUTION_DETAILS[sol.solution] || { effort: "Medium", timeline: "Q2", roi_multiplier: 0.4 };
    const savings = sol.monthly_savings_inr;
    const hours = Math.round(savings / assumptions.hourly_cost_inr);
    return {
      solution: sol.solution,
      tickets: sol.count,
      hours,
      savings,
      effort: details.effort,
      timeline: details.timeline,
    };
  });

  return (
    <div style={{ 
      background: "linear-gradient(135deg, #1E293B 0%, #334155 100%)", 
      borderRadius: 16, 
      padding: 32,
      color: "white",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: 2, marginBottom: 8 }}>
          Executive Summary
        </div>
        <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 4 }}>
          Automation Opportunity Analysis
        </div>
        <div style={{ fontSize: 14, color: "#94A3B8" }}>
          {datasetName || "Dataset"} • {summary.total.toLocaleString()} tickets analyzed
        </div>
      </div>

      {/* Key Metrics Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 32 }}>
        <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 20, textAlign: "center" }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#818CF8" }}>
            {summary.total.toLocaleString()}
          </div>
          <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>Total Tickets</div>
        </div>
        <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 20, textAlign: "center" }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#34D399" }}>
            {summary.can_automate.toLocaleString()}
          </div>
          <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>Can Be Automated</div>
          <div style={{ fontSize: 11, color: "#34D399", marginTop: 2 }}>{summary.can_automate_pct}% of total</div>
        </div>
        <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 20, textAlign: "center" }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#FBBF24" }}>
            {inr(annualSavings)}
          </div>
          <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>Annual Savings</div>
          <div style={{ fontSize: 11, color: "#FBBF24", marginTop: 2 }}>{monthlyHours.toLocaleString()} hrs/month</div>
        </div>
        <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 20, textAlign: "center" }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#A78BFA" }}>
            {manualReduction}%
          </div>
          <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>Manual Reduction</div>
          <div style={{ fontSize: 11, color: "#A78BFA", marginTop: 2 }}>Potential</div>
        </div>
      </div>

      {/* Two Column Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 32 }}>
        {/* Left: Current vs Target State */}
        <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: "#E2E8F0" }}>
            Current State vs Target State
          </div>
          
          {/* Current State */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 8 }}>CURRENT STATE</div>
            <div style={{ display: "flex", gap: 4, height: 32, borderRadius: 6, overflow: "hidden" }}>
              <div style={{ 
                width: `${summary.already_automated_pct}%`, 
                background: "#10B981",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700,
              }}>
                {summary.already_automated_pct}%
              </div>
              <div style={{ 
                width: `${summary.can_automate_pct}%`, 
                background: "#F59E0B",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700, color: "#000",
              }}>
                {summary.can_automate_pct}%
              </div>
              <div style={{ 
                width: `${summary.manual_only_pct}%`, 
                background: "#EF4444",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700,
              }}>
                {summary.manual_only_pct}%
              </div>
            </div>
          </div>

          {/* Target State */}
          <div>
            <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 8 }}>TARGET STATE (After Implementation)</div>
            <div style={{ display: "flex", gap: 4, height: 32, borderRadius: 6, overflow: "hidden" }}>
              <div style={{ 
                width: `${summary.already_automated_pct + summary.can_automate_pct}%`, 
                background: "#10B981",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700,
              }}>
                {(summary.already_automated_pct + summary.can_automate_pct).toFixed(1)}%
              </div>
              <div style={{ 
                width: `${summary.manual_only_pct}%`, 
                background: "#EF4444",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 700,
              }}>
                {summary.manual_only_pct}%
              </div>
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 12, height: 12, background: "#10B981", borderRadius: 2 }} />
              <span style={{ color: "#94A3B8" }}>Automated</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 12, height: 12, background: "#F59E0B", borderRadius: 2 }} />
              <span style={{ color: "#94A3B8" }}>Can Automate</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 12, height: 12, background: "#EF4444", borderRadius: 2 }} />
              <span style={{ color: "#94A3B8" }}>Manual</span>
            </div>
          </div>
        </div>

        {/* Right: Quick Wins */}
        <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: "#E2E8F0" }}>
            Quick Wins (Low Effort, High Impact)
          </div>
          
          {quickWins.map((sol, i) => {
            const details = SOLUTION_DETAILS[sol.solution] || { effort: "Low", timeline: "Q1", roi_multiplier: 0.5 };
            const savings = sol.monthly_savings_inr;
            return (
              <div key={i} style={{ 
                background: "rgba(52, 211, 153, 0.1)", 
                border: "1px solid rgba(52, 211, 153, 0.3)",
                borderRadius: 8, 
                padding: 12, 
                marginBottom: 8 
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#34D399" }}>{sol.solution}</div>
                    <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>
                      {sol.count.toLocaleString()} tickets • {details.timeline}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#FBBF24" }}>
                      ₹{(savings / 100000).toFixed(1)}L/mo
                    </div>
                    <div style={{ fontSize: 10, color: "#94A3B8" }}>Effort: {details.effort}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ROI Table */}
      <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: 20, marginBottom: 32 }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: "#E2E8F0" }}>
          Automation ROI by Solution
        </div>
        
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={{ textAlign: "left", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>#</th>
                <th style={{ textAlign: "left", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Solution</th>
                <th style={{ textAlign: "right", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Tickets</th>
                <th style={{ textAlign: "right", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Hours/Month</th>
                <th style={{ textAlign: "right", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Savings/Month</th>
                <th style={{ textAlign: "center", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Effort</th>
                <th style={{ textAlign: "center", padding: "10px 12px", color: "#94A3B8", fontWeight: 600 }}>Timeline</th>
              </tr>
            </thead>
            <tbody>
              {roiTable.slice(0, 6).map((row, i) => (
                <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ padding: "10px 12px", color: "#64748B" }}>{i + 1}</td>
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "#E2E8F0" }}>{row.solution}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "#818CF8" }}>{row.tickets.toLocaleString()}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "#E2E8F0" }}>{row.hours.toLocaleString()}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "#FBBF24", fontWeight: 600 }}>
                    ₹{(row.savings / 100000).toFixed(1)}L
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "center" }}>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 600,
                      background: row.effort === "Low" ? "rgba(52, 211, 153, 0.2)" : row.effort === "Medium" ? "rgba(251, 191, 36, 0.2)" : "rgba(148, 163, 184, 0.2)",
                      color: row.effort === "Low" ? "#34D399" : row.effort === "Medium" ? "#FBBF24" : "#94A3B8",
                    }}>
                      {row.effort}
                    </span>
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "center", color: "#94A3B8" }}>{row.timeline}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: "2px solid rgba(255,255,255,0.2)" }}>
                <td colSpan={2} style={{ padding: "12px", fontWeight: 700, color: "#E2E8F0" }}>TOTAL OPPORTUNITY</td>
                <td style={{ padding: "12px", textAlign: "right", fontWeight: 700, color: "#818CF8" }}>
                  {summary.can_automate.toLocaleString()}
                </td>
                <td style={{ padding: "12px", textAlign: "right", fontWeight: 700, color: "#E2E8F0" }}>
                  {monthlyHours.toLocaleString()}
                </td>
                <td style={{ padding: "12px", textAlign: "right", fontWeight: 700, color: "#FBBF24" }}>
                  {inr(monthlySavings)}
                </td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Implementation Roadmap */}
      <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: "#E2E8F0" }}>
          Implementation Roadmap
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {["Q1", "Q2", "Q3", "Q4"].map((quarter, qi) => {
            const quarterSolutions = roiTable.filter(r => r.timeline === quarter);
            const quarterTickets = quarterSolutions.reduce((sum, r) => sum + r.tickets, 0);
            const quarterSavings = quarterSolutions.reduce((sum, r) => sum + r.savings, 0);
            
            return (
              <div key={quarter} style={{ 
                background: qi === 0 ? "rgba(52, 211, 153, 0.15)" : "rgba(255,255,255,0.05)",
                border: qi === 0 ? "1px solid rgba(52, 211, 153, 0.3)" : "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8, 
                padding: 16,
                textAlign: "center",
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: qi === 0 ? "#34D399" : "#E2E8F0", marginBottom: 8 }}>
                  {quarter} 2025
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginBottom: 8 }}>
                  {quarterSolutions.map(s => s.solution.split(" ")[0]).join(", ") || "-"}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#FBBF24" }}>
                  {quarterSavings > 0 ? `₹${(quarterSavings / 100000).toFixed(1)}L` : "-"}
                </div>
                <div style={{ fontSize: 10, color: "#94A3B8" }}>
                  {quarterTickets > 0 ? `${quarterTickets.toLocaleString()} tickets` : ""}
                </div>
              </div>
            );
          })}
        </div>

        {/* Cumulative savings note */}
        <div style={{ 
          marginTop: 16, 
          padding: 12, 
          background: "rgba(251, 191, 36, 0.1)", 
          border: "1px solid rgba(251, 191, 36, 0.3)",
          borderRadius: 8,
          textAlign: "center",
        }}>
          <span style={{ color: "#FBBF24", fontWeight: 600 }}>
            Full implementation by Q4 = {inr(annualSavings)} annual savings
          </span>
          <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 6 }}>
            Assumes {assumptions.effort_minutes_per_ticket} min of analyst effort removed per automated ticket at ₹
            {assumptions.hourly_cost_inr}/hr; monthly figures are averaged over the {assumptions.months_covered} months this dump covers.
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ textAlign: "center", marginTop: 24, fontSize: 11, color: "#64748B" }}>
        Generated by TriageIQ • {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
      </div>
    </div>
  );
}