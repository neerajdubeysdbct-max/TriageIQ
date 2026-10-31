"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  X,
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Users,
  Clock,
  AlertTriangle,
  ChevronRight,
  ExternalLink,
  BarChart3,
  Target,
  DollarSign,
  RefreshCw,
} from "lucide-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  AreaChart,
  Area,
  Legend,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

// 20 distinct colors for clusters
const CLUSTER_COLORS = [
  "#10B981", "#6366F1", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
  "#84CC16", "#E11D48", "#0EA5E9", "#D946EF", "#22D3EE",
  "#A855F7", "#F43F5E", "#2DD4BF", "#FB923C", "#818CF8",
  "#34D399", "#818CF8", "#FBBF24", "#F87171", "#A78BFA",
];

const TREND_ICONS: any = {
  increasing: TrendingUp,
  decreasing: TrendingDown,
  stable: Minus,
};

const EFFORT_COLORS: Record<string, string> = {
  Low: "bg-green-500/10 text-green-600 border-green-500/20",
  Medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  High: "bg-red-500/10 text-red-600 border-red-500/20",
};

interface BERTDrillDownProps {
  uploadId: number;
  isOpen: boolean;
  onClose: () => void;
}

type TabId = "overview" | "clusters" | "problems" | "solutions" | "teams" | "charts" | "cxo";

