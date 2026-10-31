"use client";
import { useState, useEffect } from "react";
import CXOClusterView from "./CXOClusterView";

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
  "Automation Tuning": "#F59E0B",
  "Existing Automation": "#10B981",
  "Manual Process": "#EF4444",
};


const SOLUTION_ICONS: Record<string, string> = {
  "Auto-Remediation": "",
  "Script/Runbook": "",
  "Self-Service Portal": "",
  "Monitoring Rule": "",
  "Manual Review": "",
  "Automation Tuning": "",
  "Existing Automation": "✓",
  "Manual Process": "",
  "RPA": "",
};
const CLUSTER_COLORS = [
  "#4F46E5","#10B981","#F59E0B","#EF4444","#7C3AED",
  "#EC4899","#06B6D4","#84CC16","#F97316","#8B5CF6",
  "#14B8A6","#F43F5E","#6366F1","#A3E635","#FB923C",
];

interface Cluster {
  cluster_id: number;
  ticket_count: number;
  already_automated: number;
  can_automate: number;
  automation_pct: number;
  solution: string;
  action: string;
  confidence: number;
  sample_descriptions: string[];
  keywords: string[];
  hours_saved: number;
}

interface ClustersTabProps {
  uploadId: number;
  datasetName?: string;
}

export default function ClustersTab({ uploadId, datasetName }: ClustersTabProps) {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Cluster | null>(null);
  const [filter, setFilter] = useState("All");
  const [showCXO, setShowCXO] = useState(false);

  useEffect(() => {
    if (!uploadId) return;
    const token = getToken();
    fetch(`${API}/api/clusters/${uploadId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setClusters(data.clusters || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [uploadId]);

  const solutions = ["All", ...Array.from(new Set(clusters.map((c) => c.solution)))];
  const filtered = filter === "All" ? clusters : clusters.filter((c) => c.solution === filter);

  const totalTickets = clusters.reduce((s, c) => s + c.ticket_count, 0);
  const totalSaveable = clusters.filter(c => c.solution !== "Manual Review" && c.solution !== "Manual Process").reduce((s, c) => s + c.ticket_count, 0);
  const totalHours = clusters.reduce((s, c) => s + c.hours_saved, 0);

  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:300, color:"#6B7280", fontSize:13 }}>
      <div style={{ textAlign:"center" }}>
        <div style={{ fontSize:32, marginBottom:8 }}></div>
        <p>Loading cluster intelligence...</p>
      </div>
    </div>
  );

  if (clusters.length === 0) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:300, color:"#6B7280", fontSize:13 }}>
      <div style={{ textAlign:"center" }}>
        <div style={{ fontSize:32, marginBottom:8 }}></div>
        <p>BERT clustering not yet complete.</p>
        <p style={{ fontSize:11, color:"#9CA3AF", marginTop:4 }}>ML analysis runs in background — check back shortly.</p>
      </div>
    </div>
  );

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

      {/* CXO View Toggle Button */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={() => setShowCXO(!showCXO)}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
            border: showCXO ? "1px solid #E5E7EB" : "none",
            background: showCXO 
              ? "white" 
              : "linear-gradient(135deg, #1E293B 0%, #334155 100%)",
            color: showCXO ? "#1E293B" : "white",
            boxShadow: showCXO ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "all 0.2s",
          }}
        >
          {showCXO ? "Technical View" : "CXO Executive View"}
        </button>
      </div>

      {/* Conditional Rendering: CXO View or Technical View */}
      {showCXO ? (
        <CXOClusterView uploadId={uploadId} datasetName={datasetName} />
      ) : (
        <>
          {/* Summary KPIs */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
            {[
              { label:"Total Clusters", value: clusters.length, sub:"Distinct ticket patterns", color:"#4F46E5" },
              { label:"Clustered Tickets", value: totalTickets.toLocaleString(), sub:"BERT sample analyzed", color:"#7C3AED" },
              { label:"Automatable Clusters", value: clusters.filter(c=>c.solution!=="Manual Review" && c.solution!=="Manual Process").length, sub:`${Math.round(totalSaveable/totalTickets*100)}% of tickets`, color:"#10B981" },
              { label:"Est. Hours Saved", value: totalHours.toLocaleString(), sub:"Per month if automated", color:"#F59E0B" },
            ].map((k, i) => (
              <div key={i} style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:10, padding:"14px 16px", borderTop:`3px solid ${k.color}` }}>
                <div style={{ fontSize:10, fontWeight:700, color:"#9CA3AF", textTransform:"uppercase", letterSpacing:0.5 }}>{k.label}</div>
                <div style={{ fontSize:24, fontWeight:800, color:"#111827", marginTop:4, fontFamily:"'JetBrains Mono',monospace" }}>{k.value}</div>
                <div style={{ fontSize:11, color:"#6B7280", marginTop:2 }}>{k.sub}</div>
              </div>
            ))}
          </div>

          {/* Filter bar */}
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            {solutions.map((s) => (
              <button key={s} onClick={() => setFilter(s)} style={{
                padding:"5px 14px", borderRadius:20, fontSize:12, fontWeight:600, cursor:"pointer", border:"1px solid",
                borderColor: filter===s ? SOLUTION_COLORS[s] || "#4F46E5" : "#E5E7EB",
                background: filter===s ? (SOLUTION_COLORS[s] || "#4F46E5") + "15" : "white",
                color: filter===s ? SOLUTION_COLORS[s] || "#4F46E5" : "#6B7280",
              }}>
                {s !== "All" ? (SOLUTION_ICONS[s] || "") + " " : ""}{s}
                <span style={{ marginLeft:6, fontSize:10, opacity:0.7 }}>
                  {s === "All" ? clusters.length : clusters.filter(c=>c.solution===s).length}
                </span>
              </button>
            ))}
          </div>

          {/* Two-panel layout */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 380px", gap:16 }}>

            {/* Cluster list */}
            <div style={{ display:"flex", flexDirection:"column", gap:8, maxHeight:520, overflowY:"auto" }}>
              {filtered.map((cluster, i) => {
                const color = CLUSTER_COLORS[i % CLUSTER_COLORS.length];
                const isSelected = selected?.cluster_id === cluster.cluster_id;
                return (
                  <div key={cluster.cluster_id} onClick={() => setSelected(isSelected ? null : cluster)}
                    style={{
                      background:"white",
                      borderTop:`1px solid ${isSelected ? color : "#E5E7EB"}`,
                      borderRight:`1px solid ${isSelected ? color : "#E5E7EB"}`,
                      borderBottom:`1px solid ${isSelected ? color : "#E5E7EB"}`,
                      borderLeft: `4px solid ${color}`,
                      borderRadius:8, padding:"12px 14px", cursor:"pointer",
                      boxShadow: isSelected ? `0 0 0 2px ${color}30` : "none",
                      transition:"all 0.15s",
                    }}>
                    <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <div style={{ width:28, height:28, borderRadius:6, background:color+"20", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:800, color, flexShrink:0 }}>
                        C{cluster.cluster_id}
                      </div>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:12, fontWeight:600, color:"#111827", marginBottom:2, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                          {cluster.sample_descriptions[0]?.slice(0, 60) || "Cluster " + cluster.cluster_id}
                        </div>
                        <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                          {cluster.keywords.slice(0,4).map((k, ki) => (
                            <span key={ki} style={{ fontSize:9, fontWeight:600, background:"#F3F4F6", color:"#6B7280", padding:"2px 6px", borderRadius:4 }}>
                              {k}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div style={{ textAlign:"right", flexShrink:0 }}>
                        <div style={{ fontSize:13, fontWeight:800, color:"#111827" }}>{cluster.ticket_count.toLocaleString()}</div>
                        <div style={{ fontSize:10, color:"#9CA3AF" }}>tickets</div>
                      </div>
                      <div style={{ textAlign:"right", flexShrink:0, minWidth:90 }}>
                        <span style={{
                          fontSize:11, fontWeight:700, padding:"3px 8px", borderRadius:12,
                          background: (SOLUTION_COLORS[cluster.solution] || "#6B7280") + "15",
                          color: SOLUTION_COLORS[cluster.solution] || "#6B7280",
                        }}>
                          {SOLUTION_ICONS[cluster.solution] || ""} {cluster.solution}
                        </span>
                      </div>
                      <div style={{ textAlign:"right", flexShrink:0 }}>
                        <div style={{ fontSize:13, fontWeight:800, color: cluster.automation_pct > 70 ? "#10B981" : cluster.automation_pct > 40 ? "#F59E0B" : "#EF4444" }}>
                          {cluster.automation_pct}%
                        </div>
                        <div style={{ fontSize:10, color:"#9CA3AF" }}>automatable</div>
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div style={{ marginTop:8, height:3, background:"#F3F4F6", borderRadius:2, overflow:"hidden" }}>
                      <div style={{ height:"100%", width:`${cluster.automation_pct}%`, background: cluster.automation_pct > 70 ? "#10B981" : cluster.automation_pct > 40 ? "#F59E0B" : "#EF4444", borderRadius:2 }} />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Detail panel */}
            <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:10, padding:18, height:"fit-content", position:"sticky", top:0 }}>
              {selected ? (
                <>
                  <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:16 }}>
                    <div style={{ width:36, height:36, borderRadius:8, background:(SOLUTION_COLORS[selected.solution] || "#6B7280")+"20", display:"flex", alignItems:"center", justifyContent:"center", fontSize:18 }}>
                      {SOLUTION_ICONS[selected.solution] || ""}
                    </div>
                    <div>
                      <div style={{ fontSize:13, fontWeight:700, color:"#111827" }}>Cluster {selected.cluster_id}</div>
                      <div style={{ fontSize:11, color:"#6B7280" }}>{selected.ticket_count} tickets · {selected.automation_pct}% automatable</div>
                    </div>
                  </div>

                  {/* Automation recommendation */}
                  <div style={{ background: (SOLUTION_COLORS[selected.solution] || "#6B7280")+"10", border:`1px solid ${SOLUTION_COLORS[selected.solution] || "#6B7280"}30`, borderRadius:8, padding:12, marginBottom:14 }}>
                    <div style={{ fontSize:10, fontWeight:700, color: SOLUTION_COLORS[selected.solution] || "#6B7280", textTransform:"uppercase", letterSpacing:0.5, marginBottom:4 }}>
                      Recommended Action
                    </div>
                    <div style={{ fontSize:13, fontWeight:700, color:"#111827" }}>{selected.solution}</div>
                    <div style={{ fontSize:12, color:"#374151", marginTop:2 }}>{selected.action}</div>
                    <div style={{ fontSize:11, color:"#6B7280", marginTop:4 }}>Confidence: {selected.confidence}%</div>
                  </div>

                  {/* Stats */}
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginBottom:14 }}>
                    {[
                      { label:"Already Automated", value: selected.already_automated, color:"#10B981" },
                      { label:"Can Automate", value: selected.can_automate, color:"#4F46E5" },
                      { label:"Manual Only", value: Math.max(0, selected.ticket_count - selected.already_automated - selected.can_automate), color:"#EF4444" },
                      { label:"Hours Saved/Month", value: selected.hours_saved, color:"#F59E0B" },
                    ].map((s, i) => (
                      <div key={i} style={{ background:"#F9FAFB", borderRadius:6, padding:"8px 10px" }}>
                        <div style={{ fontSize:9, color:"#9CA3AF", textTransform:"uppercase", fontWeight:700 }}>{s.label}</div>
                        <div style={{ fontSize:18, fontWeight:800, color: s.color, fontFamily:"'JetBrains Mono',monospace" }}>{s.value.toLocaleString()}</div>
                      </div>
                    ))}
                  </div>

                  {/* Sample tickets */}
                  <div style={{ fontSize:10, fontWeight:700, color:"#9CA3AF", textTransform:"uppercase", letterSpacing:0.5, marginBottom:8 }}>Sample Tickets</div>
                  {selected.sample_descriptions.map((d, i) => (
                    <div key={i} style={{ fontSize:11, color:"#374151", padding:"6px 10px", background:"#F9FAFB", borderRadius:5, marginBottom:4, lineHeight:1.4 }}>
                      {d.slice(0, 90)}
                    </div>
                  ))}

                  {/* Keywords */}
                  <div style={{ marginTop:12 }}>
                    <div style={{ fontSize:10, fontWeight:700, color:"#9CA3AF", textTransform:"uppercase", letterSpacing:0.5, marginBottom:6 }}>Top Keywords</div>
                    <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                      {selected.keywords.map((k, i) => (
                        <span key={i} style={{ fontSize:11, background:"#EEF2FF", color:"#4F46E5", padding:"3px 8px", borderRadius:4, fontWeight:600 }}>{k}</span>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", height:200, color:"#9CA3AF", textAlign:"center" }}>
                  <div style={{ fontSize:32, marginBottom:8 }}></div>
                  <div style={{ fontSize:12, fontWeight:600 }}>Click a cluster to see</div>
                  <div style={{ fontSize:11, marginTop:2 }}>automation intelligence & recommendations</div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}