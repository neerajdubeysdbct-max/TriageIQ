/**
 * TicketIntelligenceTab.tsx (v2)
 * ===============================
 * Main container for Ticket Intelligence tab.
 *
 * Changes:
 *   - Dynamic filters from DB (not hardcoded)
 *   - Enhanced KPIs: FCR%, SLA breach, annual savings
 *   - Mini charts: channel donut, priority bar, lever bar
 *   - Top 10 widget (subcategories, groups, quick wins)
 *   - New filters: channel, priority, assignment_group, resolved_by, MTTR range, solution_lever
 *   - Clean column names (no "AIO" prefix)
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { AIODataTable } from "./AIODataTable";
import { AIOPivotCharts } from "./AIOPivotCharts";
import { PivotBuilder } from "./PivotBuilder";
import { PPTExportConfig } from "./PPTExportConfig";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// INTERFACES
// ============================================================

interface Stats {
  upload_id: number;
  filename: string;
  record_type: string;
  total_tickets: number;
  already_automated: number;
  already_automated_pct: number;
  can_be_automated: number;
  can_be_automated_pct: number;
  manual: number;
  manual_pct: number;
  avg_mttr_hours: number;
  fcr_pct: number;
  sla_breach_pct: number;
  estimated_annual_savings: number;
  needs_review: number;
  avg_aio_confidence: number;
  tower_distribution: { name: string; count: number }[];
  channel_distribution: { name: string; count: number }[];
  priority_distribution: { name: string; count: number }[];
  lever_distribution: { name: string; count: number }[];
  top_subcategories: { name: string; count: number }[];
}

interface TaxonomyItem {
  value: string;
  count: number;
}

interface Taxonomy {
  towers: TaxonomyItem[];
  categories: TaxonomyItem[];
  channels: TaxonomyItem[];
  priorities: TaxonomyItem[];
  assignment_groups: TaxonomyItem[];
  automation_statuses: TaxonomyItem[];
  solution_levers: TaxonomyItem[];
}

interface Top10Data {
  top_subcategories: { name: string; count: number }[];
  top_assignment_groups: { name: string; count: number }[];
  quick_wins: {
    subcategory: string;
    total: number;
    automatable: number;
    automation_pct: number;
    avg_mttr: number;
    est_savings: number;
  }[];
}

interface Filters {
  search: string;
  aio_tower: string;
  aio_category: string;
  automation_status: string;
  channel: string;
  priority: string;
  assignment_group: string;
  solution_lever: string;
  needs_review: boolean;
  mttr_min: string;
  mttr_max: string;
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function TicketIntelligenceTab({ uploadId }: { uploadId: number }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [top10, setTop10] = useState<Top10Data | null>(null);
  const [activeSection, setActiveSection] = useState("table");
  const [showPPTConfig, setShowPPTConfig] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  const [filters, setFilters] = useState<Filters>({
    search: "", aio_tower: "", aio_category: "", automation_status: "",
    channel: "", priority: "", assignment_group: "", solution_lever: "",
    needs_review: false, mttr_min: "", mttr_max: "",
  });

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}` };

  // --- Fetch data on mount ---
  useEffect(() => {
    if (!uploadId) return;
    fetchAll();
  }, [uploadId]);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, taxRes, top10Res] = await Promise.all([
        fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/stats`, { headers }),
        fetch(`${API_BASE}/api/ticket-intelligence/taxonomy/${uploadId}`, { headers }),
        fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/top10`, { headers }),
      ]);

      if (!statsRes.ok) throw new Error("Failed to load stats");
      setStats(await statsRes.json());

      if (taxRes.ok) setTaxonomy(await taxRes.json());
      if (top10Res.ok) setTop10(await top10Res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // --- Export handlers ---
  const handleExport = async (format: string) => {
    if (format === "ppt") { setShowPPTConfig(true); return; }
    setExporting(format);
    try {
      const url = `${API_BASE}/api/ticket-intelligence/${uploadId}/export/${format}`;
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `TicketIntelligence_${stats?.filename || uploadId}.${format === "excel" ? "xlsx" : format}`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert("Export failed");
    } finally {
      setExporting(null);
    }
  };

  const updateFilter = (key: keyof Filters, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  // --- Loading / Error ---
  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400, gap: 12 }}>
        <div style={{ width: 24, height: 24, border: "3px solid #e5e7eb", borderTopColor: "#2563eb", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <span style={{ color: "#6b7280", fontSize: 13 }}>Loading Ticket Intelligence...</span>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 400, gap: 12 }}>
        <span style={{ color: "#ef4444", fontSize: 14, fontWeight: 600 }}>Failed to load data</span>
        <span style={{ color: "#6b7280", fontSize: 12 }}>{error}</span>
        <button onClick={fetchAll} style={{ padding: "8px 20px", background: "#2563eb", color: "white", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Retry</button>
      </div>
    );
  }

  const recordBadge = stats.record_type === "incident"
    ? { color: "#ef4444", bg: "#fef2f2", label: "INCIDENT DUMP" }
    : { color: "#2563eb", bg: "#eff6ff", label: "REQUEST DUMP" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: recordBadge.color, background: recordBadge.bg, padding: "3px 10px", borderRadius: 4, letterSpacing: 0.5 }}>
            {recordBadge.label}
          </span>
          <span style={{ fontSize: 13, color: "#374151", fontWeight: 500 }}>{stats.filename}</span>
          <span style={{ fontSize: 12, color: "#9ca3af" }}>{stats.total_tickets.toLocaleString()} tickets</span>
          {stats.needs_review > 0 && (
            <span style={{ fontSize: 11, color: "#f59e0b", fontWeight: 600 }}>
              {stats.needs_review.toLocaleString()} need review
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "#9ca3af" }}>
          Confidence: {stats.avg_aio_confidence}% avg
        </div>
      </div>

      {/* ── KPI Cards (8 cards) ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
        <KPICard label="Total Tickets" value={stats.total_tickets.toLocaleString()} color="#2563eb" />
        <KPICard label="Already Automated" value={`${stats.already_automated.toLocaleString()} (${stats.already_automated_pct}%)`} color="#16a34a" />
        <KPICard label="Can Be Automated" value={`${stats.can_be_automated.toLocaleString()} (${stats.can_be_automated_pct}%)`} color="#0ea5e9" />
        <KPICard label="Manual" value={`${stats.manual.toLocaleString()} (${stats.manual_pct}%)`} color="#ef4444" />
        <KPICard label="Avg MTTR" value={`${stats.avg_mttr_hours}h`} color="#6b7280" />
        <KPICard label="FCR %" value={`${stats.fcr_pct}%`} color="#8b5cf6" />
        <KPICard label="SLA Breach" value={`${stats.sla_breach_pct}%`} color="#f97316" />
        <KPICard label="Est. Annual Savings" value={`₹${(stats.estimated_annual_savings || 0).toLocaleString()}`} color="#059669" />
      </div>

      {/* ── Mini Charts Row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <MiniBarChart title="Top Channels" data={stats.channel_distribution} />
        <MiniBarChart title="Priority Split" data={stats.priority_distribution} />
        <MiniBarChart title="Solution Levers" data={stats.lever_distribution} />
      </div>

      {/* ── Export Bar ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 600, marginRight: 4 }}>EXPORT:</span>
        {["csv", "excel", "pdf"].map((fmt) => (
          <button key={fmt} onClick={() => handleExport(fmt)} disabled={exporting === fmt}
            style={{ padding: "6px 14px", fontSize: 11, fontWeight: 600, border: "1px solid #e5e7eb", borderRadius: 6, background: "white", cursor: "pointer", color: "#374151", opacity: exporting === fmt ? 0.5 : 1 }}>
            {exporting === fmt ? "..." : fmt === "csv" ? "CSV" : fmt === "excel" ? "Excel" : "PDF"}
          </button>
        ))}
        <button onClick={() => setShowPPTConfig(true)}
          style={{ padding: "6px 14px", fontSize: 11, fontWeight: 700, border: "none", borderRadius: 6, background: "#2563eb", color: "white", cursor: "pointer" }}>
          PowerPoint
        </button>
      </div>

      {/* ── Section Tabs ── */}
      <div style={{ display: "flex", borderBottom: "2px solid #e5e7eb", gap: 0 }}>
        {[
          { key: "table", label: "Data Table" },
          { key: "pivots", label: `Auto Pivots (12)` },
          { key: "pivot_builder", label: "Pivot Builder" },
          { key: "top10", label: "Top 10" },
        ].map((tab) => (
          <button key={tab.key} onClick={() => setActiveSection(tab.key)}
            style={{
              padding: "10px 18px", fontSize: 13, fontWeight: activeSection === tab.key ? 600 : 400,
              color: activeSection === tab.key ? "#2563eb" : "#6b7280",
              borderTop: "none", borderLeft: "none", borderRight: "none",
              borderBottom: activeSection === tab.key ? "2px solid #2563eb" : "2px solid transparent",
              marginBottom: -2, background: "none", cursor: "pointer",
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Filters (for Data Table) ── */}
      {activeSection === "table" && taxonomy && (
        <FilterBar filters={filters} taxonomy={taxonomy} onFilterChange={updateFilter} />
      )}

      {/* ── Content ── */}
      {activeSection === "table" && (
        <AIODataTable uploadId={uploadId} filters={filters} taxonomy={taxonomy} onOverrideSaved={fetchAll} />
      )}
      {activeSection === "pivots" && <AIOPivotCharts uploadId={uploadId} />}
      {activeSection === "pivot_builder" && <PivotBuilder uploadId={uploadId} />}
      {activeSection === "top10" && top10 && <Top10Widget data={top10} onFilterClick={(key, val) => { updateFilter(key as keyof Filters, val); setActiveSection("table"); }} />}

      {/* ── PPT Config Modal ── */}
      {showPPTConfig && <PPTExportConfig uploadId={uploadId} stats={stats} onClose={() => setShowPPTConfig(false)} />}
    </div>
  );
}

// ============================================================
// KPI CARD
// ============================================================

function KPICard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 8, padding: "12px 14px", borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: 10, color: color, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#111827" }}>{value}</div>
    </div>
  );
}