export default function BERTDrillDown({ uploadId, isOpen, onClose }: BERTDrillDownProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);
  const [chartConfig, setChartConfig] = useState({
    x_axis: "cluster_id",
    y_axis: "count",
    group_by: "",
  });
  const [dynamicChartData, setDynamicChartData] = useState<any>(null);

  useEffect(() => {
    if (isOpen && uploadId) fetchData();
  }, [isOpen, uploadId]);

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
        x_axis: chartConfig.x_axis,
        y_axis: chartConfig.y_axis,
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

  if (!isOpen) return null;

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "clusters", label: `All ${data?.model_info?.total_clusters || ""} Clusters` },
    { id: "problems", label: "Problems" },
    { id: "solutions", label: "Solutions & ROI" },
    { id: "teams", label: "Team View" },
    { id: "charts", label: "Dynamic Graph" },
    { id: "cxo", label: "CXO Summary" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="w-[30%] bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="w-[70%] bg-background border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
              <Brain className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">BERT Semantic Analysis</h2>
              <p className="text-xs text-muted-foreground">
                {data?.model_info?.total_clusters || "—"} clusters · {data?.model_info?.total_tickets?.toLocaleString() || "—"} tickets · {data?.model_info?.model || "all-MiniLM-L6-v2"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => {
                window.open(`/dashboard/advanced/bert?uploadId=${uploadId}`, '_blank');
                }}>
                <ExternalLink className="w-3 h-3" />
                Open in Tab
            </Button>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 px-6 border-b border-border bg-card overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">Analyzing clusters...</p>
                </div>
              </div>
            ) : !data ? (
              <div className="text-center text-muted-foreground py-20">No data available</div>
            ) : (
              <>
                {/* ═══ OVERVIEW TAB ═══ */}
                {activeTab === "overview" && (
                  <div className="flex flex-col gap-6">
                    {/* Quick stats */}
                    <div className="grid grid-cols-4 gap-4">
                      {[
                        { label: "Total Clusters", value: data.model_info.total_clusters, icon: Brain },
                        { label: "Tickets Analyzed", value: data.model_info.total_tickets.toLocaleString(), icon: BarChart3 },
                        { label: "Total Savings", value: `₹${data.cxo_summary.total_annual_savings_cr}Cr/yr`, icon: DollarSign },
                        { label: "Quick Wins", value: data.cxo_summary.quick_wins?.length || 0, icon: Zap },
                      ].map((stat) => (
                        <Card key={stat.label} className="py-4 gap-2">
                          <CardContent className="px-4 py-0">
                            <stat.icon className="w-4 h-4 text-primary mb-2" />
                            <p className="text-xl font-bold text-foreground">{stat.value}</p>
                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{stat.label}</p>
                          </CardContent>
                        </Card>
                      ))}
                    </div>

                    {/* t-SNE Scatter Plot */}
                    {data.tsne_data && data.tsne_data.length > 0 && (
                      <Card>
                        <CardHeader>
                          <CardTitle>Ticket Cluster Map (t-SNE)</CardTitle>
                          <CardDescription>
                            Each dot is a ticket, color = cluster. Nearby dots are semantically similar.
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="h-80">
                            <ResponsiveContainer width="100%" height="100%">
                              <ScatterChart>
                                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                                <XAxis dataKey="x" tick={{ fontSize: 9 }} name="t-SNE 1" />
                                <YAxis dataKey="y" tick={{ fontSize: 9 }} name="t-SNE 2" />
                                <Tooltip
                                  content={({ payload }: any) => {
                                    if (!payload?.[0]?.payload) return null;
                                    const p = payload[0].payload;
                                    return (
                                      <div className="bg-popover border border-border rounded-lg p-3 shadow-lg max-w-xs">
                                        <p className="text-xs font-semibold text-foreground">{p.ticket_id}</p>
                                        <p className="text-[11px] text-muted-foreground mt-1">{p.short_description}</p>
                                        <p className="text-[10px] text-primary mt-1">Cluster {p.cluster_id}</p>
                                      </div>
                                    );
                                  }}
                                />
                                <Scatter data={data.tsne_data} fillOpacity={0.6}>
                                  {data.tsne_data.map((point: any, i: number) => (
                                    <Cell
                                      key={i}
                                      fill={CLUSTER_COLORS[point.cluster_id % CLUSTER_COLORS.length]}
                                    />
                                  ))}
                                </Scatter>
                              </ScatterChart>
                            </ResponsiveContainer>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Cluster Size Distribution */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Cluster Size Distribution</CardTitle>
                        <CardDescription>Ticket count per cluster, sorted by volume</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data.clusters.slice(0, 15)}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                              <XAxis
                                dataKey="cluster_name"
                                tick={{ fontSize: 8 }}
                                interval={0}
                                angle={-30}
                                textAnchor="end"
                                height={60}
                              />
                              <YAxis tick={{ fontSize: 10 }} />
                              <Tooltip
                                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E5E7EB" }}
                                formatter={(value: any) => [typeof value === "number" ? value.toLocaleString() : value, "Tickets"]}
                              />
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

                {/* ═══ ALL CLUSTERS TAB ═══ */}
                {activeTab === "clusters" && (
                  <div className="flex flex-col gap-4">
                    {data.clusters.map((cluster: any, i: number) => {
                      const TrendIcon = TREND_ICONS[cluster.trend] || Minus;
                      const isExpanded = expandedCluster === cluster.cluster_id;
                      return (
                        <Card
                          key={cluster.cluster_id}
                          className="cursor-pointer hover:border-primary/30 transition-colors"
                          onClick={() => setExpandedCluster(isExpanded ? null : cluster.cluster_id)}
                        >
                          <CardContent className="p-4">
                            {/* Cluster header */}
                            <div className="flex items-start justify-between mb-3">
                              <div className="flex items-center gap-3">
                                <div
                                  className="w-3 h-8 rounded-sm"
                                  style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
                                />
                                <div>
                                  <h3 className="text-sm font-semibold text-foreground">
                                    {cluster.cluster_name}
                                  </h3>
                                  <p className="text-[11px] text-muted-foreground">
                                    Cluster {cluster.cluster_id} · {cluster.team}
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-[10px] gap-1">
                                  <TrendIcon className="w-3 h-3" />
                                  {cluster.trend}
                                </Badge>
                                <Badge className={EFFORT_COLORS[cluster.solution.effort] + " text-[10px]"}>
                                  {cluster.solution.effort} effort
                                </Badge>
                                <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                              </div>
                            </div>

                            {/* Quick metrics */}
                            <div className="grid grid-cols-5 gap-3">
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase">Tickets</p>
                                <p className="text-sm font-bold">{cluster.ticket_count.toLocaleString()}</p>
                                <p className="text-[10px] text-muted-foreground">{cluster.pct_of_total}%</p>
                              </div>
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase">Avg MTTR</p>
                                <p className="text-sm font-bold">{cluster.mttr.avg_hours}h</p>
                              </div>
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase">Automatable</p>
                                <p className="text-sm font-bold">{cluster.automation.automatable_pct}%</p>
                              </div>
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase">Annual Cost</p>
                                <p className="text-sm font-bold">₹{cluster.annual_cost_lakhs}L</p>
                              </div>
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase">Savings</p>
                                <p className="text-sm font-bold text-primary">₹{cluster.solution.annual_savings_lakhs}L</p>
                              </div>
                            </div>

                            {/* Keywords */}
                            <div className="flex flex-wrap gap-1 mt-3">
                              {cluster.keywords.map((kw: string) => (
                                <span key={kw} className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                                  {kw}
                                </span>
                              ))}
                            </div>

                            {/* Expanded content */}
                            {isExpanded && (
                              <div className="mt-4 pt-4 border-t border-border space-y-4">
                                {/* Problem statement */}
                                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                                  <p className="text-[10px] font-semibold text-red-600 uppercase mb-1">Problem</p>
                                  <p className="text-xs text-foreground">{cluster.problem_statement}</p>
                                </div>

                                {/* Solution */}
                                <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
                                  <p className="text-[10px] font-semibold text-green-600 uppercase mb-1">Solution</p>
                                  <p className="text-xs text-foreground">
                                    {cluster.solution.name} — {cluster.solution.reduction_pct}% reduction expected
                                  </p>
                                  <p className="text-[10px] text-muted-foreground mt-1">
                                    Timeline: {cluster.solution.timeline} · Savings: ₹{cluster.solution.annual_savings_lakhs}L/year
                                  </p>
                                </div>

                                {/* Assignment groups */}
                                <div>
                                  <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Top Assignment Groups</p>
                                  <div className="space-y-1">
                                    {cluster.assignment_groups.map((ag: any) => (
                                      <div key={ag.group} className="flex justify-between text-xs">
                                        <span className="text-foreground">{ag.group}</span>
                                        <span className="text-muted-foreground">{ag.count} tickets</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                {/* Monthly trend */}
                                {cluster.monthly_trend.length > 1 && (
                                  <div>
                                    <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Monthly Trend</p>
                                    <div className="h-32">
                                      <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={cluster.monthly_trend}>
                                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                                          <XAxis dataKey="month" tick={{ fontSize: 8 }} />
                                          <YAxis tick={{ fontSize: 9 }} />
                                          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                                          <Area
                                            type="monotone"
                                            dataKey="count"
                                            stroke={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
                                            fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
                                            fillOpacity={0.15}
                                          />
                                        </AreaChart>
                                      </ResponsiveContainer>
                                    </div>
                                  </div>
                                )}

                                {/* Sample tickets */}
                                <div>
                                  <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">Sample Tickets</p>
                                  <div className="space-y-1">
                                    {cluster.sample_tickets.map((t: any) => (
                                      <div key={t.ticket_id} className="flex items-start gap-2 text-xs bg-muted/50 p-2 rounded">
                                        <span className="font-mono text-[10px] text-primary shrink-0">{t.ticket_id}</span>
                                        <span className="text-foreground">{t.short_description}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}

                {/* ═══ PROBLEMS TAB ═══ */}
                {activeTab === "problems" && (
                  <div className="flex flex-col gap-4">
                    <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4 mb-2">
                      <p className="text-sm font-semibold text-red-600">
                        {data.clusters.length} Problem Areas Identified
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Sorted by annual cost impact — highest first
                      </p>
                    </div>
                    {[...data.clusters]
                      .sort((a: any, b: any) => b.annual_cost - a.annual_cost)
                      .map((cluster: any, i: number) => (
                        <Card key={cluster.cluster_id} className="gap-0">
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-primary bg-primary/10 w-6 h-6 flex items-center justify-center rounded">
                                  {i + 1}
                                </span>
                                <h3 className="text-sm font-semibold text-foreground">
                                  {cluster.cluster_name}
                                </h3>
                              </div>
                              <Badge variant="outline" className="text-[10px]">
                                ₹{cluster.annual_cost_lakhs}L/yr
                              </Badge>
                            </div>
                            <p className="text-xs text-foreground mb-2">{cluster.problem_statement}</p>
                            <p className="text-[11px] text-muted-foreground">{cluster.impact}</p>
                            <div className="flex gap-4 mt-3 pt-3 border-t border-border">
                              <div className="text-[10px]">
                                <span className="text-muted-foreground">Team: </span>
                                <span className="font-medium text-foreground">{cluster.team}</span>
                              </div>
                              <div className="text-[10px]">
                                <span className="text-muted-foreground">Reassign avg: </span>
                                <span className="font-medium text-foreground">{cluster.quality.avg_reassignments}</span>
                              </div>
                              <div className="text-[10px]">
                                <span className="text-muted-foreground">Reopen avg: </span>
                                <span className="font-medium text-foreground">{cluster.quality.avg_reopens}</span>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                  </div>
                )}

                {/* ═══ SOLUTIONS & ROI TAB ═══ */}
                {activeTab === "solutions" && (
                  <div className="flex flex-col gap-6">
                    {/* Cumulative savings chart */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Cumulative ROI — If You Implement Top to Bottom</CardTitle>
                        <CardDescription>
                          Each bar adds to total savings. Quick wins (green) can be done in Q1.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                              data={[...data.clusters]
                                .sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings)
                                .slice(0, 12)
                                .map((c: any) => ({
                                  name: c.cluster_name.length > 15 ? c.cluster_name.slice(0, 15) + "..." : c.cluster_name,
                                  savings: c.solution.annual_savings_lakhs,
                                  effort: c.solution.effort,
                                }))}
                            >
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                              <XAxis dataKey="name" tick={{ fontSize: 8 }} angle={-30} textAnchor="end" height={60} />
                              <YAxis tick={{ fontSize: 10 }} label={{ value: "₹ Lakhs/yr", angle: -90, position: "insideLeft", fontSize: 10 }} />
                              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} formatter={(value: any) => [`₹${value}L/yr`, "Savings"]} />
                              <Bar dataKey="savings" radius={[4, 4, 0, 0]}>
                                {[...data.clusters]
                                  .sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings)
                                  .slice(0, 12)
                                  .map((c: any, i: number) => (
                                    <Cell
                                      key={i}
                                      fill={c.solution.effort === "Low" ? "#10B981" : c.solution.effort === "Medium" ? "#F59E0B" : "#EF4444"}
                                    />
                                  ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Solution table */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Solution Recommendations</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>#</TableHead>
                              <TableHead>Problem</TableHead>
                              <TableHead>Solution</TableHead>
                              <TableHead>Effort</TableHead>
                              <TableHead>Timeline</TableHead>
                              <TableHead>Reduction</TableHead>
                              <TableHead>Savings</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {[...data.clusters]
                              .sort((a: any, b: any) => b.solution.annual_savings - a.solution.annual_savings)
                              .map((c: any, i: number) => (
                                <TableRow key={c.cluster_id}>
                                  <TableCell className="font-bold text-primary">{i + 1}</TableCell>
                                  <TableCell className="font-medium text-foreground text-xs max-w-[150px] truncate">
                                    {c.cluster_name}
                                  </TableCell>
                                  <TableCell className="text-xs">{c.solution.name}</TableCell>
                                  <TableCell>
                                    <Badge variant="outline" className={`text-[10px] ${EFFORT_COLORS[c.solution.effort]}`}>
                                      {c.solution.effort}
                                    </Badge>
                                  </TableCell>
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

                {/* ═══ TEAM VIEW TAB ═══ */}
                {activeTab === "teams" && (
                  <div className="flex flex-col gap-6">
                    {/* Team distribution pie */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Ticket Distribution by Team</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center gap-8">
                          <div className="w-48 h-48">
                            <ResponsiveContainer width="100%" height="100%">
                              <PieChart>
                                <Pie
                                  data={data.team_summary.map((t: any, i: number) => ({
                                    name: t.team,
                                    value: t.ticket_count,
                                    fill: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
                                  }))}
                                  cx="50%"
                                  cy="50%"
                                  innerRadius={40}
                                  outerRadius={80}
                                  paddingAngle={2}
                                  dataKey="value"
                                >
                                  {data.team_summary.map((_: any, i: number) => (
                                    <Cell key={i} fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                                  ))}
                                </Pie>
                                <Tooltip formatter={(value: any) => [typeof value === "number" ? value.toLocaleString() : value, "Tickets"]} />
                              </PieChart>
                            </ResponsiveContainer>
                          </div>
                          <div className="flex-1 space-y-2">
                            {data.team_summary.map((team: any, i: number) => (
                              <div key={team.team} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                                  <span className="text-xs text-foreground">{team.team}</span>
                                </div>
                                <span className="text-xs font-semibold">{team.ticket_count.toLocaleString()} ({team.pct_of_total}%)</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Per-team cards */}
                    {data.team_summary.map((team: any, i: number) => (
                      <Card key={team.team}>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-8 rounded-sm" style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }} />
                              <div>
                                <CardTitle>{team.team}</CardTitle>
                                <CardDescription>
                                  {team.cluster_count} clusters · {team.ticket_count.toLocaleString()} tickets · {team.pct_of_total}% of total
                                </CardDescription>
                              </div>
                            </div>
                            <Badge className="bg-primary/10 text-primary text-xs">
                              ₹{team.annual_savings_lakhs}L savings potential
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-3 gap-4 mb-3">
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase">Total MTTR Hours</p>
                              <p className="text-sm font-bold">{team.total_mttr_hours.toLocaleString()}h</p>
                            </div>
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase">Automatable</p>
                              <p className="text-sm font-bold">{team.automatable_tickets.toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase">Clusters</p>
                              <p className="text-sm font-bold">{team.cluster_ids.join(", ")}</p>
                            </div>
                          </div>
                          {/* Show clusters belonging to this team */}
                          <div className="space-y-1 mt-3 pt-3 border-t border-border">
                            {data.clusters
                              .filter((c: any) => team.cluster_ids.includes(c.cluster_id))
                              .map((c: any) => (
                                <div key={c.cluster_id} className="flex items-center justify-between text-xs py-1">
                                  <span className="text-foreground">{c.cluster_name}</span>
                                  <div className="flex items-center gap-3">
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

                {/* ═══ DYNAMIC GRAPH TAB ═══ */}
                {activeTab === "charts" && (
                  <div className="flex flex-col gap-6">
                    <Card>
                      <CardHeader>
                        <CardTitle>Dynamic Graph Builder</CardTitle>
                        <CardDescription>Choose axes and grouping to generate custom charts from real data</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div>
                            <label className="text-[10px] text-muted-foreground uppercase block mb-1">X-Axis</label>
                            <select
                              className="w-full text-xs border border-border rounded-md px-2 py-1.5 bg-background"
                              value={chartConfig.x_axis}
                              onChange={(e) => setChartConfig({ ...chartConfig, x_axis: e.target.value })}
                            >
                              <option value="cluster_id">Cluster</option>
                              <option value="priority">Priority</option>
                              <option value="assignment_group">Assignment Group</option>
                              <option value="l1_category">L1 Category</option>
                              <option value="channel">Channel</option>
                              <option value="month">Month</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-muted-foreground uppercase block mb-1">Y-Axis</label>
                            <select
                              className="w-full text-xs border border-border rounded-md px-2 py-1.5 bg-background"
                              value={chartConfig.y_axis}
                              onChange={(e) => setChartConfig({ ...chartConfig, y_axis: e.target.value })}
                            >
                              <option value="count">Ticket Count</option>
                              <option value="avg_mttr">Avg MTTR (hours)</option>
                              <option value="total_mttr">Total MTTR (hours)</option>
                              <option value="automation_score">Automation Score</option>
                              <option value="reassignment_count">Avg Reassignments</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-muted-foreground uppercase block mb-1">Group By</label>
                            <select
                              className="w-full text-xs border border-border rounded-md px-2 py-1.5 bg-background"
                              value={chartConfig.group_by}
                              onChange={(e) => setChartConfig({ ...chartConfig, group_by: e.target.value })}
                            >
                              <option value="">None</option>
                              <option value="priority">Priority</option>
                              <option value="aiops_automation_status">Automation Status</option>
                            </select>
                          </div>
                        </div>
                        <Button size="sm" onClick={fetchDynamicChart} className="gap-2">
                          <BarChart3 className="w-3.5 h-3.5" />
                          Generate Chart
                        </Button>
                      </CardContent>
                    </Card>

                    {dynamicChartData && (
                      <Card>
                        <CardHeader>
                          <CardTitle>
                            {chartConfig.y_axis.replace("_", " ")} by {chartConfig.x_axis.replace("_", " ")}
                            {chartConfig.group_by ? ` (grouped by ${chartConfig.group_by.replace("_", " ")})` : ""}
                          </CardTitle>
                          <CardDescription>{dynamicChartData.total_points} data points</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="h-72">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={dynamicChartData.chart_data.slice(0, 25)}>
                                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                                <XAxis dataKey="x" tick={{ fontSize: 8 }} angle={-30} textAnchor="end" height={60} />
                                <YAxis tick={{ fontSize: 10 }} />
                                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                                <Legend />
                                {dynamicChartData.groups.map((group: string, i: number) => (
                                  <Bar
                                    key={group}
                                    dataKey={group}
                                    fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
                                    radius={[3, 3, 0, 0]}
                                    stackId={chartConfig.group_by ? "stack" : undefined}
                                  />
                                ))}
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Pre-built templates */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Quick Templates</CardTitle>
                        <CardDescription>One-click pre-built analysis</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { label: "Tickets by Cluster", x: "cluster_id", y: "count", g: "" },
                            { label: "MTTR by Priority", x: "priority", y: "avg_mttr", g: "" },
                            { label: "Volume by Month", x: "month", y: "count", g: "" },
                            { label: "Tickets by Team × Priority", x: "assignment_group", y: "count", g: "priority" },
                            { label: "Automation Score by Category", x: "l1_category", y: "automation_score", g: "" },
                            { label: "Reassignments by Team", x: "assignment_group", y: "reassignment_count", g: "" },
                          ].map((template) => (
                            <Button
                              key={template.label}
                              variant="outline"
                              size="sm"
                              className="justify-start text-xs h-auto py-2"
                              onClick={() => {
                                setChartConfig({ x_axis: template.x, y_axis: template.y, group_by: template.g });
                                setTimeout(fetchDynamicChart, 100);
                              }}
                            >
                              <BarChart3 className="w-3 h-3 mr-2 text-primary" />
                              {template.label}
                            </Button>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* ═══ CXO SUMMARY TAB ═══ */}
                {activeTab === "cxo" && (
                  <div className="flex flex-col gap-6">
                    {/* Headline */}
                    <Card className="border-primary/30 bg-primary/5">
                      <CardContent className="p-6">
                        <p className="text-lg font-semibold text-foreground leading-relaxed">
                          {data.cxo_summary.headline}
                        </p>
                      </CardContent>
                    </Card>

                    {/* Big numbers */}
                    <div className="grid grid-cols-3 gap-4">
                      <Card className="py-6 gap-2">
                        <CardContent className="px-4 py-0 text-center">
                          <p className="text-3xl font-bold text-primary">₹{data.cxo_summary.total_annual_savings_cr}Cr</p>
                          <p className="text-xs text-muted-foreground mt-1">Annual Savings Potential</p>
                        </CardContent>
                      </Card>
                      <Card className="py-6 gap-2">
                        <CardContent className="px-4 py-0 text-center">
                          <p className="text-3xl font-bold text-foreground">{data.cxo_summary.total_clusters}</p>
                          <p className="text-xs text-muted-foreground mt-1">Distinct Problem Areas</p>
                        </CardContent>
                      </Card>
                      <Card className="py-6 gap-2">
                        <CardContent className="px-4 py-0 text-center">
                          <p className="text-3xl font-bold text-foreground">{data.cxo_summary.quick_wins?.length || 0}</p>
                          <p className="text-xs text-muted-foreground mt-1">Quick Wins (Q1)</p>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Top 5 problems */}
                    <Card>
                      <CardHeader>
                        <CardTitle>Top 5 Cost Drivers</CardTitle>
                        <CardDescription>Highest-impact problems requiring immediate attention</CardDescription>
                      </CardHeader>
                      <CardContent>
                        {data.cxo_summary.top_5_problems.map((prob: any, i: number) => (
                          <div key={i} className={`flex items-center justify-between py-3 ${i < 4 ? "border-b border-border" : ""}`}>
                            <div className="flex items-center gap-3">
                              <span className="text-lg font-bold text-primary">{i + 1}</span>
                              <div>
                                <p className="text-sm font-semibold text-foreground">{prob.cluster_name}</p>
                                <p className="text-[11px] text-muted-foreground">
                                  {prob.ticket_count.toLocaleString()} tickets · ₹{prob.annual_cost_lakhs}L/yr cost
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-bold text-primary">₹{prob.savings_lakhs}L</p>
                              <p className="text-[10px] text-muted-foreground">
                                {prob.solution} · {prob.effort} effort
                              </p>
                            </div>
                          </div>
                        ))}
                      </CardContent>
                    </Card>

                    {/* Quick wins */}
                    {data.cxo_summary.quick_wins && data.cxo_summary.quick_wins.length > 0 && (
                      <Card className="border-green-500/30">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-green-600" />
                            Quick Wins — Low Effort, High Impact
                          </CardTitle>
                          <CardDescription>Can be implemented in Q1 with minimal investment</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {data.cxo_summary.quick_wins.map((qw: any) => (
                              <div key={qw.cluster_id} className="flex items-center justify-between bg-green-500/5 rounded-lg p-3">
                                <div>
                                  <p className="text-sm font-medium text-foreground">{qw.cluster_name}</p>
                                  <p className="text-[11px] text-muted-foreground">
                                    {qw.ticket_count.toLocaleString()} tickets · {qw.solution.name}
                                  </p>
                                </div>
                                <Badge className="bg-green-500/10 text-green-600">
                                  ₹{qw.solution.annual_savings_lakhs}L/yr
                                </Badge>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}