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
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Clock,
  ShieldAlert,
  BarChart3,
  RefreshCw,
  ChevronRight,
  Activity,
} from "lucide-react";
import {
  ComposedChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
  PieChart,
  Pie,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

interface PredictionsRiskProps {
  uploadId: number;
}

const RISK_COLORS: Record<string, string> = {
  critical: "#EF4444", Critical: "#EF4444",
  high: "#F97316", High: "#F97316",
  medium: "#EAB308", Medium: "#EAB308",
  low: "#22C55E", Low: "#22C55E",
};

const RISK_BG: Record<string, string> = {
  critical: "bg-red-500/10 text-red-600 border-red-500/20",
  Critical: "bg-red-500/10 text-red-600 border-red-500/20",
  high: "bg-orange-500/10 text-orange-600 border-orange-500/20",
  High: "bg-orange-500/10 text-orange-600 border-orange-500/20",
  medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  Medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  low: "bg-green-500/10 text-green-600 border-green-500/20",
  Low: "bg-green-500/10 text-green-600 border-green-500/20",
};

export default function PredictionsRisk({ uploadId }: PredictionsRiskProps) {
  const [slaData, setSlaData] = useState<any>(null);
  const [forecastData, setForecastData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState<"overview" | "tickets">("overview");

  useEffect(() => {
    if (uploadId) fetchAll();
  }, [uploadId]);

  async function fetchAll() {
    try {
      setLoading(true);
      const token = getToken();
      const headers = { Authorization: `Bearer ${token}` };

      const [slaRes, forecastRes] = await Promise.all([
        fetch(`${API}/api/predictions/${uploadId}/sla-risk`, { headers }),
        fetch(`${API}/api/predictions/${uploadId}/volume-forecast`, { headers }),
      ]);

      if (slaRes.ok) setSlaData(await slaRes.json());
      if (forecastRes.ok) setForecastData(await forecastRes.json());
    } catch (err) {
      console.error("Failed to fetch predictions:", err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Analyzing SLA risk patterns...</p>
        </div>
      </div>
    );
  }

  // ── SLA Risk Data ──
  const riskDist = slaData?.risk_distribution || {};
  const compliancePct = slaData?.sla_compliance_pct || 0;
  const atRisk = slaData?.at_risk_count || 0;
  const breached = slaData?.breached_count || 0;
  const totalTickets = slaData?.total_tickets || 0;
  const avgRisk = slaData?.avg_risk_score || 0;

  // Pie chart data for risk distribution
  const riskPieData = Object.entries(riskDist).map(([name, value]) => ({
    name,
    value: value as number,
    fill: RISK_COLORS[name] || "#94A3B8",
  }));

  // Top risk groups for table
  const topRiskGroups = slaData?.top_risk_groups || [];

  // SLA tickets sample
  const riskTickets = slaData?.tickets || [];

  // ── Forecast Data ──
  const historical = forecastData?.historical || [];
  const forecast = forecastData?.forecast || [];
  const hourlyPattern = forecastData?.hourly_pattern || [];
  const stats = forecastData?.statistics || {};
  const summary = forecastData?.summary || {};

  // Combine historical + forecast for chart
  const combinedChart = [
    ...historical.slice(-30).map((d: any) => ({
      date: d.date?.slice(5) || "",
      actual: d.volume,
      forecast: null,
      band: null,
    })),
    ...forecast.slice(0, 14).map((d: any) => ({
      date: d.date?.slice(5) || "",
      actual: null,
      forecast: d.predicted_volume,
      band: [d.confidence_lower, d.confidence_upper],
    })),
  ];

  // Hourly pattern: the busiest quarter of hours is highlighted
  const hourlyAvgs = hourlyPattern.map((h: any) => h.avg_volume).sort((a: number, b: number) => a - b);
  const peakThreshold = hourlyAvgs.length ? hourlyAvgs[Math.floor(hourlyAvgs.length * 0.75)] : Infinity;

  // Hourly pattern for bar chart
  const hourlyChartData = hourlyPattern.map((h: any) => ({
    hour: `${h.hour}:00`,
    avg: Math.round(h.avg_volume * 10) / 10,
  }));

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Historical SLA consumption of resolved tickets and a backtested volume forecast · {totalTickets.toLocaleString()} tickets
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-border overflow-hidden">
            <button
              onClick={() => setActiveView("overview")}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                activeView === "overview"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveView("tickets")}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                activeView === "tickets"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              Risk Tickets
            </button>
          </div>
          <Button variant="outline" size="sm" className="gap-2" onClick={fetchAll}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {activeView === "overview" ? (
        <>
          {/* KPI Cards Row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="py-4 gap-2">
              <CardContent className="px-4 py-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-md bg-green-500/10">
                    <ShieldAlert className="w-4 h-4 text-green-600" />
                  </div>
                  <Badge className="bg-green-500/10 text-green-600 border-green-500/20 text-[10px]">
                    {compliancePct >= 90 ? "HEALTHY" : compliancePct >= 70 ? "AT RISK" : "CRITICAL"}
                  </Badge>
                </div>
                <p className="text-2xl font-bold text-foreground">{compliancePct}%</p>
                <p className="text-[11px] text-muted-foreground">SLA Compliance</p>
              </CardContent>
            </Card>

            <Card className="py-4 gap-2">
              <CardContent className="px-4 py-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-md bg-red-500/10">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                  </div>
                  <Badge className="bg-red-500/10 text-red-600 border-red-500/20 text-[10px]">
                    BREACHED
                  </Badge>
                </div>
                <p className="text-2xl font-bold text-foreground">{breached.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground">SLA Breaches</p>
              </CardContent>
            </Card>

            <Card className="py-4 gap-2">
              <CardContent className="px-4 py-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-md bg-orange-500/10">
                    <Clock className="w-4 h-4 text-orange-600" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-foreground">{atRisk.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground">Tickets At Risk</p>
              </CardContent>
            </Card>

            <Card className="py-4 gap-2">
              <CardContent className="px-4 py-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-md bg-blue-500/10">
                    <Activity className="w-4 h-4 text-blue-600" />
                  </div>
                </div>
                <p className="text-2xl font-bold text-foreground">{avgRisk.toFixed(1)}%</p>
                <p className="text-[11px] text-muted-foreground">Avg Risk Score</p>
              </CardContent>
            </Card>
          </div>

          {/* Risk Distribution + Top Risk Groups */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Risk Distribution Pie */}
            <Card>
              <CardHeader>
                <CardTitle>Risk Distribution</CardTitle>
                <CardDescription>Ticket breakdown by SLA risk severity</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="w-48 h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={riskPieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={80}
                          paddingAngle={2}
                          dataKey="value"
                        >
                          {riskPieData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                        <Tooltip
                          
                          formatter={(value: any) => [typeof value === "number" ? value.toLocaleString() : value, "Tickets"]}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex-1 space-y-3">
                    {riskPieData.map((item) => (
                      <div key={item.name} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: item.fill }}
                          />
                          <span className="text-sm text-foreground">{item.name}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-sm font-semibold">
                            {(item.value as number).toLocaleString()}
                          </span>
                          <span className="text-[11px] text-muted-foreground ml-1.5">
                            ({((item.value as number) / totalTickets * 100).toFixed(1)}%)
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Top Risk Groups */}
            <Card>
              <CardHeader>
                <CardTitle>Top Risk Groups</CardTitle>
                <CardDescription>Priority groups with highest SLA breach rates</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Assignment Group</TableHead>
                      <TableHead>At Risk</TableHead>
                      <TableHead>Avg Risk</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topRiskGroups.slice(0, 6).map((group: any, i: number) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium text-foreground">
                          {group.group || group.priority || `Group ${i + 1}`}
                        </TableCell>
                        <TableCell>{(group.at_risk_count || group.count || 0).toLocaleString()}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-12 h-1.5 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${Math.min(group.avg_risk || 0, 100)}%`,
                                  backgroundColor:
                                    (group.avg_risk || 0) >= 70
                                      ? "#EF4444"
                                      : (group.avg_risk || 0) >= 40
                                      ? "#F97316"
                                      : "#22C55E",
                                }}
                              />
                            </div>
                            <span className="text-xs font-mono">
                              {(group.avg_risk || 0).toFixed(1)}%
                            </span>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          {/* Volume Forecast Chart */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Volume Forecast</CardTitle>
                  <CardDescription>
                    Historical ticket volume (30d) + {forecast.length}-day forecast ·{" "}
                    Trend: {stats.trend_direction === "increasing" ? "↑" : stats.trend_direction === "decreasing" ? "↓" : "→"}{" "}
                    {stats.trend_direction} ({stats.trend_slope > 0 ? "+" : ""}{stats.trend_slope?.toFixed(2)}/day)
                    {forecastData?.model && (
                      <>
                        <br />
                        Model: <b>{forecastData.model.selected.replace("_", " ")}</b>, chosen by a{" "}
                        {forecastData.model.backtest_origins}-origin backtest ({forecastData.model.selection_rule}); backtest MAE{" "}
                        {Object.entries(forecastData.model.backtest)
                          .map(([name, r]: [string, any]) => `${name.replace("_", " ")} ${r.mae}`)
                          .join(" · ")}
                        . Band: {forecastData.model.interval}.
                      </>
                    )}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-primary rounded" />
                    Actual
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-blue-400 rounded" style={{ borderStyle: "dashed" }} />
                    Forecast
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-2 bg-blue-500/10 rounded" />
                    Confidence
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={combinedChart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6B7280" }} interval={Math.max(1, Math.floor(combinedChart.length / 8))} />
                    <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} allowDecimals={false} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #E5E7EB" }} />
                    <Area type="monotone" dataKey="band" name="80% interval" stroke="none" fill="#4F46E5" fillOpacity={0.12} />
                    <Line type="monotone" dataKey="actual" name="Actual" stroke="#1F2937" strokeWidth={1.5} dot={false} connectNulls={false} />
                    <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#4F46E5" strokeWidth={2} strokeDasharray="5 3" dot={false} connectNulls={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Forecast summary stats */}
              <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t">
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Avg Daily</p>
                  <p className="text-sm font-semibold">{stats.overall_avg != null ? stats.overall_avg.toFixed(1) : "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Std Dev</p>
                  <p className="text-sm font-semibold">{stats.overall_std != null ? stats.overall_std.toFixed(1) : "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Forecast Avg</p>
                  <p className="text-sm font-semibold">{summary.avg_daily_forecast?.toFixed(0) || "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Peak Day</p>
                  <p className="text-sm font-semibold">{summary.peak_volume || "—"}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Hourly Pattern */}
          <Card>
            <CardHeader>
              <CardTitle>Hourly Ticket Pattern</CardTitle>
              <CardDescription>
                Average ticket creation by hour of day — identifies peak operational windows
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={hourlyChartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                    <XAxis dataKey="hour" tick={{ fontSize: 9 }} interval={2} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #E5E7EB",
                      }}
                      formatter={(value: any) => [value, "Avg tickets"]}
                    />
                    <Bar dataKey="avg" radius={[3, 3, 0, 0]}>
                      {hourlyChartData.map((entry: any, i: number) => (
                        <Cell
                          key={i}
                          fill={entry.avg >= peakThreshold ? "#4F46E5" : "#CBD5E1"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        /* ── Risk Tickets Table View ── */
        <Card>
          <CardHeader>
            <CardTitle>High-Risk Tickets</CardTitle>
            <CardDescription>
              Resolved tickets by share of their SLA target used (resolution time ÷ target for their priority) — top {Math.min(riskTickets.length, 50)} of {riskTickets.length}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[600px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ticket</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>MTTR (h)</TableHead>
                    <TableHead>SLA Deadline</TableHead>
                    <TableHead>Risk %</TableHead>
                    <TableHead>Risk Level</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {riskTickets.slice(0, 50).map((ticket: any, i: number) => (
                    <TableRow key={i}>
                      <TableCell className="font-mono text-xs text-foreground">
                        {ticket.ticket_id || ticket.number || `#${i + 1}`}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {ticket.priority}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {ticket.mttr_hours?.toFixed(1)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {ticket.sla_deadline}h
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-10 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(ticket.risk_pct, 100)}%`,
                                backgroundColor:
                                  ticket.risk_pct >= 90
                                    ? "#EF4444"
                                    : ticket.risk_pct >= 70
                                    ? "#F97316"
                                    : ticket.risk_pct >= 40
                                    ? "#EAB308"
                                    : "#22C55E",
                              }}
                            />
                          </div>
                          <span className="text-xs font-mono">
                            {ticket.risk_pct?.toFixed(0)}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${RISK_BG[ticket.risk_level] || ""}`}
                        >
                          {ticket.risk_level}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}