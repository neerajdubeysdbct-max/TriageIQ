/**
 * AIOPivotCharts.tsx (v2)
 * ========================
 * Renders 12 auto-generated pivot charts.
 * Clean labels — no "AIO" prefix.
 * Supports: bar, horizontal_bar, stacked_bar, line, table
 */

"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LineChart, Line, Cell,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COLORS = [
  "#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#e11d48",
];

const AUTO_STATUS_COLORS: Record<string, string> = {
  "Already Automated": "#16a34a",
  "Can Be Automated": "#2563eb",
  "Manual": "#dc2626",
};

interface Pivot {
  id: string;
  title: string;
  chart_type: string;
  data: any[];
  x_key?: string;
  y_key?: string;
  series?: string[];
}

interface AIOPivotChartsProps {
  uploadId: number;
}

export function AIOPivotCharts({ uploadId }: AIOPivotChartsProps) {
  const [pivots, setPivots] = useState<Pivot[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedPivot, setExpandedPivot] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetchPivots();
  }, [uploadId]);

  const fetchPivots = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/pivots`, { headers });
      if (!res.ok) throw new Error("Failed to load pivots");
      setPivots(await res.json());
    } catch (err) {
      console.error("Pivot load error:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 256, gap: 8 }}>
        <div style={{ width: 20, height: 20, border: "2px solid #2563eb", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <span style={{ color: "#9ca3af", fontSize: 12 }}>Generating pivots...</span>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (pivots.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 256, color: "#9ca3af", fontSize: 13 }}>
        No pivot data available. Run AIO classification first.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: expandedPivot ? "1fr" : "1fr 1fr", gap: 16, padding: 4 }}>
      {pivots.map((pivot, idx) => {
        const isExpanded = expandedPivot === pivot.id;
        if (expandedPivot && !isExpanded) return null;

        return (
          <div key={pivot.id} style={{
            background: "white", border: "1px solid #e5e7eb", borderRadius: 10,
            overflow: "hidden", gridColumn: isExpanded ? "1 / -1" : "auto",
          }}>
            {/* Header */}
            <div style={{
              padding: "10px 16px", borderBottom: "1px solid #f3f4f6",
              display: "flex", alignItems: "center", justifyContent: "space-between", background: "#f9fafb",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>#{idx + 1}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#374151" }}>{pivot.title}</span>
              </div>
              <button
                onClick={() => setExpandedPivot(isExpanded ? null : pivot.id)}
                style={{ fontSize: 11, color: "#6b7280", background: "none", border: "none", cursor: "pointer", padding: "2px 8px" }}
              >
                {isExpanded ? "Collapse" : "Expand"}
              </button>
            </div>

            {/* Chart */}
            <div style={{ padding: 12, height: isExpanded ? 500 : 320 }}>
              <RenderChart pivot={pivot} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// CHART RENDERER
// ============================================================

function RenderChart({ pivot }: { pivot: Pivot }) {
  if (!pivot.data || pivot.data.length === 0) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#d1d5db", fontSize: 12 }}>No data</div>;
  }

  switch (pivot.chart_type) {
    case "bar": return <BarChartView pivot={pivot} />;
    case "horizontal_bar": return <HorizontalBarView pivot={pivot} />;
    case "stacked_bar": return <StackedBarView pivot={pivot} />;
    case "line": return <LineChartView pivot={pivot} />;
    case "heatmap":
    case "table":
    default: return <TableView pivot={pivot} />;
  }
}

function BarChartView({ pivot }: { pivot: Pivot }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={pivot.data} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={pivot.x_key || "name"} tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
        <Bar dataKey={pivot.y_key || "count"} radius={[4, 4, 0, 0]}>
          {pivot.data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function HorizontalBarView({ pivot }: { pivot: Pivot }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={pivot.data} layout="vertical" margin={{ top: 5, right: 20, left: 130, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis type="number" tick={{ fontSize: 10 }} />
        <YAxis type="category" dataKey={pivot.y_key || "name"} tick={{ fontSize: 9 }} width={120} />
        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {pivot.data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function StackedBarView({ pivot }: { pivot: Pivot }) {
  const series = pivot.series || ["Already Automated", "Can Be Automated", "Manual"];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={pivot.data} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={pivot.x_key || "tower"} tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} stackId="a" fill={AUTO_STATUS_COLORS[s] || COLORS[i % COLORS.length]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineChartView({ pivot }: { pivot: Pivot }) {
  const series = pivot.series || [];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={pivot.data} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={pivot.x_key || "month"} tick={{ fontSize: 10 }} angle={-35} textAnchor="end" />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TableView({ pivot }: { pivot: Pivot }) {
  if (!pivot.data || pivot.data.length === 0) return null;
  const columns = Object.keys(pivot.data[0]);

  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
        <thead style={{ position: "sticky", top: 0 }}>
          <tr>
            {columns.map((col) => (
              <th key={col} style={{
                padding: "8px 12px", textAlign: "left", background: "#f3f4f6",
                borderBottom: "2px solid #e5e7eb", fontWeight: 700, color: "#374151",
                whiteSpace: "nowrap", fontSize: 10,
              }}>
                {col.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pivot.data.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "white" : "#f9fafb" }}>
              {columns.map((col) => (
                <td key={col} style={{
                  padding: "6px 12px", borderBottom: "1px solid #f3f4f6",
                  whiteSpace: "nowrap", color: "#374151",
                }}>
                  {formatValue(row[col], col)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatValue(val: any, colName: string): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "number") {
    if (colName.includes("pct") || colName.includes("automation")) {
      return `${val.toFixed(1)}%`;
    }
    if (colName.includes("mttr")) {
      return `${val.toFixed(2)}h`;
    }
    if (colName.includes("savings") || colName.includes("est_")) {
      return `₹${val.toLocaleString()}`;
    }
    return val.toLocaleString();
  }
  return String(val);
}