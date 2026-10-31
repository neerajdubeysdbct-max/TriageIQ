"use client";
import { useState, useEffect } from "react";
import { X } from "lucide-react";

interface DrillDownModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  type: string;
  data: any;
}

export default function DrillDownModal({ isOpen, onClose, title, subtitle, type, data }: DrillDownModalProps) {
  if (!isOpen) return null;

  const renderContent = () => {
    switch (type) {
      case "teams_volume":
        return <TeamsVolumeView data={data} />;
      case "teams_mttr":
        return <TeamsMTTRView data={data} />;
      case "teams_automation":
        return <TeamsAutomationView data={data} />;
      case "mttr_breakdown":
        return <MTTRBreakdownView data={data} />;
      case "channels":
        return <ChannelsView data={data} />;
      case "priority":
        return <PriorityView data={data} />;
      case "solutions":
        return <SolutionsView data={data} />;
      case "hours_saved":
        return <HoursSavedView data={data} />;
      case "callers":
        return <CallersView data={data} />;
      case "categories":
        return <CategoriesView data={data} />;
      default:
        return <div>No data available</div>;
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "white",
          borderRadius: 12,
          width: "90%",
          maxWidth: 800,
          maxHeight: "85vh",
          overflow: "hidden",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid #E5E7EB",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#111827" }}>{title}</div>
            {subtitle && <div style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}>{subtitle}</div>}
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: "1px solid #E5E7EB",
              background: "white",
              cursor: "pointer",
              fontSize: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: "20px 24px", maxHeight: "calc(85vh - 80px)", overflowY: "auto" }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}

