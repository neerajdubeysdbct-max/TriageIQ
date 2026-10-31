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
  Eye,
  RefreshCw,
  Activity,
  Zap,
  Search,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  if (typeof window !== "undefined") return localStorage.getItem("token");
  return null;
}

interface AnomalyDetectionProps {
  uploadId: number;
}

const SEV_COLORS: Record<string, string> = {
  critical: "#EF4444", Critical: "#EF4444",
  high: "#F97316", High: "#F97316",
  medium: "#EAB308", Medium: "#EAB308",
  low: "#22C55E", Low: "#22C55E",
};

const SEV_BG: Record<string, string> = {
  critical: "bg-red-500/10 text-red-600 border-red-500/20",
  Critical: "bg-red-500/10 text-red-600 border-red-500/20",
  high: "bg-orange-500/10 text-orange-600 border-orange-500/20",
  High: "bg-orange-500/10 text-orange-600 border-orange-500/20",
  medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  Medium: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  low: "bg-green-500/10 text-green-600 border-green-500/20",
  Low: "bg-green-500/10 text-green-600 border-green-500/20",
};

export default function AnomalyDetection({ uploadId }: AnomalyDetectionProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAnomaly, setSelectedAnomaly] = useState<any>(null);

  useEffect(() => {
    if (uploadId) fetchData();
  }, [uploadId]);

  async function fetchData() {
    try {
      setLoading(true);
      const token = getToken();
      const res = await fetch(`${API}/api/predictions/${uploadId}/anomalies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Failed to fetch anomalies:", err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Running anomaly detection...</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const totalAnomalies = data.total_anomalies || 0;
  const sevDist = data.severity_distribution || {};
  const anomalies = data.anomalies || [];
  const meanMttr = data.mean_mttr || 0;
  const stdMttr = data.std_mttr || 0;
  const confHistogram = data.confidence_histogram || [];
  const evalQ3 = data.evaluation?.datasets?.["unseen dump (northwind_q3)"];
  const mttrHistogram = data.mttr_histogram || [];

  // Severity pie/bar data
  const sevBarData = Object.entries(sevDist).map(([name, value]) => ({
    name,
    count: value as number,
    fill: SEV_COLORS[name] || "#94A3B8",
  }));

  // MTTR histogram for chart
  const mttrChartData = mttrHistogram.map((item: any) => ({
    range: item.range || item.bucket || `${item.min}-${item.max}`,
    count: item.count,
  }));

  // Confidence histogram for chart
  const confChartData = confHistogram.map((item: any) => ({
    range: item.range || item.bucket || `${item.min}-${item.max}`,
    count: item.count,
  }));

  // Scatter data — anomaly score vs MTTR
  const scatterData = anomalies.slice(0, 200).map((a: any) => ({
    x: a.mttr_hours || 0,
    y: a.anomaly_score || 0,
    severity: a.severity,
    ticket: a.ticket_id || a.number,
  }));

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            IsolationForest with per-ticket-type context · {totalAnomalies.toLocaleString()} anomalies flagged
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="gap-1.5">
            <Activity className="w-3 h-3" />
            μ MTTR: {meanMttr.toFixed(1)}h · σ: {stdMttr.toFixed(1)}h
          </Badge>
          <Button variant="outline" size="sm" className="gap-2" onClick={fetchData}>
            <RefreshCw className="w-3.5 h-3.5" />
            Re-scan
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="py-4 gap-2">
          <CardContent className="px-4 py-0">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-md bg-red-500/10">
                <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
              </div>
            </div>
            <p className="text-2xl font-bold text-foreground">{totalAnomalies.toLocaleString()}</p>
            <p className="text-[11px] text-muted-foreground">Total Anomalies</p>
          </CardContent>
        </Card>
        {["Critical", "High", "Medium", "Low"].map((sev) => (
          <Card key={sev} className="py-4 gap-2">
            <CardContent className="px-4 py-0">
              <div className="flex items-center justify-between mb-2">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: SEV_COLORS[sev] }}
                />
                <span className="text-[10px] text-muted-foreground uppercase">{sev}</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                {(sevDist[sev] || 0).toLocaleString()}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {totalAnomalies > 0
                  ? ((((sevDist[sev] as number) || 0) / totalAnomalies) * 100).toFixed(1)
                  : "0"}
                % of anomalies
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Severity Distribution Bar */}
        <Card>
          <CardHeader>
            <CardTitle>Severity Distribution</CardTitle>
            <CardDescription>Flagged tickets ranked by anomaly score: top third Critical, then High, then Medium</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sevBarData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={60} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid #E5E7EB",
                    }}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {sevBarData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Anomaly Score vs MTTR Scatter */}
        <Card>
          <CardHeader>
            <CardTitle>Anomaly Score vs Resolution Time</CardTitle>
            <CardDescription>Each dot is an anomalous ticket — higher = more anomalous</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="x"
                    name="MTTR (hours)"
                    tick={{ fontSize: 10 }}
                    label={{ value: "MTTR (hours)", position: "bottom", fontSize: 10, offset: -5 }}
                  />
                  <YAxis
                    dataKey="y"
                    name="Anomaly Score"
                    tick={{ fontSize: 10 }}
                    domain={[0, 1]}
                    label={{ value: "Score", angle: -90, position: "insideLeft", fontSize: 10 }}
                  />
                  <ZAxis range={[20, 60]} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid #E5E7EB",
                    }}
                    formatter={(value: any, name: any) => [
                      typeof value === "number" ? value.toFixed(2) : value,
                      name,
                    ]}
                  />
                  <Scatter data={scatterData} fill="#4F46E5" fillOpacity={0.5} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* MTTR + Confidence Histograms */}
      {(mttrChartData.length > 0 || confChartData.length > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {mttrChartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>MTTR Distribution</CardTitle>
                <CardDescription>Resolution time histogram — tails indicate anomalies</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={mttrChartData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                      <XAxis dataKey="range" tick={{ fontSize: 9 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 8,
                          border: "1px solid #E5E7EB",
                        }}
                      />
                      <Bar dataKey="count" fill="#4F46E5" radius={[3, 3, 0, 0]} fillOpacity={0.7} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {confChartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Anomaly Score Distribution</CardTitle>
                <CardDescription>IsolationForest score of every ticket (0 = typical, 1 = most unusual)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={confChartData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                      <XAxis dataKey="range" tick={{ fontSize: 9 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 8,
                          border: "1px solid #E5E7EB",
                        }}
                      />
                      <Bar dataKey="count" fill="#8B5CF6" radius={[3, 3, 0, 0]} fillOpacity={0.7} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Anomalies Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Detected Anomalies</CardTitle>
              <CardDescription>
                Tickets flagged by multi-factor statistical analysis — top {Math.min(anomalies.length, 50)}
              </CardDescription>
            </div>
            <Badge variant="outline" className="gap-1">
              <Search className="w-3 h-3" />
              {anomalies.length} results
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[420px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticket</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>MTTR (h)</TableHead>
                  <TableHead>Reassign</TableHead>
                  <TableHead>Reopen</TableHead>
                  <TableHead className="w-[240px]">Reasons</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {anomalies.slice(0, 50).map((a: any, i: number) => (
                  <TableRow
                    key={i}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedAnomaly(selectedAnomaly === i ? null : i)}
                  >
                    <TableCell className="font-mono text-xs text-foreground">
                      {a.ticket_id || a.number || `#${i + 1}`}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-10 h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(a.anomaly_score || 0) * 100}%`,
                              backgroundColor: SEV_COLORS[a.severity] || "#94A3B8",
                            }}
                          />
                        </div>
                        <span className="text-xs font-mono">
                          {(a.anomaly_score || 0).toFixed(2)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${SEV_BG[a.severity] || ""}`}
                      >
                        {a.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {(a.mttr_hours || 0).toFixed(1)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {a.reassignment_count || 0}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {a.reopen_count || 0}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {(a.reasons || []).slice(0, 2).map((reason: string, ri: number) => (
                          <span
                            key={ri}
                            className="inline-block text-[10px] bg-muted px-1.5 py-0.5 rounded"
                          >
                            {reason.length > 35 ? reason.slice(0, 35) + "..." : reason}
                          </span>
                        ))}
                        {(a.reasons || []).length > 2 && (
                          <span className="inline-block text-[10px] text-muted-foreground">
                            +{(a.reasons || []).length - 2}
                          </span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Methodology Note */}
      <Card className="bg-muted/30">
        <CardContent className="py-4 px-5">
          <div className="flex items-start gap-3">
            <Zap className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
            <div className="text-xs text-muted-foreground leading-relaxed">
              <span className="font-semibold text-foreground">Detection Method:</span>{" "}
              IsolationForest over features measured against each ticket&apos;s own type (its L2 subcategory):
              resolution time as a robust z-score (median / MAD) within the type, reassignments, reopens, and
              off-hours activity weighted by how rare it is for that type. The {(data.contamination ?? 0.03) * 100}% most
              isolated tickets are flagged.
              {evalQ3 && (
                <>
                  {" "}Evaluated against planted anomalies on an unseen dump: average precision{" "}
                  {evalQ3.results[evalQ3.results.length - 1].average_precision.toFixed(2)} vs{" "}
                  {evalQ3.results[1].average_precision.toFixed(2)} for the previous rule score (base rate{" "}
                  {(evalQ3.base_rate * 100).toFixed(1)}%); recall {(evalQ3.operating_point.recall * 100).toFixed(0)}% at
                  precision {(evalQ3.operating_point.precision * 100).toFixed(0)}%. Weakest on slow-resolution outliers,
                  which overlap with legitimately slow ticket paths.
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}