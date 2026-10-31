"use client";
import { useState, useEffect, useCallback } from "react";
import ExecutiveSummary from "./ExecutiveSummary";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
  "Already Automated": { color: "#10B981", bg: "#ECFDF5", icon: "✓" },
  "Can Be Automated": { color: "#4F46E5", bg: "#EFF6FF", icon: "" },
  "Manual Only": { color: "#EF4444", bg: "#FEF2F2", icon: "" },
};

const SOLUTION_CONFIG: Record<string, { color: string; icon: string }> = {
  "Self-Service Portal": { color: "#7C3AED", icon: "" },
  "Automation Tuning": { color: "#F59E0B", icon: "" },
  "Auto-Remediation": { color: "#10B981", icon: "" },
  "Existing Automation": { color: "#10B981", icon: "✓" },
  "Manual Process": { color: "#EF4444", icon: "" },
  "Script/Runbook": { color: "#4F46E5", icon: "" },
  "RPA": { color: "#8B5CF6", icon: "" },
  "Auto-Close Script": { color: "#06B6D4", icon: "" },
  "Self-Healing": { color: "#10B981", icon: "" },
  "Ignio Auto-Remediation": { color: "#10B981", icon: "" },
  "Monitoring Rule": { color: "#F59E0B", icon: "" },
};

interface TicketRow {
  id: string;
  short_description: string;
  assignment_group: string;
  l1_category: string;
  l2_subcategory: string;
  aiops_automation_status: string;
  aiops_solution_lever: string;
  aiops_keywords: string;
  aiops_additional_info?: string;
  resolved_by: string;
  mttr_hours: number;
  automation_potential_score: number;
}

interface Summary {
  total: number;
  already_automated: number;
  already_automated_pct: number;
  can_automate: number;
  can_automate_pct: number;
  manual_only: number;
  manual_only_pct: number;
  by_solution: { solution: string; count: number }[];
}

interface Domain {
  name: string;
  count: number;
}

interface AutomationOpportunitiesTabProps {
  uploadId: number;
  datasetName?: string;
}

