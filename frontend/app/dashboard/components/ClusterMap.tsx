"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

const SOLUTION_COLORS: Record<string, string> = {
  "Auto-Remediation": "#10B981",
  "Script/Runbook": "#4F46E5",
  "Self-Service Portal": "#7C3AED",
  "Monitoring Rule": "#F59E0B",
  "Manual Review": "#EF4444",
};

const SOLUTION_ICONS: Record<string, string> = {
  "Auto-Remediation": "",
  "Script/Runbook": "",
  "Self-Service Portal": "",
  "Monitoring Rule": "",
  "Manual Review": "",
};

interface ClusterMapProps {
  onClusterClick?: (clusterId: number) => void;
  uploadId?: number;
}

export default function ClusterMap({ onClusterClick, uploadId }: ClusterMapProps) {
  const [clusters, setClusters] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    if (!uploadId) { setLoading(false); return; }
    const token = getToken();
    fetch(API + "/api/clusters/" + uploadId, {
      headers: { Authorization: "Bearer " + token },
    })
      .then(r => r.json())
      .then(data => {
        setClusters((data.clusters || []).slice(0, 10));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [uploadId]);

  if (loading) return (
    <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "#9CA3AF", fontSize: 12 }}>
      Loading cluster data...
    </div>
  );

  if (clusters.length === 0) return (
    <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "#9CA3AF", fontSize: 12, flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 28 }}></div>
      <div>BERT clustering running in background...</div>
    </div>
  );

  const maxCount = Math.max(...clusters.map(c => c.ticket_count));

  const getAutomationColor = (pct: number) => {
    if (pct > 50) return "#10B981";
    if (pct > 25) return "#F59E0B";
    return "#EF4444";
  };

  return (
    <div style={{ width: "100%" }}>
      {!selected ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {clusters.map((cluster) => {
            const color = SOLUTION_COLORS[cluster.solution] || "#6B7280";
            const barWidth = (cluster.ticket_count / maxCount) * 100;
            const label = cluster.sample_descriptions[0]?.slice(0, 45) || ("Cluster " + cluster.cluster_id);
            const isHovered = hovered === cluster.cluster_id;
            const autoPct = Math.min(cluster.automation_pct, 100);

            return (
              <div 
                key={cluster.cluster_id}
                onClick={() => { setSelected(cluster); if (onClusterClick) onClusterClick(cluster.cluster_id); }}
                onMouseEnter={() => setHovered(cluster.cluster_id)}
                onMouseLeave={() => setHovered(null)}
                style={{ 
                  cursor: "pointer", 
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: isHovered ? "#F8FAFC" : "transparent",
                  border: isHovered ? "1px solid #E2E8F0" : "1px solid transparent",
                  transition: "all 0.15s ease",
                  transform: isHovered ? "translateX(2px)" : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <div style={{ 
                    width: 20, height: 20, borderRadius: 4, 
                    background: color + "20", 
                    display: "flex", alignItems: "center", justifyContent: "center", 
                    fontSize: 9, fontWeight: 800, color: color, flexShrink: 0 
                  }}>
                    {SOLUTION_ICONS[cluster.solution]}
                  </div>
                  <div style={{ fontSize: 11, color: "#374151", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#111827", flexShrink: 0 }}>
                    {cluster.ticket_count.toLocaleString()}
                  </div>
                  <div style={{ 
                    fontSize: 10, fontWeight: 600, 
                    color: getAutomationColor(autoPct), 
                    flexShrink: 0, minWidth: 35, textAlign: "right" 
                  }}>
                    {autoPct.toFixed(0)}%
                  </div>
                </div>
                <div style={{ height: 5, background: "#F3F4F6", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ 
                    height: "100%", 
                    width: barWidth + "%", 
                    background: color,
                    borderRadius: 3, 
                    transition: "width 0.4s ease" 
                  }} />
                </div>
              </div>
            );
          })}
          <div style={{ fontSize: 10, color: "#9CA3AF", textAlign: "center", marginTop: 6 }}>
            Click any cluster to drill down · Top 10 of {clusters.length} clusters
          </div>
        </div>
      ) : (
        <div style={{ position: "relative" }}>
          <button 
            onClick={() => setSelected(null)} 
            style={{
              position: "absolute", top: 0, right: 0, fontSize: 11, color: "#6B7280",
              background: "#F3F4F6", border: "none", borderRadius: 6, padding: "4px 12px", 
              cursor: "pointer", fontWeight: 600,
            }}
          >
            ← Back
          </button>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#111827" }}>
              {SOLUTION_ICONS[selected.solution]} {selected.sample_descriptions[0]?.slice(0, 50)}
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>
              {selected.ticket_count} tickets · {selected.solution} · {selected.confidence}% confidence
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, marginBottom: 12 }}>
            <div style={{ background: "#F9FAFB", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: "#10B981", fontFamily: "'JetBrains Mono',monospace" }}>{selected.already_automated}</div>
              <div style={{ fontSize: 9, color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600 }}>Already Automated</div>
            </div>
            <div style={{ background: "#F9FAFB", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: "#4F46E5", fontFamily: "'JetBrains Mono',monospace" }}>{selected.can_automate}</div>
              <div style={{ fontSize: 9, color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600 }}>Can Automate</div>
            </div>
            <div style={{ background: "#F9FAFB", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: "#F59E0B", fontFamily: "'JetBrains Mono',monospace" }}>{selected.hours_saved}</div>
              <div style={{ fontSize: 9, color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600 }}>Hours Saved/mo</div>
            </div>
          </div>

          <div style={{ 
            background: (SOLUTION_COLORS[selected.solution] || "#6B7280") + "10", 
            border: "1px solid " + (SOLUTION_COLORS[selected.solution] || "#6B7280") + "30", 
            borderRadius: 8, padding: "8px 12px", marginBottom: 10 
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: SOLUTION_COLORS[selected.solution], textTransform: "uppercase" }}>Recommended</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#111827" }}>{selected.action}</div>
          </div>

          <div style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", marginBottom: 5 }}>Sample Tickets</div>
          {selected.sample_descriptions.slice(0, 3).map((d: string, i: number) => (
            <div key={i} style={{ fontSize: 11, color: "#374151", padding: "4px 8px", background: "#F9FAFB", borderRadius: 4, marginBottom: 3 }}>
              {d.slice(0, 70)}
            </div>
          ))}

          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 8 }}>
            {selected.keywords.map((k: string, i: number) => (
              <span key={i} style={{ fontSize: 10, background: "#EEF2FF", color: "#4F46E5", padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>{k}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}