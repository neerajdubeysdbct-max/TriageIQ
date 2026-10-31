"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  Brain, TrendingUp, TrendingDown, Minus, Zap,
  ChevronRight, BarChart3, DollarSign, RefreshCw, X,
} from "lucide-react";
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie, AreaChart, Area, Legend,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

const CLUSTER_COLORS = [
  "#10B981", "#6366F1", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
  "#84CC16", "#E11D48", "#0EA5E9", "#D946EF", "#22D3EE",
  "#A855F7", "#F43F5E", "#2DD4BF", "#FB923C", "#818CF8",
  "#34D399", "#818CF8", "#FBBF24", "#F87171", "#A78BFA",
];

const TREND_ICONS: any = {
  increasing: TrendingUp, decreasing: TrendingDown, stable: Minus,
};

const EFFORT_COLORS: Record<string, string> = {
  Low: "bg-green-500/10 text-green-600 border-green-500/20",
  Medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  High: "bg-red-500/10 text-red-600 border-red-500/20",
};

type TabId = "overview" | "clusters" | "problems" | "solutions" | "teams" | "charts" | "cxo";

function BERTFullView({ uploadId }: { uploadId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);
  const [chartConfig, setChartConfig] = useState({ x_axis: "cluster_id", y_axis: "count", group_by: "" });
  const [dynamicChartData, setDynamicChartData] = useState<any>(null);

  useEffect(() => {
    if (uploadId) fetchData();
  }, [uploadId]);

  async function fetchData() {
    try {
      setLoading(true);
      const token = getToken();
      const res = await fetch(`${API}/api/cluster-intelligence/${uploadId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Failed to fetch cluster intelligence:", err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchDynamicChart() {
    try {
      const token = getToken();
      const params = new URLSearchParams({
        x_axis: chartConfig.x_axis, y_axis: chartConfig.y_axis,
        ...(chartConfig.group_by && { group_by: chartConfig.group_by }),
      });
      const res = await fetch(
        `${API}/api/cluster-intelligence/${uploadId}/dynamic-chart?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) setDynamicChartData(await res.json());
    } catch (err) {
      console.error("Failed to fetch dynamic chart:", err);
    }
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "clusters", label: `All ${data?.model_info?.total_clusters || ""} Clusters` },
    { id: "problems", label: "Problems" },
    { id: "solutions", label: "Solutions & ROI" },
    { id: "teams", label: "Team View" },
    { id: "charts", label: "Dynamic Graph" },
    { id: "cxo", label: "CXO Summary" },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-center">
          <RefreshCw className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
          <p className="text-lg font-semibold text-foreground">Analyzing clusters...</p>
          <p className="text-sm text-muted-foreground mt-1">Processing ticket patterns with BERT</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <p className="text-muted-foreground">No cluster data available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-4 border-b border-border bg-card shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10">
            <Brain className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">BERT Semantic Intelligence</h1>
            <p className="text-sm text-muted-foreground">
              {data.model_info.total_clusters} clusters · {data.model_info.total_tickets.toLocaleString()} tickets · {data.model_info.model}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="gap-1.5 bg-green-500/10 text-green-600 border-green-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Analysis Complete
          </Badge>
          <Button variant="outline" size="sm" className="gap-2" onClick={fetchData}>
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </Button>
          <Button variant="outline" size="sm" className="gap-2" onClick={() => window.close()}>
            <X className="w-3.5 h-3.5" /> Close Tab
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-8 border-b border-border bg-card shrink-0 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-5 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content — scrollable full width */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto p-8">

          {/* ═══ OVERVIEW ═══ */}
          {activeTab === "overview" && (
            <div className="flex flex-col gap-8">
              <div className="grid grid-cols-4 gap-6">
                {[
                  { label: "Total Clusters", value: data.model_info.total_clusters, icon: Brain },
                  { label: "Tickets Analyzed", value: data.model_info.total_tickets.toLocaleString(), icon: BarChart3 },
                  { label: "Total Savings", value: `₹${data.cxo_summary.total_annual_savings_cr}Cr/yr`, icon: DollarSign },
                  { label: "Quick Wins", value: data.cxo_summary.quick_wins?.length || 0, icon: Zap },
                ].map((s) => (
                  <Card key={s.label} className="py-6 gap-2">
                    <CardContent className="px-6 py-0">
                      <s.icon className="w-5 h-5 text-primary mb-3" />
                      <p className="text-2xl font-bold text-foreground">{s.value}</p>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{s.label}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {data.tsne_data?.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Ticket Cluster Map (t-SNE)</CardTitle>
                    <CardDescription>Each dot is a ticket, color = cluster. Nearby dots are semantically similar.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[500px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="x" tick={{ fontSize: 9 }} name="t-SNE 1" />
                          <YAxis dataKey="y" tick={{ fontSize: 9 }} name="t-SNE 2" />
                          <Tooltip content={({ payload }: any) => {
                            if (!payload?.[0]?.payload) return null;
                            const p = payload[0].payload;
                            return (
                              <div className="bg-popover border border-border rounded-lg p-3 shadow-lg max-w-xs">
                                <p className="text-xs font-semibold text-foreground">{p.ticket_id}</p>
                                <p className="text-[11px] text-muted-foreground mt-1">{p.short_description}</p>
                                <p className="text-[10px] text-primary mt-1">Cluster {p.cluster_id}</p>
                              </div>
                            );
                          }} />
                          <Scatter data={data.tsne_data} fillOpacity={0.6}>
                            {data.tsne_data.map((pt: any, i: number) => (
                              <Cell key={i} fill={CLUSTER_COLORS[pt.cluster_id % CLUSTER_COLORS.length]} />
                            ))}
                          </Scatter>
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Cluster Size Distribution</CardTitle>
                  <CardDescription>Ticket count per cluster, sorted by volume</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.clusters.slice(0, 15)}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                        <XAxis dataKey="cluster_name" tick={{ fontSize: 8 }} interval={0} angle={-30} textAnchor="end" height={80} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(value: any) => [typeof value === "number" ? value.toLocaleString() : value, "Tickets"]} />
                        <Bar dataKey="ticket_count" radius={[4, 4, 0, 0]}>
                          {data.clusters.slice(0, 15).map((_: any, i: number) => (
                            <Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ═══ ALL CLUSTERS ═══ */}
          {activeTab === "clusters" && (
            <div className="flex flex-col gap-4">
              {data.clusters.map((cluster: any, i: number) => {
                const TrendIcon = TREND_ICONS[cluster.trend] || Minus;
                const isExpanded = expandedCluster === cluster.cluster_id;
                return (
                  <Card key={cluster.cluster_id} className="cursor-pointer hover:border-primary/30 transition-colors"
                    onClick={() => setExpandedCluster(isExpanded ? null : cluster.cluster_id)}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-3 h-10 rounded-sm" style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                          <div>
                            <h3 className="text-base font-semibold text-foreground">{cluster.cluster_name}</h3>
                            <p className="text-xs text-muted-foreground">Cluster {cluster.cluster_id} · {cluster.team}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] gap-1"><TrendIcon className="w-3 h-3" /> {cluster.trend}</Badge>
                          <Badge className={EFFORT_COLORS[cluster.solution.effort] + " text-[10px]"}>{cluster.solution.effort} effort</Badge>
                          <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                        </div>
                      </div>

                      <div className="grid grid-cols-6 gap-4">
                        {[
                          { label: "Tickets", value: cluster.ticket_count.toLocaleString(), sub: `${cluster.pct_of_total}%` },
                          { label: "Avg MTTR", value: `${cluster.mttr.avg_hours}h` },
                          { label: "Automatable", value: `${cluster.automation.automatable_pct}%` },
                          { label: "Annual Cost", value: `₹${cluster.annual_cost_lakhs}L` },
                          { label: "Savings", value: `₹${cluster.solution.annual_savings_lakhs}L`, highlight: true },
                          { label: "Reassignments", value: cluster.quality.avg_reassignments },
                        ].map((m) => (
                          <div key={m.label}>
                            <p className="text-[10px] text-muted-foreground uppercase">{m.label}</p>
                            <p className={`text-sm font-bold ${m.highlight ? "text-primary" : ""}`}>{m.value}</p>
                            {m.sub && <p className="text-[10px] text-muted-foreground">{m.sub}</p>}
                          </div>
                        ))}
                      </div>

                      <div className="flex flex-wrap gap-1 mt-3">
                        {cluster.keywords.map((kw: string) => (
                          <span key={kw} className="text-[10px] bg-muted px-1.5 py-0.5 rounded">{kw}</span>
                        ))}
                      </div>

                      {isExpanded && (
                        <div className="mt-4 pt-4 border-t border-border space-y-4">
                          <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4">
                            <p className="text-[10px] font-semibold text-red-600 uppercase mb-1">Problem Statement</p>
                            <p className="text-sm text-foreground">{cluster.problem_statement}</p>
                          </div>
                          <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-4">
                            <p className="text-[10px] font-semibold text-green-600 uppercase mb-1">Recommended Solution</p>
                            <p className="text-sm text-foreground">{cluster.solution.name} — {cluster.solution.reduction_pct}% reduction</p>
                            <p className="text-xs text-muted-foreground mt-1">Timeline: {cluster.solution.timeline} · Savings: ₹{cluster.solution.annual_savings_lakhs}L/year</p>
                          </div>
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Top Assignment Groups</p>
                            {cluster.assignment_groups.map((ag: any) => (
                              <div key={ag.group} className="flex justify-between text-xs py-1">
                                <span className="text-foreground">{ag.group}</span>
                                <span className="text-muted-foreground">{ag.count} tickets</span>
                              </div>
                            ))}
                          </div>
                          {cluster.monthly_trend.length > 1 && (
                            <div>
                              <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Monthly Trend</p>
                              <div className="h-40">
                                <ResponsiveContainer width="100%" height="100%">
                                  <AreaChart data={cluster.monthly_trend}>
                                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                                    <XAxis dataKey="month" tick={{ fontSize: 9 }} />
                                    <YAxis tick={{ fontSize: 9 }} />
                                    <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                                    <Area type="monotone" dataKey="count" stroke={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} fillOpacity={0.15} />
                                  </AreaChart>
                                </ResponsiveContainer>
                              </div>
                            </div>
                          )}
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Sample Tickets</p>
                            {cluster.sample_tickets.map((t: any) => (
                              <div key={t.ticket_id} className="flex items-start gap-2 text-xs bg-muted/50 p-2 rounded mb-1">
                                <span className="font-mono text-[10px] text-primary shrink-0">{t.ticket_id}</span>
                                <span className="text-foreground">{t.short_description}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* ═══ PROBLEMS ═══ */}
          {activeTab === "problems" && (
            <div className="flex flex-col gap-4">
              <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-5 mb-2">
                <p className="text-lg font-semibold text-red-600">{data.clusters.length} Problem Areas Identified</p>
                <p className="text-sm text-muted-foreground mt-1">Sorted by annual cost impact — highest first</p>
              </div>
              {[...data.clusters].sort((a: any, b: any) => b.annual_cost - a.annual_cost).map((c: any, i: number) => (
                <Card key={c.cluster_id} className="gap-0">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-primary bg-primary/10 w-8 h-8 flex items-center justify-center rounded">{i + 1}</span>
                        <h3 className="text-base font-semibold text-foreground">{c.cluster_name}</h3>
                      </div>
                      <Badge variant="outline">₹{c.annual_cost_lakhs}L/yr</Badge>
                    </div>
                    <p className="text-sm text-foreground mb-2">{c.problem_statement}</p>
                    <p className="text-xs text-muted-foreground">{c.impact}</p>
                    <div className="flex gap-6 mt-3 pt-3 border-t border-border text-xs">
                      <span><span className="text-muted-foreground">Team: </span><span className="font-medium">{c.team}</span></span>
                      <span><span className="text-muted-foreground">Reassign avg: </span><span className="font-medium">{c.quality.avg_reassignments}</span></span>
                      <span><span className="text-muted-foreground">Reopen avg: </span><span className="font-medium">{c.quality.avg_reopens}</span></span>
                      <span><span className="text-muted-foreground">Solution: </span><span className="font-medium text-primary">{c.solution.name}</span></span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* ═══ SOLUTIONS & ROI ═══ */}
          {activeTab === "solutions" && (
            <div className="flex flex-col gap-8">
              <Card>
                <CardHeader>
                  <CardTitle>Cumulative ROI — Implementation Priority</CardTitle>
                  <CardDescription>Green = Quick Win, Yellow = Medium, Red = High effort</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={[...data.clusters].sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings).slice(0, 15).map((c: any) => ({
                        name: c.cluster_name.length > 20 ? c.cluster_name.slice(0, 20) + "..." : c.cluster_name,
                        savings: c.solution.annual_savings_lakhs, effort: c.solution.effort,
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 8 }} angle={-30} textAnchor="end" height={80} />
                        <YAxis tick={{ fontSize: 10 }} label={{ value: "₹ Lakhs/yr", angle: -90, position: "insideLeft", fontSize: 10 }} />
                        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} formatter={(value: any) => [`₹${value}L/yr`, "Savings"]} />
                        <Bar dataKey="savings" radius={[4, 4, 0, 0]}>
                          {[...data.clusters].sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings).slice(0, 15).map((c: any, i: number) => (
                            <Cell key={i} fill={c.solution.effort === "Low" ? "#10B981" : c.solution.effort === "Medium" ? "#F59E0B" : "#EF4444"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Solution Recommendations</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>#</TableHead>
                        <TableHead>Problem</TableHead>
                        <TableHead>Tickets</TableHead>
                        <TableHead>Solution</TableHead>
                        <TableHead>Effort</TableHead>
                        <TableHead>Timeline</TableHead>
                        <TableHead>Reduction</TableHead>
                        <TableHead>Savings/yr</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[...data.clusters].sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings).map((c: any, i: number) => (
                        <TableRow key={c.cluster_id}>
                          <TableCell className="font-bold text-primary">{i + 1}</TableCell>
                          <TableCell className="font-medium text-xs max-w-[200px] truncate">{c.cluster_name}</TableCell>
                          <TableCell className="text-xs">{c.ticket_count.toLocaleString()}</TableCell>
                          <TableCell className="text-xs">{c.solution.name}</TableCell>
                          <TableCell><Badge variant="outline" className={`text-[10px] ${EFFORT_COLORS[c.solution.effort]}`}>{c.solution.effort}</Badge></TableCell>
                          <TableCell className="text-xs">{c.solution.timeline}</TableCell>
                          <TableCell className="text-xs font-mono">{c.solution.reduction_pct}%</TableCell>
                          <TableCell className="text-xs font-semibold text-primary">₹{c.solution.annual_savings_lakhs}L</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ═══ TEAM VIEW ═══ */}
          {activeTab === "teams" && (
            <div className="flex flex-col gap-8">
              <Card>
                <CardHeader><CardTitle>Ticket Distribution by Team</CardTitle></CardHeader>
                <CardContent>
                  <div className="flex items-center gap-10">
                    <div className="w-64 h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={data.team_summary.map((t: any, i: number) => ({ name: t.team, value: t.ticket_count, fill: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }))}
                            cx="50%" cy="50%" innerRadius={55} outerRadius={110} paddingAngle={2} dataKey="value">
                            {data.team_summary.map((_: any, i: number) => (<Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />))}
                          </Pie>
                          <Tooltip formatter={(value: any) => [typeof value === "number" ? value.toLocaleString() : value, "Tickets"]} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex-1 space-y-3">
                      {data.team_summary.map((team: any, i: number) => (
                        <div key={team.team} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                            <span className="text-sm text-foreground">{team.team}</span>
                          </div>
                          <span className="text-sm font-semibold">{team.ticket_count.toLocaleString()} ({team.pct_of_total}%)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {data.team_summary.map((team: any, i: number) => (
                <Card key={team.team}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-3 h-10 rounded-sm" style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                        <div>
                          <CardTitle>{team.team}</CardTitle>
                          <CardDescription>{team.cluster_count} clusters · {team.ticket_count.toLocaleString()} tickets · {team.pct_of_total}%</CardDescription>
                        </div>
                      </div>
                      <Badge className="bg-primary/10 text-primary text-sm">₹{team.annual_savings_lakhs}L savings</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-6 mb-4">
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase">Total MTTR Hours</p>
                        <p className="text-lg font-bold">{team.total_mttr_hours.toLocaleString()}h</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase">Automatable Tickets</p>
                        <p className="text-lg font-bold">{team.automatable_tickets.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase">Clusters</p>
                        <p className="text-lg font-bold">{team.cluster_ids.join(", ")}</p>
                      </div>
                    </div>
                    <div className="space-y-1 pt-4 border-t border-border">
                      {data.clusters.filter((c: any) => team.cluster_ids.includes(c.cluster_id)).map((c: any) => (
                        <div key={c.cluster_id} className="flex items-center justify-between text-sm py-1.5">
                          <span className="text-foreground">{c.cluster_name}</span>
                          <div className="flex items-center gap-4">
                            <span className="text-muted-foreground">{c.ticket_count.toLocaleString()} tickets</span>
                            <span className="font-semibold text-primary">₹{c.solution.annual_savings_lakhs}L</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* ═══ DYNAMIC GRAPH ═══ */}
          {activeTab === "charts" && (
            <div className="flex flex-col gap-8">
              <Card>
                <CardHeader>
                  <CardTitle>Dynamic Graph Builder</CardTitle>
                  <CardDescription>Choose axes and grouping to generate custom charts from real ticket data</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-6 mb-6">
                    <div>
                      <label className="text-xs text-muted-foreground uppercase block mb-1.5">X-Axis</label>
                      <select className="w-full text-sm border border-border rounded-md px-3 py-2 bg-background" value={chartConfig.x_axis} onChange={(e) => setChartConfig({ ...chartConfig, x_axis: e.target.value })}>
                        <option value="cluster_id">Cluster</option>
                        <option value="priority">Priority</option>
                        <option value="assignment_group">Assignment Group</option>
                        <option value="l1_category">L1 Category</option>
                        <option value="channel">Channel</option>
                        <option value="month">Month</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground uppercase block mb-1.5">Y-Axis</label>
                      <select className="w-full text-sm border border-border rounded-md px-3 py-2 bg-background" value={chartConfig.y_axis} onChange={(e) => setChartConfig({ ...chartConfig, y_axis: e.target.value })}>
                        <option value="count">Ticket Count</option>
                        <option value="avg_mttr">Avg MTTR (hours)</option>
                        <option value="total_mttr">Total MTTR (hours)</option>
                        <option value="automation_score">Automation Score</option>
                        <option value="reassignment_count">Avg Reassignments</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground uppercase block mb-1.5">Group By</label>
                      <select className="w-full text-sm border border-border rounded-md px-3 py-2 bg-background" value={chartConfig.group_by} onChange={(e) => setChartConfig({ ...chartConfig, group_by: e.target.value })}>
                        <option value="">None</option>
                        <option value="priority">Priority</option>
                        <option value="aiops_automation_status">Automation Status</option>
                      </select>
                    </div>
                  </div>
                  <Button onClick={fetchDynamicChart} className="gap-2">
                    <BarChart3 className="w-4 h-4" /> Generate Chart
                  </Button>
                </CardContent>
              </Card>

              {dynamicChartData && (
                <Card>
                  <CardHeader>
                    <CardTitle>{chartConfig.y_axis.replace(/_/g, " ")} by {chartConfig.x_axis.replace(/_/g, " ")}</CardTitle>
                    <CardDescription>{dynamicChartData.total_points} data points</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-96">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={dynamicChartData.chart_data.slice(0, 30)}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                          <XAxis dataKey="x" tick={{ fontSize: 8 }} angle={-30} textAnchor="end" height={80} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                          <Legend />
                          {dynamicChartData.groups.map((group: string, i: number) => (
                            <Bar key={group} dataKey={group} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} radius={[3, 3, 0, 0]} stackId={chartConfig.group_by ? "stack" : undefined} />
                          ))}
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Quick Templates</CardTitle>
                  <CardDescription>One-click pre-built analysis from real data</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: "Tickets by Cluster", x: "cluster_id", y: "count", g: "" },
                      { label: "MTTR by Priority", x: "priority", y: "avg_mttr", g: "" },
                      { label: "Volume by Month", x: "month", y: "count", g: "" },
                      { label: "Tickets by Team × Priority", x: "assignment_group", y: "count", g: "priority" },
                      { label: "Automation Score by Category", x: "l1_category", y: "automation_score", g: "" },
                      { label: "Reassignments by Team", x: "assignment_group", y: "reassignment_count", g: "" },
                    ].map((t) => (
                      <Button key={t.label} variant="outline" className="justify-start text-sm h-auto py-3" onClick={() => {
                        setChartConfig({ x_axis: t.x, y_axis: t.y, group_by: t.g });
                        setTimeout(fetchDynamicChart, 100);
                      }}>
                        <BarChart3 className="w-4 h-4 mr-2 text-primary" /> {t.label}
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ═══ CXO SUMMARY ═══ */}
          {activeTab === "cxo" && (
            <div className="flex flex-col gap-8">
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="p-8">
                  <p className="text-xl font-semibold text-foreground leading-relaxed">{data.cxo_summary.headline}</p>
                </CardContent>
              </Card>

              <div className="grid grid-cols-3 gap-6">
                <Card className="py-8 gap-2">
                  <CardContent className="px-6 py-0 text-center">
                    <p className="text-4xl font-bold text-primary">₹{data.cxo_summary.total_annual_savings_cr}Cr</p>
                    <p className="text-sm text-muted-foreground mt-2">Annual Savings Potential</p>
                  </CardContent>
                </Card>
                <Card className="py-8 gap-2">
                  <CardContent className="px-6 py-0 text-center">
                    <p className="text-4xl font-bold text-foreground">{data.cxo_summary.total_clusters}</p>
                    <p className="text-sm text-muted-foreground mt-2">Distinct Problem Areas</p>
                  </CardContent>
                </Card>
                <Card className="py-8 gap-2">
                  <CardContent className="px-6 py-0 text-center">
                    <p className="text-4xl font-bold text-foreground">{data.cxo_summary.quick_wins?.length || 0}</p>
                    <p className="text-sm text-muted-foreground mt-2">Quick Wins (Q1)</p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Top 5 Cost Drivers</CardTitle>
                  <CardDescription>Highest-impact problems requiring immediate attention</CardDescription>
                </CardHeader>
                <CardContent>
                  {data.cxo_summary.top_5_problems.map((prob: any, i: number) => (
                    <div key={i} className={`flex items-center justify-between py-4 ${i < 4 ? "border-b border-border" : ""}`}>
                      <div className="flex items-center gap-4">
                        <span className="text-2xl font-bold text-primary">{i + 1}</span>
                        <div>
                          <p className="text-base font-semibold text-foreground">{prob.cluster_name}</p>
                          <p className="text-xs text-muted-foreground">{prob.ticket_count.toLocaleString()} tickets · ₹{prob.annual_cost_lakhs}L/yr cost</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-primary">₹{prob.savings_lakhs}L</p>
                        <p className="text-xs text-muted-foreground">{prob.solution} · {prob.effort} effort</p>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {data.cxo_summary.quick_wins?.length > 0 && (
                <Card className="border-green-500/30">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-green-600" /> Quick Wins — Low Effort, High Impact
                    </CardTitle>
                    <CardDescription>Can be implemented in Q1 with minimal investment</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {data.cxo_summary.quick_wins.map((qw: any) => (
                        <div key={qw.cluster_id} className="flex items-center justify-between bg-green-500/5 rounded-lg p-4">
                          <div>
                            <p className="text-base font-medium text-foreground">{qw.cluster_name}</p>
                            <p className="text-xs text-muted-foreground">{qw.ticket_count.toLocaleString()} tickets · {qw.solution.name}</p>
                          </div>
                          <Badge className="bg-green-500/10 text-green-600 text-sm">₹{qw.solution.annual_savings_lakhs}L/yr</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function BERTPageInner() {
  const searchParams = useSearchParams();
  const uploadId = Number(searchParams.get("uploadId")) || 0;
  if (!uploadId) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <p className="text-muted-foreground">No upload ID provided</p>
      </div>
    );
  }
  return <BERTFullView uploadId={uploadId} />;
}

export default function BERTPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-screen bg-background">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">Loading BERT Intelligence...</p>
          </div>
        </div>
      }
    >
      <BERTPageInner />
    </Suspense>
  );
}