export default function AutomationOpportunitiesTab({ uploadId, datasetName }: AutomationOpportunitiesTabProps) {
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [filter, setFilter] = useState<string>("Can Be Automated");
  const [solutionFilter, setSolutionFilter] = useState<string>("All");
  const [domainFilter, setDomainFilter] = useState<string>("All");
  const [page, setPage] = useState(1);
  const [totalFiltered, setTotalFiltered] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showExecutive, setShowExecutive] = useState(false);
  const pageSize = 20;

  // Fetch tickets with filters from API
  const fetchTickets = useCallback(async (status: string, solution: string, domain: string, pageNum: number) => {
    if (!uploadId) return;
    setTicketsLoading(true);
    const token = getToken();
    
    const params = new URLSearchParams();
    if (status && status !== "All") params.append("status", status);
    if (solution && solution !== "All") params.append("solution", solution);
    if (domain && domain !== "All") params.append("domain", domain);
    params.append("skip", String((pageNum - 1) * pageSize));
    params.append("limit", String(pageSize));
    
    try {
      const response = await fetch(
        `${API}/api/automation-opportunities/${uploadId}?${params.toString()}`,
        { headers: { Authorization: "Bearer " + token } }
      );
      const data = await response.json();
      setTickets(data.tickets || []);
      setTotalFiltered(data.total || 0);
      if (data.domains) {
        setDomains(data.domains.filter((d: Domain) => d.name && d.name !== "Automated" && d.name !== "None"));
      }
    } catch (error) {
      console.error("Error fetching tickets:", error);
    } finally {
      setTicketsLoading(false);
    }
  }, [uploadId]);

  // Initial load - fetch summary
  useEffect(() => {
    if (!uploadId) return;
    const token = getToken();

    // Fetch summary
    fetch(API + "/api/automation-summary/" + uploadId, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => r.json())
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    // Fetch initial tickets
    fetchTickets("Can Be Automated", "All", "All", 1);
  }, [uploadId, fetchTickets]);

  // Fetch tickets when filters change
  useEffect(() => {
    fetchTickets(filter, solutionFilter, domainFilter, page);
  }, [filter, solutionFilter, domainFilter, page, fetchTickets]);

  const totalPages = Math.ceil(totalFiltered / pageSize);

  // Get count for filter button
  const getFilterCount = (status: string): number => {
    if (!summary) return 0;
    switch (status) {
      case "All": return summary.total;
      case "Can Be Automated": return summary.can_automate;
      case "Manual Only": return summary.manual_only;
      case "Already Automated": return summary.already_automated;
      default: return 0;
    }
  };

  // Handle filter changes
  const handleStatusFilter = (status: string) => {
    setFilter(status);
    setSolutionFilter("All");
    setPage(1);
  };

  const handleSolutionFilter = (solution: string) => {
    setSolutionFilter(solution);
    setFilter("All"); // Show all statuses when filtering by solution
    setPage(1);
  };

  const handleDomainFilter = (domain: string) => {
    setDomainFilter(domain);
    setPage(1);
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: "#6B7280" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}></div>
          <p>Loading automation opportunities...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* View Toggle */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={() => setShowExecutive(!showExecutive)}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            border: "none",
            background: showExecutive ? "#1E293B" : "linear-gradient(135deg, #1E293B 0%, #334155 100%)",
            color: "white",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "all 0.2s",
          }}
        >
          {showExecutive ? "Show Details" : "Executive Summary"}
        </button>
      </div>

      {/* Executive Summary View */}
      {showExecutive ? (
        <ExecutiveSummary uploadId={uploadId} datasetName={datasetName} />
      ) : (
        <>
      {/* Summary KPIs */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px", borderTop: "3px solid #10B981" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 16 }}>✓</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: 0.5 }}>Already Automated</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#111827", fontFamily: "'JetBrains Mono', monospace" }}>
              {summary.already_automated.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: "#10B981", marginTop: 2 }}>{summary.already_automated_pct}% of total</div>
          </div>

          <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px", borderTop: "3px solid #4F46E5" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 16 }}></span>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: 0.5 }}>Can Be Automated</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#111827", fontFamily: "'JetBrains Mono', monospace" }}>
              {summary.can_automate.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>Actionable opportunities</div>
          </div>

          <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px", borderTop: "3px solid #EF4444" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 16 }}></span>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: 0.5 }}>Manual Only</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#111827", fontFamily: "'JetBrains Mono', monospace" }}>
              {summary.manual_only.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>Requires human judgment</div>
          </div>

          <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px", borderTop: "3px solid #F59E0B" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 16 }}></span>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: 0.5 }}>Est. Monthly Savings</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#111827", fontFamily: "'JetBrains Mono', monospace" }}>
              ₹{((summary.can_automate * 0.5 * 850) / 100000).toFixed(1)}L
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>{(summary.can_automate * 0.5).toLocaleString()} hours @ ₹850/hr</div>
          </div>
        </div>
      )}

      {/* Solution Breakdown - CLICKABLE */}
      {summary?.by_solution && summary.by_solution.length > 0 && (
        <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 12 }}>
            Solution Recommendations
            {solutionFilter !== "All" && (
              <button
                onClick={() => setSolutionFilter("All")}
                style={{
                  marginLeft: 12,
                  padding: "2px 8px",
                  fontSize: 10,
                  background: "#FEF2F2",
                  color: "#EF4444",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                }}
              >
                Clear filter ✕
              </button>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {summary.by_solution.map((sol, i) => {
              const config = SOLUTION_CONFIG[sol.solution] || { color: "#6B7280", icon: "" };
              const isActive = solutionFilter === sol.solution;
              return (
                <div
                  key={i}
                  onClick={() => handleSolutionFilter(isActive ? "All" : sol.solution)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 14px",
                    background: isActive ? config.color + "20" : config.color + "10",
                    border: isActive ? "2px solid " + config.color : "1px solid " + config.color + "30",
                    borderRadius: 8,
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  <span style={{ fontSize: 16 }}>{config.icon}</span>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: config.color }}>{sol.solution}</div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: "#111827" }}>{sol.count.toLocaleString()}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6 }}>
          {["All", "Can Be Automated", "Manual Only", "Already Automated"].map((status) => {
            const config = STATUS_CONFIG[status] || { color: "#6B7280", bg: "#F3F4F6" };
            const isActive = filter === status && solutionFilter === "All";
            const count = getFilterCount(status);
            return (
              <button
                key={status}
                onClick={() => handleStatusFilter(status)}
                style={{
                  padding: "6px 14px",
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: isActive ? "2px solid" : "1px solid",
                  borderColor: isActive ? config.color : "#E5E7EB",
                  background: isActive ? config.bg : "white",
                  color: isActive ? config.color : "#6B7280",
                  transition: "all 0.15s",
                }}
              >
                {status === "All" ? "All" : status.replace("Can Be ", "").replace(" Only", "")}
                <span style={{ opacity: 0.7, marginLeft: 6 }}>{count.toLocaleString()}</span>
              </button>
            );
          })}
        </div>

        {/* Dynamic Domain Filters */}
        <div style={{ display: "flex", gap: 6, marginLeft: "auto", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#9CA3AF" }}>Domain:</span>
          <button
            onClick={() => handleDomainFilter("All")}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              border: domainFilter === "All" ? "2px solid #4F46E5" : "1px solid #E5E7EB",
              background: domainFilter === "All" ? "#EFF6FF" : "white",
              color: domainFilter === "All" ? "#4F46E5" : "#6B7280",
            }}
          >
            All
          </button>
          {domains.slice(0, 6).map((domain) => (
            <button
              key={domain.name}
              onClick={() => handleDomainFilter(domain.name)}
              style={{
                padding: "4px 10px",
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                border: domainFilter === domain.name ? "2px solid #4F46E5" : "1px solid #E5E7EB",
                background: domainFilter === domain.name ? "#EFF6FF" : "white",
                color: domainFilter === domain.name ? "#4F46E5" : "#6B7280",
              }}
              title={`${domain.count.toLocaleString()} tickets`}
            >
              {domain.name}
            </button>
          ))}
        </div>
      </div>

      {/* Active Filters Info */}
      <div style={{ fontSize: 11, color: "#9CA3AF", background: "#F9FAFB", padding: "8px 12px", borderRadius: 6, display: "flex", alignItems: "center", gap: 8 }}>
        <span>ℹ</span>
        <span>
          Showing {totalFiltered.toLocaleString()} tickets
          {filter !== "All" && ` with status "${filter}"`}
          {solutionFilter !== "All" && ` with solution "${solutionFilter}"`}
          {domainFilter !== "All" && ` in domain "${domainFilter}"`}
        </span>
        {ticketsLoading && <span style={{ marginLeft: 8 }}>Loading...</span>}
      </div>

      {/* Tickets Table */}
      <div style={{ background: "white", border: "1px solid #E5E7EB", borderRadius: 10, overflow: "hidden", opacity: ticketsLoading ? 0.6 : 1, transition: "opacity 0.2s" }}>
        {/* Header */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "100px 1fr 140px 140px 120px 80px",
            gap: 8,
            padding: "10px 14px",
            background: "#F9FAFB",
            borderBottom: "1px solid #E5E7EB",
            fontSize: 10,
            fontWeight: 700,
            color: "#6B7280",
            textTransform: "uppercase",
            letterSpacing: 0.5,
          }}
        >
          <div>Ticket #</div>
          <div>Description</div>
          <div>Category</div>
          <div>Status</div>
          <div>Solution</div>
          <div>Score</div>
        </div>

        {/* Rows */}
        {tickets.map((ticket) => {
          const statusConfig = STATUS_CONFIG[ticket.aiops_automation_status] || { color: "#6B7280", bg: "#F3F4F6", icon: "?" };
          const solutionConfig = SOLUTION_CONFIG[ticket.aiops_solution_lever] || { color: "#6B7280", icon: "" };
          const isExpanded = expanded === ticket.id;

          return (
            <div key={ticket.id}>
              <div
                onClick={() => setExpanded(isExpanded ? null : ticket.id)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "100px 1fr 140px 140px 120px 80px",
                  gap: 8,
                  padding: "10px 14px",
                  borderBottom: "1px solid #F3F4F6",
                  fontSize: 12,
                  color: "#374151",
                  cursor: "pointer",
                  background: isExpanded ? "#FAFBFC" : "white",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#4F46E5" }}>
                  {ticket.id?.slice(0, 12)}
                </div>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {ticket.short_description?.slice(0, 55)}
                </div>
                <div style={{ fontSize: 11 }}>
                  <div style={{ fontWeight: 600, color: "#111827" }}>{ticket.l1_category || "-"}</div>
                  <div style={{ color: "#9CA3AF", fontSize: 10, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ticket.l2_subcategory?.slice(0, 20) || "-"}
                  </div>
                </div>
                <div>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "2px 8px",
                      borderRadius: 12,
                      fontSize: 10,
                      fontWeight: 600,
                      background: statusConfig.bg,
                      color: statusConfig.color,
                    }}
                  >
                    {statusConfig.icon} {ticket.aiops_automation_status?.replace("Already ", "").replace(" Only", "").replace("Can Be ", "")}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: solutionConfig.color, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {solutionConfig.icon} {ticket.aiops_solution_lever?.slice(0, 12)}
                </div>
                <div>
                  <div
                    style={{
                      width: 36,
                      height: 5,
                      background: "#F3F4F6",
                      borderRadius: 3,
                      overflow: "hidden",
                      display: "inline-block",
                      verticalAlign: "middle",
                      marginRight: 6,
                    }}
                  >
                    <div
                      style={{
                        width: (ticket.automation_potential_score || 0) + "%",
                        height: "100%",
                        background: ticket.automation_potential_score > 70 ? "#10B981" : ticket.automation_potential_score > 40 ? "#F59E0B" : "#EF4444",
                        borderRadius: 3,
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#111827" }}>{ticket.automation_potential_score || 0}</span>
                </div>
              </div>

              {/* Expanded Evidence Panel */}
              {isExpanded && (
                <div
                  style={{
                    padding: "12px 14px 12px 114px",
                    background: "#F9FAFB",
                    borderBottom: "1px solid #E5E7EB",
                    fontSize: 11,
                  }}
                >
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                    <div>
                      <div style={{ fontWeight: 700, color: "#9CA3AF", fontSize: 9, textTransform: "uppercase", marginBottom: 4 }}>
                        Evidence
                      </div>
                      <div style={{ color: "#374151", lineHeight: 1.5 }}>
                        {ticket.aiops_keywords?.split(" | ").map((evidence, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 4 }}>
                            <span style={{ color: evidence.startsWith("✓") ? "#10B981" : evidence.startsWith("✗") ? "#EF4444" : "#F59E0B" }}>
                              {evidence.startsWith("✓") || evidence.startsWith("✗") || evidence.startsWith("") ? "" : "•"}
                            </span>
                            <span>{evidence}</span>
                          </div>
                        ))}
                        {!ticket.aiops_keywords && <span style={{ color: "#9CA3AF" }}>No evidence recorded</span>}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, color: "#9CA3AF", fontSize: 9, textTransform: "uppercase", marginBottom: 4 }}>
                        Resolution Info
                      </div>
                      <div style={{ color: "#374151", lineHeight: 1.6 }}>
                        <div><strong>Resolved by:</strong> {ticket.resolved_by || "N/A"}</div>
                        <div><strong>MTTR:</strong> {ticket.mttr_hours ? (ticket.mttr_hours * 60).toFixed(0) + " min" : "N/A"}</div>
                        <div><strong>Team:</strong> {ticket.assignment_group?.slice(0, 30) || "N/A"}</div>
                      </div>
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, color: "#9CA3AF", fontSize: 9, textTransform: "uppercase", marginBottom: 4 }}>
                        Recommendation
                      </div>
                      <div
                        style={{
                          padding: "8px 10px",
                          background: solutionConfig.color + "10",
                          border: "1px solid " + solutionConfig.color + "30",
                          borderRadius: 6,
                          color: solutionConfig.color,
                          fontWeight: 600,
                          marginBottom: 8,
                        }}
                      >
                        {solutionConfig.icon} {ticket.aiops_solution_lever}
                      </div>
                      {ticket.aiops_additional_info && (
                        <div style={{ fontSize: 10, color: "#6B7280", lineHeight: 1.4 }}>
                          {ticket.aiops_additional_info}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {tickets.length === 0 && !ticketsLoading && (
          <div style={{ padding: 40, textAlign: "center", color: "#9CA3AF" }}>
            No tickets match the current filters
          </div>
        )}

        {ticketsLoading && tickets.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: "#9CA3AF" }}>
            Loading tickets...
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1 || ticketsLoading}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #E5E7EB",
              background: "white",
              color: page === 1 ? "#D1D5DB" : "#374151",
              cursor: page === 1 ? "not-allowed" : "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 12, color: "#6B7280" }}>
            Page {page} of {totalPages} ({totalFiltered.toLocaleString()} total)
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages || ticketsLoading}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #E5E7EB",
              background: "white",
              color: page === totalPages ? "#D1D5DB" : "#374151",
              cursor: page === totalPages ? "not-allowed" : "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            Next →
          </button>
        </div>
      )}
        </>
      )}
    </div>
  );
}