// ============================================================
// MINI BAR CHART (inline horizontal bars)
// ============================================================

function MiniBarChart({ title, data }: { title: string; data: { name: string; count: number }[] }) {
  if (!data || data.length === 0) return null;
  const maxCount = Math.max(...data.map((d) => d.count));
  const totalCount = data.reduce((sum, d) => sum + d.count, 0);
  const colors = ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

  return (
    <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#374151", marginBottom: 8 }}>{title}</div>
      {data.slice(0, 5).map((d, i) => (
        <div key={d.name} style={{ marginBottom: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#6b7280", marginBottom: 2 }}>
            <span style={{ maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name || "Unknown"}</span>
            <span style={{ fontWeight: 600 }}>{d.count.toLocaleString()} ({Math.round(d.count / totalCount * 100)}%)</span>
          </div>
          <div style={{ height: 6, background: "#f3f4f6", borderRadius: 3 }}>
            <div style={{ height: 6, background: colors[i % colors.length], borderRadius: 3, width: `${(d.count / maxCount) * 100}%`, transition: "width 0.3s" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// FILTER BAR (dynamic from taxonomy)
// ============================================================

function FilterBar({ filters, taxonomy, onFilterChange }: {
  filters: Filters;
  taxonomy: Taxonomy;
  onFilterChange: (key: keyof Filters, value: any) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
      {/* Search */}
      <input
        type="text" placeholder="Search tickets..."
        value={filters.search}
        onChange={(e) => onFilterChange("search", e.target.value)}
        style={{ padding: "6px 12px", fontSize: 12, border: "1px solid #d1d5db", borderRadius: 6, width: 200, outline: "none" }}
      />

      {/* Tower */}
      <DynamicDropdown
        value={filters.aio_tower}
        options={taxonomy.towers}
        placeholder="All Towers"
        onChange={(v) => onFilterChange("aio_tower", v)}
      />

      {/* Category */}
      <DynamicDropdown
        value={filters.aio_category}
        options={taxonomy.categories}
        placeholder="All Categories"
        onChange={(v) => onFilterChange("aio_category", v)}
      />

      {/* Channel */}
      <DynamicDropdown
        value={filters.channel}
        options={taxonomy.channels}
        placeholder="All Channels"
        onChange={(v) => onFilterChange("channel", v)}
      />

      {/* Priority */}
      <DynamicDropdown
        value={filters.priority}
        options={taxonomy.priorities}
        placeholder="All Priorities"
        onChange={(v) => onFilterChange("priority", v)}
      />

      {/* Automation Status */}
      <DynamicDropdown
        value={filters.automation_status}
        options={taxonomy.automation_statuses}
        placeholder="All Statuses"
        onChange={(v) => onFilterChange("automation_status", v)}
      />

      {/* Solution Lever */}
      <DynamicDropdown
        value={filters.solution_lever}
        options={taxonomy.solution_levers}
        placeholder="All Actions"
        onChange={(v) => onFilterChange("solution_lever", v)}
      />

      {/* MTTR Range */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <input
          type="number" placeholder="MTTR min"
          value={filters.mttr_min}
          onChange={(e) => onFilterChange("mttr_min", e.target.value)}
          style={{ padding: "6px 8px", fontSize: 11, border: "1px solid #d1d5db", borderRadius: 6, width: 70, outline: "none" }}
        />
        <span style={{ fontSize: 10, color: "#9ca3af" }}>—</span>
        <input
          type="number" placeholder="max"
          value={filters.mttr_max}
          onChange={(e) => onFilterChange("mttr_max", e.target.value)}
          style={{ padding: "6px 8px", fontSize: 11, border: "1px solid #d1d5db", borderRadius: 6, width: 70, outline: "none" }}
        />
      </div>

      {/* Needs Review */}
      <button
        onClick={() => onFilterChange("needs_review", !filters.needs_review)}
        style={{
          padding: "6px 12px", fontSize: 11, fontWeight: 600, borderRadius: 6, cursor: "pointer",
          background: filters.needs_review ? "#fef3c7" : "white",
          border: filters.needs_review ? "1px solid #f59e0b" : "1px solid #d1d5db",
          color: filters.needs_review ? "#b45309" : "#6b7280",
        }}>
        Needs Review
      </button>

      {/* Clear All */}
      {Object.values(filters).some((v) => v && v !== false) && (
        <button
          onClick={() => onFilterChange("search" as any, "")}
          style={{ padding: "6px 10px", fontSize: 10, color: "#ef4444", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>
          ✕ Clear All
        </button>
      )}
    </div>
  );
}

// ============================================================
// DYNAMIC DROPDOWN (shows counts)
// ============================================================

function DynamicDropdown({ value, options, placeholder, onChange }: {
  value: string;
  options: TaxonomyItem[];
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ padding: "6px 10px", fontSize: 11, border: "1px solid #d1d5db", borderRadius: 6, background: "white", color: "#374151", outline: "none", maxWidth: 200 }}
    >
      <option value="">{placeholder}</option>
      {options?.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.value} ({opt.count?.toLocaleString()})
        </option>
      ))}
    </select>
  );
}

// ============================================================
// TOP 10 WIDGET
// ============================================================

function Top10Widget({ data, onFilterClick }: {
  data: Top10Data;
  onFilterClick: (key: string, value: string) => void;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, padding: 4 }}>
      {/* Top 10 SubCategories */}
      <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "#111827", marginBottom: 12, borderBottom: "2px solid #2563eb", paddingBottom: 6 }}>
          Top 10 Sub Categories
        </h3>
        {data.top_subcategories.map((item, i) => (
          <div key={item.name}
            onClick={() => onFilterClick("aio_subcategory", item.name)}
            style={{ display: "flex", justifyContent: "space-between", padding: "6px 8px", borderRadius: 4, cursor: "pointer", fontSize: 12, color: "#374151", background: i % 2 === 0 ? "#f9fafb" : "white" }}
          >
            <span style={{ fontWeight: 500 }}>{i + 1}. {item.name}</span>
            <span style={{ fontWeight: 700, color: "#2563eb" }}>{item.count.toLocaleString()}</span>
          </div>
        ))}
      </div>

      {/* Top 10 Assignment Groups */}
      <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "#111827", marginBottom: 12, borderBottom: "2px solid #16a34a", paddingBottom: 6 }}>
          Top 10 Assignment Groups
        </h3>
        {data.top_assignment_groups.map((item, i) => (
          <div key={item.name}
            onClick={() => onFilterClick("assignment_group", item.name)}
            style={{ display: "flex", justifyContent: "space-between", padding: "6px 8px", borderRadius: 4, cursor: "pointer", fontSize: 12, color: "#374151", background: i % 2 === 0 ? "#f9fafb" : "white" }}
          >
            <span style={{ fontWeight: 500, maxWidth: "65%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{i + 1}. {item.name}</span>
            <span style={{ fontWeight: 700, color: "#16a34a" }}>{item.count.toLocaleString()}</span>
          </div>
        ))}
      </div>

      {/* Quick Wins */}
      <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "#111827", marginBottom: 12, borderBottom: "2px solid #f59e0b", paddingBottom: 6 }}>
          Quick Wins (by ROI)
        </h3>
        {data.quick_wins.map((item, i) => (
          <div key={item.subcategory}
            onClick={() => onFilterClick("aio_subcategory", item.subcategory)}
            style={{ display: "flex", justifyContent: "space-between", padding: "6px 8px", borderRadius: 4, cursor: "pointer", fontSize: 11, color: "#374151", background: i % 2 === 0 ? "#f9fafb" : "white" }}
          >
            <div>
              <div style={{ fontWeight: 500, fontSize: 12 }}>{i + 1}. {item.subcategory}</div>
              <div style={{ fontSize: 10, color: "#9ca3af" }}>{item.total} tickets · {item.automation_pct}% auto</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontWeight: 700, color: "#059669", fontSize: 12 }}>₹{item.est_savings.toLocaleString()}</div>
              <div style={{ fontSize: 10, color: "#9ca3af" }}>/year</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}