// ========== TEAMS BY VOLUME VIEW ==========
function TeamsVolumeView({ data }: { data: any }) {
  const teams = data?.team_performance?.top_teams_by_volume || [];
  const total = data?.automation_value?.total_tickets || 1;

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Top 10 assignment groups by ticket volume
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#F9FAFB" }}>
            <th style={{ ...thStyle, textAlign: "left" }}>#</th>
            <th style={{ ...thStyle, textAlign: "left" }}>Team / Assignment Group</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Tickets</th>
            <th style={{ ...thStyle, textAlign: "right" }}>% of Total</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Avg MTTR</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team: any, i: number) => (
            <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
              <td style={{ ...tdStyle, color: "#9CA3AF" }}>{i + 1}</td>
              <td style={{ ...tdStyle, fontWeight: 500 }}>{team.team}</td>
              <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                {team.count.toLocaleString()}
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                <span style={{ 
                  background: "#EFF6FF", 
                  color: "#4F46E5", 
                  padding: "2px 8px", 
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: 600 
                }}>
                  {((team.count / total) * 100).toFixed(1)}%
                </span>
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                <span style={{ 
                  color: team.avg_mttr < 10 ? "#059669" : team.avg_mttr < 50 ? "#D97706" : "#DC2626",
                  fontWeight: 600 
                }}>
                  {team.avg_mttr}h
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== TEAMS MTTR VIEW ==========
function TeamsMTTRView({ data }: { data: any }) {
  const teams = data?.team_performance?.top_teams_by_volume || [];
  const sorted = [...teams].sort((a, b) => a.avg_mttr - b.avg_mttr);
  const avgMttr = data?.operational_efficiency?.avg_mttr_hours || 0;

  return (
    <div>
      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(3, 1fr)", 
        gap: 16, 
        marginBottom: 24 
      }}>
        <SummaryCard 
          label="Overall Avg MTTR" 
          value={`${avgMttr}h`} 
          color="#F59E0B" 
        />
        <SummaryCard 
          label="Best Team MTTR" 
          value={`${sorted[0]?.avg_mttr || 0}h`} 
          subtext={sorted[0]?.team?.slice(0, 20)} 
          color="#10B981" 
        />
        <SummaryCard 
          label="Worst Team MTTR" 
          value={`${sorted[sorted.length - 1]?.avg_mttr || 0}h`} 
          subtext={sorted[sorted.length - 1]?.team?.slice(0, 20)} 
          color="#EF4444" 
        />
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>
        MTTR by Team (Sorted Best → Worst)
      </div>
      
      {sorted.map((team: any, i: number) => {
        const maxMttr = sorted[sorted.length - 1]?.avg_mttr || 100;
        const pct = (team.avg_mttr / maxMttr) * 100;
        const color = team.avg_mttr < 10 ? "#10B981" : team.avg_mttr < 50 ? "#F59E0B" : "#EF4444";
        
        return (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "#374151" }}>{team.team}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color }}>{team.avg_mttr}h</span>
            </div>
            <div style={{ height: 8, background: "#F3F4F6", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ========== TEAMS AUTOMATION VIEW ==========
function TeamsAutomationView({ data }: { data: any }) {
  const teams = data?.team_performance?.team_automation_rates || [];
  const sorted = [...teams].sort((a, b) => b.automation_pct - a.automation_pct);

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Automation rate by assignment group (tickets already automated / total)
      </div>
      
      {sorted.map((team: any, i: number) => {
        const color = team.automation_pct >= 80 ? "#10B981" : team.automation_pct >= 50 ? "#F59E0B" : "#EF4444";
        
        return (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "#374151" }}>{team.team}</span>
              <div>
                <span style={{ fontSize: 11, color: "#6B7280", marginRight: 8 }}>
                  {team.automated.toLocaleString()} / {team.total.toLocaleString()}
                </span>
                <span style={{ 
                  fontSize: 12, 
                  fontWeight: 600, 
                  color,
                  background: `${color}15`,
                  padding: "2px 8px",
                  borderRadius: 4
                }}>
                  {team.automation_pct}%
                </span>
              </div>
            </div>
            <div style={{ height: 8, background: "#F3F4F6", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${team.automation_pct}%`, height: "100%", background: color, borderRadius: 4 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ========== MTTR BREAKDOWN VIEW ==========
function MTTRBreakdownView({ data }: { data: any }) {
  const oe = data?.operational_efficiency || {};
  const m = oe.mttr_by_status;
  const overall = m?.overall?.avg_hours ?? oe.avg_mttr_hours ?? 0;
  const teams = data?.team_performance?.top_teams_by_volume || [];

  return (
    <div>
      {/* Resolution time by automation status (same definition on every page) */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
        <SummaryCard label="All tickets" value={fmtH(m?.overall?.avg_hours ?? oe.avg_mttr_hours)} subtext={m ? `${m.overall.tickets.toLocaleString()} tickets` : undefined} color="#6B7280" />
        <SummaryCard label="Automated" value={fmtH(m?.automated?.avg_hours)} subtext={m ? `${m.automated.tickets.toLocaleString()} tickets` : undefined} color="#4F46E5" />
        <SummaryCard label="Can be automated" value={fmtH(m?.can_automate?.avg_hours)} subtext={m ? `${m.can_automate.tickets.toLocaleString()} tickets` : undefined} color="#4F46E5" />
        <SummaryCard label="Manual only" value={fmtH(m?.manual_only?.avg_hours)} subtext={m ? `${m.manual_only.tickets.toLocaleString()} tickets` : undefined} color="#6B7280" />
      </div>
      <p style={{ fontSize: 12, color: "#6B7280", marginBottom: 24 }}>
        These groups are different kinds of tickets, so the gap between them is a comparison, not a measured saving.
        Human-handled (can be automated + manual only): {fmtH(m?.human_handled?.avg_hours ?? oe.mttr_manual_hours)}.
      </p>

      {/* By Team */}
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>MTTR by Team</div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#F9FAFB" }}>
            <th style={{ ...thStyle, textAlign: "left" }}>Team</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Tickets</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Avg MTTR</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {teams.slice(0, 10).map((team: any, i: number) => (
            <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
              <td style={{ ...tdStyle, fontWeight: 500 }}>{team.team}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{team.count.toLocaleString()}</td>
              <td style={{ ...tdStyle, textAlign: "right", fontWeight: 600 }}>{team.avg_mttr}h</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                {team.avg_mttr <= overall ? (
                  <span style={{ color: "#047857" }}>Faster than average</span>
                ) : team.avg_mttr <= overall * 2 ? (
                  <span style={{ color: "#B45309" }}>Up to 2× average</span>
                ) : (
                  <span style={{ color: "#B91C1C" }}>More than 2× average</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== CHANNELS VIEW ==========
function ChannelsView({ data }: { data: any }) {
  const channels = data?.channel_analysis?.by_channel || [];
  const total = data?.automation_value?.total_tickets || 1;

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Ticket distribution by source channel with automation rates
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#F9FAFB" }}>
            <th style={{ ...thStyle, textAlign: "left" }}>Channel</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Tickets</th>
            <th style={{ ...thStyle, textAlign: "right" }}>% of Total</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Automated</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Auto Rate</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((ch: any, i: number) => (
            <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
              <td style={{ ...tdStyle, fontWeight: 500 }}>
                {ch.channel}
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{ch.count.toLocaleString()}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{((ch.count / total) * 100).toFixed(1)}%</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{ch.automated.toLocaleString()}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                <span style={{ 
                  background: ch.automation_pct >= 80 ? "#ECFDF5" : ch.automation_pct >= 50 ? "#FFFBEB" : "#FEF2F2",
                  color: ch.automation_pct >= 80 ? "#059669" : ch.automation_pct >= 50 ? "#D97706" : "#DC2626",
                  padding: "2px 8px", 
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: 600 
                }}>
                  {ch.automation_pct}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Insight */}
      <div style={{ 
        marginTop: 16, 
        padding: 12, 
        background: "#FEF3C7", 
        borderRadius: 8,
        fontSize: 12,
        color: "#92400E"
      }}>
        {(() => {
          const sizable = channels.filter((c: any) => c.count / total >= 0.05);
          const low = [...sizable].sort((x: any, y: any) => x.automation_pct - y.automation_pct)[0];
          return low ? <>Lowest automation among channels with at least 5% of tickets: <strong>{low.channel}</strong> ({low.automation_pct}% automated, {low.count.toLocaleString()} tickets).</> : null;
        })()}
      </div>
    </div>
  );
}

const fmtH = (h: number | null | undefined) => (h == null ? "—" : h >= 100 ? `${Math.round(h)}h` : `${Number(h).toFixed(1)}h`);

// ========== PRIORITY VIEW ==========
function PriorityView({ data }: { data: any }) {
  const priorities = data?.operational_efficiency?.priority_distribution || [];
  const total = data?.automation_value?.total_tickets || 1;
  const slaRisk = data?.operational_efficiency?.sla_breach_risk_count || 0;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16, marginBottom: 24 }}>
        <SummaryCard 
          label="High Priority (P1/P2)" 
          value={(data?.operational_efficiency?.high_priority_count ?? 0).toLocaleString()} 
          color="#EF4444" 
        />
        <SummaryCard 
          label="SLA Breached (P1 > 4h, P2 > 8h)" 
          value={slaRisk.toLocaleString()} 
          subtext={`${data?.operational_efficiency?.sla_breach_risk_pct}% of P1/P2`}
          color="#DC2626" 
        />
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Priority Distribution</div>
      {priorities.map((p: any, i: number) => {
        const pct = (p.count / total) * 100;
        const color = p.priority.includes("P1") ? "#DC2626" : 
                      p.priority.includes("P2") ? "#F59E0B" : 
                      p.priority.includes("P3") ? "#6366F1" : "#6B7280";
        
        return (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>{p.priority}</span>
              <span style={{ fontSize: 12, color: "#6B7280" }}>
                {p.count.toLocaleString()} ({pct.toFixed(1)}%)
              </span>
            </div>
            <div style={{ height: 10, background: "#F3F4F6", borderRadius: 5, overflow: "hidden" }}>
              <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 5 }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ========== SOLUTIONS VIEW ==========
function SolutionsView({ data }: { data: any }) {
  const solutions = data?.ml_patterns?.solution_distribution || [];
  const total = data?.automation_value?.total_tickets || 1;

  const colors: Record<string, string> = {
    "Self-Service Portal": "#7C3AED",
    "Auto-Remediation": "#10B981",
    "Script/Runbook": "#4F46E5",
    "Automation Tuning": "#F59E0B",
    "RPA": "#8B5CF6",
    "Existing Automation": "#10B981",
    "Manual Process": "#EF4444",
  };

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Recommended automation solutions by ticket volume. Higher % = more tickets can benefit from this solution.
      </div>

      {solutions.map((sol: any, i: number) => {
        const color = colors[sol.solution] || "#6B7280";
        
        return (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>{sol.solution}</span>
              <div>
                <span style={{ fontSize: 12, color: "#6B7280", marginRight: 8 }}>
                  {sol.count.toLocaleString()} tickets
                </span>
                <span style={{ fontSize: 12, fontWeight: 700, color }}>{sol.pct}%</span>
              </div>
            </div>
            <div style={{ height: 12, background: "#F3F4F6", borderRadius: 6, overflow: "hidden" }}>
              <div style={{ width: `${sol.pct}%`, height: "100%", background: color, borderRadius: 6 }} />
            </div>
          </div>
        );
      })}

      {/* ROI Link */}
      <div style={{ 
        marginTop: 20, 
        padding: 12, 
        background: "#EFF6FF", 
        borderRadius: 8,
        fontSize: 12,
        color: "#4338CA"
      }}>
        See the <strong>ROI Calculator</strong> for implementation costs and payback.
      </div>
    </div>
  );
}

// ========== HOURS SAVED VIEW ==========
function HoursSavedView({ data }: { data: any }) {
  const av = data?.automation_value || {};
  const solutions = data?.ml_patterns?.solution_distribution || [];

  // Estimate hours by solution
  const solutionHours = solutions.map((sol: any) => ({
    solution: sol.solution,
    tickets: sol.count,
    hours_monthly: Math.round(sol.count * 0.25),
    savings_monthly: Math.round(sol.count * 0.25 * 850),
  }));

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        <strong>Potential</strong> hours that can be saved if automation is implemented. Based on 15 min avg handling time per ticket.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
        <SummaryCard 
          label="Automatable Tickets" 
          value={av.can_automate?.toLocaleString()} 
          color="#4F46E5" 
        />
        <SummaryCard 
          label="Potential Hours/Month" 
          value={av.hours_saved_monthly?.toLocaleString()} 
          subtext="If fully automated"
          color="#7C3AED" 
        />
        <SummaryCard 
          label="Potential Savings/Year" 
          value={`₹${av.annual_savings_cr} Cr`} 
          subtext="@ ₹850/hr"
          color="#10B981" 
        />
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Breakdown by Solution</div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#F9FAFB" }}>
            <th style={{ ...thStyle, textAlign: "left" }}>Solution</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Tickets</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Hours/Month</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Savings/Month</th>
          </tr>
        </thead>
        <tbody>
          {solutionHours.slice(0, 6).map((sol: any, i: number) => (
            <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
              <td style={{ ...tdStyle, fontWeight: 500 }}>{sol.solution}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{sol.tickets.toLocaleString()}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{sol.hours_monthly.toLocaleString()}</td>
              <td style={{ ...tdStyle, textAlign: "right", color: "#059669", fontWeight: 600 }}>
                ₹{(sol.savings_monthly / 100000).toFixed(1)}L
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ 
        marginTop: 16, 
        padding: 12, 
        background: "#ECFDF5", 
        borderRadius: 8,
        fontSize: 12,
        color: "#065F46"
      }}>
        {av.savings_assumptions ? (
          <>
            <strong>Calculation:</strong> {av.can_automate?.toLocaleString()} automatable tickets ×{" "}
            {av.savings_assumptions.effort_minutes_per_ticket} min ÷ {av.savings_assumptions.months_covered} months ={" "}
            {av.hours_saved_monthly?.toLocaleString()} h/month × ₹{av.savings_assumptions.hourly_cost_inr}/h × 12 = ₹{av.annual_savings_lakhs}L per year
          </>
        ) : null}
      </div>
    </div>
  );
}

// ========== CALLERS VIEW ==========
function CallersView({ data }: { data: any }) {
  const callers = data?.channel_analysis?.top_callers || [];

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Top repeat callers/requesters. These are opportunities for self-service or training.
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#F9FAFB" }}>
            <th style={{ ...thStyle, textAlign: "left" }}>#</th>
            <th style={{ ...thStyle, textAlign: "left" }}>Caller / Requester</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Ticket Count</th>
          </tr>
        </thead>
        <tbody>
          {callers.map((c: any, i: number) => (
            <tr key={i} style={{ borderBottom: "1px solid #F3F4F6" }}>
              <td style={{ ...tdStyle, color: "#9CA3AF" }}>{i + 1}</td>
              <td style={{ ...tdStyle, fontWeight: 500 }}>{c.caller}</td>
              <td style={{ ...tdStyle, textAlign: "right", fontWeight: 600 }}>{c.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ========== CATEGORIES VIEW ==========
function CategoriesView({ data }: { data: any }) {
  const categories = data?.infrastructure?.category_distribution || [];

  return (
    <div>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 16 }}>
        Ticket distribution by L1 category
      </div>
      {categories.map((cat: any, i: number) => (
        <div key={i} style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: "#374151" }}>{cat.category}</span>
            <span style={{ fontSize: 12, color: "#6B7280" }}>
              {cat.count.toLocaleString()} ({cat.pct}%)
            </span>
          </div>
          <div style={{ height: 8, background: "#F3F4F6", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ width: `${cat.pct}%`, height: "100%", background: "#4F46E5", borderRadius: 4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ========== HELPER COMPONENTS ==========
function SummaryCard({ label, value, subtext, color }: { label: string; value: string; subtext?: string; color: string }) {
  return (
    <div style={{ 
      background: `${color}10`, 
      border: `1px solid ${color}30`, 
      borderRadius: 8, 
      padding: 12 
    }}>
      <div style={{ fontSize: 10, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      {subtext && <div style={{ fontSize: 10, color: "#6B7280", marginTop: 2 }}>{subtext}</div>}
    </div>
  );
}


// Styles
const thStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 11,
  fontWeight: 600,
  color: "#6B7280",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: 12,
  color: "#374151",
};