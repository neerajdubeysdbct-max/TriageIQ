"use client";
import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

interface ClusterStory {
  cluster_id: number;
  name: string;
  icon: string;
  color: string;
  confidence: number;
  what: string;
  why: string;
  impact: string;
  ticket_count: number;
  can_automate: number;
  already_automated: number;
  manual_only: number;
  automation_pct: number;
  hours_saved_monthly: number;
  monthly_savings_lakhs: number;
  annual_savings_lakhs: number;
  solution: string;
  solution_detail: string;
  implementation: string;
  investment: string;
  payback_months: number;
  roi_percent: number;
  keywords: string[];
  sample_tickets: string[];
}

interface Summary {
  dataset_name: string;
  total_tickets: number;
  total_clusters: number;
  total_can_automate: number;
  total_already_automated: number;
  total_hours_saved: number;
  total_monthly_savings_lakhs: number;
  total_annual_savings_cr: number;
}

interface CXOClusterViewProps {
  uploadId: number;
  datasetName?: string;
}

const SOLUTION_ICONS: Record<string, string> = {
  "Self-Service Portal": "",
  "Auto-Remediation": "",
  "Automation Tuning": "",
  "Script/Runbook": "",
  "Existing Automation": "✓",
  "Manual Process": "",
};

export default function CXOClusterView({ uploadId, datasetName }: CXOClusterViewProps) {
  const [clusters, setClusters] = useState<ClusterStory[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<ClusterStory | null>(null);
  const [showMLExplainer, setShowMLExplainer] = useState(false);

  useEffect(() => {
    if (!uploadId) return;
    const token = getToken();

    fetch(`${API}/api/cxo-clusters/${uploadId}`, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => r.json())
      .then((data) => {
        setClusters(data.clusters || []);
        setSummary(data.summary || null);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching CXO clusters:", err);
        setLoading(false);
      });
  }, [uploadId]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400, color: "#6B7280" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}></div>
          <p style={{ fontSize: 14 }}>Analyzing patterns with AI...</p>
        </div>
      </div>
    );
  }

  const getAutomationColor = (pct: number): string => {
    if (pct >= 80) return "#10B981";
    if (pct >= 50) return "#F59E0B";
    if (pct >= 20) return "#F97316";
    return "#EF4444";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Executive Summary Header */}
      <div style={{
        background: "linear-gradient(135deg, #1E293B 0%, #334155 100%)",
        borderRadius: 16,
        padding: 28,
        color: "white",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: 2, marginBottom: 6 }}>
              AI-Discovered Automation Opportunities
            </div>
            <div style={{ fontSize: 26, fontWeight: 800 }}>
              {summary?.dataset_name || datasetName || "Ticket Analysis"}
            </div>
            <div style={{ fontSize: 13, color: "#94A3B8", marginTop: 4 }}>
              BERT ML analyzed {summary?.total_tickets?.toLocaleString()} tickets and found {summary?.total_clusters} distinct patterns
            </div>
          </div>
          <button
            onClick={() => setShowMLExplainer(!showMLExplainer)}
            style={{
              padding: "8px 16px",
              background: "rgba(255,255,255,0.1)",
              border: "1px solid rgba(255,255,255,0.2)",
              borderRadius: 8,
              color: "white",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {showMLExplainer ? "Hide" : "How AI Works"}
          </button>
        </div>

        {/* Key Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 16, textAlign: "center" }}>
            <div style={{ fontSize: 32, fontWeight: 800, color: "#818CF8" }}>
              {summary?.total_clusters}
            </div>
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>Patterns Found</div>
          </div>
          <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 16, textAlign: "center" }}>
            <div style={{ fontSize: 32, fontWeight: 800, color: "#34D399" }}>
              {summary?.total_can_automate?.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>Can Automate</div>
          </div>
          <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 16, textAlign: "center" }}>
            <div style={{ fontSize: 32, fontWeight: 800, color: "#FBBF24" }}>
              ₹{summary?.total_annual_savings_cr}Cr
            </div>
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>Annual Savings</div>
          </div>
          <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: 16, textAlign: "center" }}>
            <div style={{ fontSize: 32, fontWeight: 800, color: "#A78BFA" }}>
              {summary?.total_hours_saved?.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>Hours Saved/Month</div>
          </div>
        </div>
      </div>

      {/* ML Explainer (Collapsible) */}
      {showMLExplainer && (
        <div style={{
          background: "#F8FAFC",
          border: "1px solid #E2E8F0",
          borderRadius: 12,
          padding: 24,
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#1E293B", marginBottom: 16 }}>
            How AI Discovered These Patterns
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", background: "#EEF2FF",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 12px", fontSize: 28
              }}>
                
              </div>
              <div style={{ fontWeight: 700, color: "#1E293B", marginBottom: 4 }}>Step 1: BERT Embeddings</div>
              <div style={{ fontSize: 12, color: "#64748B" }}>
                Each ticket description converted to 384-dimensional vector capturing semantic meaning
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", background: "#F0FDF4",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 12px", fontSize: 28
              }}>
                
              </div>
              <div style={{ fontWeight: 700, color: "#1E293B", marginBottom: 4 }}>Step 2: K-Means Clustering</div>
              <div style={{ fontSize: 12, color: "#64748B" }}>
                Similar tickets grouped into {summary?.total_clusters} clusters based on semantic similarity
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", background: "#FEF3C7",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 12px", fontSize: 28
              }}>
                
              </div>
              <div style={{ fontWeight: 700, color: "#1E293B", marginBottom: 4 }}>Step 3: Business Mapping</div>
              <div style={{ fontSize: 12, color: "#64748B" }}>
                Each cluster mapped to business category with automation recommendation
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cluster Tiles Grid */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#374151", marginBottom: 16 }}>
          {summary?.total_clusters} Automation Opportunities
          <span style={{ fontWeight: 400, color: "#9CA3AF", marginLeft: 8 }}>
            Click any tile to see details
          </span>
        </div>
        
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 12,
        }}>
          {clusters.map((cluster) => {
            const autoColor = getAutomationColor(cluster.automation_pct);
            const isSelected = selectedCluster?.cluster_id === cluster.cluster_id;
            
            return (
              <div
                key={cluster.cluster_id}
                onClick={() => setSelectedCluster(isSelected ? null : cluster)}
                style={{
                  background: isSelected ? `${cluster.color}10` : "white",
                  border: isSelected ? `2px solid ${cluster.color}` : "1px solid #E5E7EB",
                  borderRadius: 12,
                  padding: 16,
                  cursor: "pointer",
                  transition: "all 0.2s",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                {/* Color accent bar */}
                <div style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 4,
                  background: cluster.color,
                }} />

                {/* Header */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 12, marginTop: 4 }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    background: `${cluster.color}15`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 18,
                    flexShrink: 0,
                  }}>
                    {cluster.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: "#1E293B",
                      lineHeight: 1.3,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                    }}>
                      {cluster.name}
                    </div>
                  </div>
                </div>

                {/* Ticket Count */}
                <div style={{ fontSize: 24, fontWeight: 800, color: "#1E293B", marginBottom: 4 }}>
                  {cluster.ticket_count.toLocaleString()}
                </div>
                <div style={{ fontSize: 11, color: "#64748B", marginBottom: 12 }}>tickets</div>

                {/* Automation Bar */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: "#64748B" }}>Automatable</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: autoColor }}>{cluster.automation_pct}%</span>
                  </div>
                  <div style={{
                    height: 6,
                    background: "#F1F5F9",
                    borderRadius: 3,
                    overflow: "hidden",
                  }}>
                    <div style={{
                      width: `${cluster.automation_pct}%`,
                      height: "100%",
                      background: autoColor,
                      borderRadius: 3,
                    }} />
                  </div>
                </div>

                {/* Solution & Savings */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 8px",
                    background: "#F1F5F9",
                    borderRadius: 6,
                    fontSize: 10,
                    fontWeight: 600,
                    color: "#475569",
                  }}>
                    {SOLUTION_ICONS[cluster.solution] || ""} {cluster.solution.split(" ")[0]}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#10B981" }}>
                    ₹{cluster.monthly_savings_lakhs}L/mo
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Cluster Detail Panel */}
      {selectedCluster && (
        <div style={{
          background: "white",
          border: `2px solid ${selectedCluster.color}`,
          borderRadius: 16,
          padding: 24,
          marginTop: 8,
        }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: 12,
              background: `${selectedCluster.color}15`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
            }}>
              {selectedCluster.icon}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#1E293B" }}>
                {selectedCluster.name}
              </div>
              <div style={{ fontSize: 13, color: "#64748B" }}>
                Cluster #{selectedCluster.cluster_id} • {selectedCluster.ticket_count.toLocaleString()} tickets • {selectedCluster.automation_pct}% automatable
              </div>
            </div>
            <div style={{
              padding: "6px 12px",
              background: `${selectedCluster.color}15`,
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 600,
              color: selectedCluster.color,
            }}>
              {selectedCluster.confidence}% confidence
            </div>
          </div>

          {/* Story Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
            {/* WHAT */}
            <div style={{ background: "#F8FAFC", borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8", textTransform: "uppercase", marginBottom: 8 }}>
                What Is This?
              </div>
              <div style={{ fontSize: 14, color: "#334155", lineHeight: 1.6 }}>
                {selectedCluster.what}
              </div>
            </div>

            {/* WHY */}
            <div style={{ background: "#F8FAFC", borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8", textTransform: "uppercase", marginBottom: 8 }}>
                Why Does It Happen?
              </div>
              <div style={{ fontSize: 14, color: "#334155", lineHeight: 1.6 }}>
                {selectedCluster.why}
              </div>
            </div>
          </div>

          {/* Impact & Numbers */}
          <div style={{
            background: "#FEF2F2",
            border: "1px solid #FECACA",
            borderRadius: 12,
            padding: 16,
            marginBottom: 24,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#DC2626", textTransform: "uppercase", marginBottom: 8 }}>
              Business Impact
            </div>
            <div style={{ fontSize: 15, color: "#7F1D1D", fontWeight: 600 }}>
              {selectedCluster.impact}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 16 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#10B981" }}>{selectedCluster.already_automated.toLocaleString()}</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Already Automated</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#4F46E5" }}>{selectedCluster.can_automate.toLocaleString()}</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Can Automate</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#F59E0B" }}>{selectedCluster.hours_saved_monthly.toLocaleString()}</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Hours/Month</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#10B981" }}>₹{selectedCluster.annual_savings_lakhs}L</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Annual Savings</div>
              </div>
            </div>
          </div>

          {/* Recommended Solution */}
          <div style={{
            background: `${selectedCluster.color}10`,
            border: `1px solid ${selectedCluster.color}30`,
            borderRadius: 12,
            padding: 20,
            marginBottom: 24,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: selectedCluster.color, textTransform: "uppercase", marginBottom: 8 }}>
              Recommended Solution
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#1E293B", marginBottom: 8 }}>
              {SOLUTION_ICONS[selectedCluster.solution]} {selectedCluster.solution}
            </div>
            <div style={{ fontSize: 14, color: "#475569", marginBottom: 16 }}>
              {selectedCluster.solution_detail}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              <div style={{ background: "white", borderRadius: 8, padding: 12, textAlign: "center" }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#1E293B" }}>{selectedCluster.implementation}</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Implementation</div>
              </div>
              <div style={{ background: "white", borderRadius: 8, padding: 12, textAlign: "center" }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#1E293B" }}>{selectedCluster.investment}</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Investment</div>
              </div>
              <div style={{ background: "white", borderRadius: 8, padding: 12, textAlign: "center" }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#10B981" }}>{selectedCluster.payback_months} months</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Payback Period</div>
              </div>
              <div style={{ background: "white", borderRadius: 8, padding: 12, textAlign: "center" }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#10B981" }}>{selectedCluster.roi_percent}%</div>
                <div style={{ fontSize: 10, color: "#64748B" }}>Annual ROI</div>
              </div>
            </div>
          </div>

          {/* Sample Tickets & Keywords */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8", textTransform: "uppercase", marginBottom: 12 }}>
                Sample Tickets
              </div>
              {selectedCluster.sample_tickets.map((ticket, i) => (
                <div key={i} style={{
                  padding: "10px 12px",
                  background: "#F8FAFC",
                  borderRadius: 6,
                  marginBottom: 6,
                  fontSize: 12,
                  color: "#475569",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {ticket}
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8", textTransform: "uppercase", marginBottom: 12 }}>
                Top Keywords
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {selectedCluster.keywords.map((keyword, i) => (
                  <span key={i} style={{
                    padding: "4px 10px",
                    background: `${selectedCluster.color}15`,
                    color: selectedCluster.color,
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 600,
                  }}>
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", gap: 12, marginTop: 24, paddingTop: 20, borderTop: "1px solid #E5E7EB" }}>
            <button 
              onClick={() => {
                // Navigate to tickets filtered by cluster
                window.location.href = `/dashboard?tab=automation&cluster=${selectedCluster.cluster_id}`;
              }}
              style={{
                flex: 1,
                padding: "12px",
                background: selectedCluster.color,
                color: "white",
                border: "none",
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              View All {selectedCluster.ticket_count.toLocaleString()} Tickets
            </button>
            <button 
              onClick={() => {
                // Generate and download PDF report
                const reportContent = `
AUTOMATION OPPORTUNITY REPORT
=============================
Generated: ${new Date().toLocaleDateString('en-IN')}

CLUSTER: ${selectedCluster.name}
Cluster ID: #${selectedCluster.cluster_id}
Total Tickets: ${selectedCluster.ticket_count.toLocaleString()}
Automation Potential: ${selectedCluster.automation_pct}%

ANALYSIS
--------
What Is This?
${selectedCluster.what}

Why Does It Happen?
${selectedCluster.why}

Business Impact:
${selectedCluster.impact}

METRICS
-------
Already Automated: ${selectedCluster.already_automated.toLocaleString()}
Can Automate: ${selectedCluster.can_automate.toLocaleString()}
Hours Saved/Month: ${selectedCluster.hours_saved_monthly.toLocaleString()}
Monthly Savings: ₹${selectedCluster.monthly_savings_lakhs}L
Annual Savings: ₹${selectedCluster.annual_savings_lakhs}L

RECOMMENDED SOLUTION
--------------------
Solution: ${selectedCluster.solution}
Details: ${selectedCluster.solution_detail}
Implementation: ${selectedCluster.implementation}
Investment: ${selectedCluster.investment}
Payback Period: ${selectedCluster.payback_months} months
Annual ROI: ${selectedCluster.roi_percent}%

SAMPLE TICKETS
--------------
${selectedCluster.sample_tickets.map((t, i) => `${i+1}. ${t}`).join('\n')}

TOP KEYWORDS
------------
${selectedCluster.keywords.join(', ')}

---
Generated by TriageIQ ML Engine
                `.trim();
                
                const blob = new Blob([reportContent], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Cluster_${selectedCluster.cluster_id}_${selectedCluster.name.replace(/[^a-zA-Z0-9]/g, '_')}_Report.txt`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              style={{
                flex: 1,
                padding: "12px",
                background: "white",
                color: selectedCluster.color,
                border: `1px solid ${selectedCluster.color}`,
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Export Report
            </button>
            <button 
              onClick={() => {
                alert('Added to proposal! (Feature coming soon)');
              }}
              style={{
                flex: 1,
                padding: "12px",
                background: "white",
                color: "#475569",
                border: "1px solid #E5E7EB",
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Add to Proposal
            </button>
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{
        display: "flex",
        justifyContent: "center",
        gap: 24,
        padding: 16,
        background: "#F8FAFC",
        borderRadius: 8,
        fontSize: 11,
        color: "#64748B",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, background: "#10B981", borderRadius: 2 }} />
          <span>High automation (≥80%)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, background: "#F59E0B", borderRadius: 2 }} />
          <span>Medium (50-79%)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, background: "#F97316", borderRadius: 2 }} />
          <span>Low (20-49%)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, background: "#EF4444", borderRadius: 2 }} />
          <span>Manual (&lt;20%)</span>
        </div>
      </div>

      {/* Footer */}
      <div style={{ textAlign: "center", fontSize: 11, color: "#94A3B8" }}>
        Generated by TriageIQ ML Engine • {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
      </div>
    </div>
  );
}