/**
 * AIODataTable.tsx (v2)
 * =======================
 * Enterprise-grade data table for Ticket Intelligence.
 *
 * Features:
 *   - Resizable columns (drag border like Excel)
 *   - Single-click row → Ticket Detail Modal
 *   - Column reordering (drag header)
 *   - New columns: Channel, Resolved By, Reassignments, Sub Category 1, Evidence, Cluster, Est Savings
 *   - Dynamic filters passed from parent
 *   - Color-coded automation status
 *   - Confidence bar
 *   - Inline cell editing on double-click
 *   - Clean column names (no "AIO" prefix)
 */

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { AIOCellEditor } from "./AIOCellEditor";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// INTERFACES
// ============================================================

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

interface AIODataTableProps {
  uploadId: number;
  filters: Filters;
  taxonomy: any;
  onOverrideSaved: () => void;
}

interface TicketRow {
  id: number;
  ticket_number: string;
  short_description: string;
  channel: string;
  assignment_group: string;
  resolved_by: string;
  priority: string;
  mttr_hours: number | null;
  reassignment_count: number;
  aio_tower: string;
  aio_category: string;
  aio_subcategory: string;
  aio_detail: string;
  aio_summary: string;
  aio_confidence: number;
  aio_classified_by: string;
  aio_needs_review: boolean;
  automation_status: string;
  action: string;
  evidence: string;
  cluster_id: number | null;
  cluster_count: number;
  est_savings: number;
}

// ============================================================
// COLUMN DEFINITIONS
// ============================================================

interface ColumnDef {
  key: string;
  label: string;
  width: number;
  minWidth: number;
  type: "text" | "badge" | "confidence" | "editable" | "evidence" | "cluster" | "savings";
  editable?: boolean;
  editField?: string;
  isAIO?: boolean;
}

const DEFAULT_COLUMNS: ColumnDef[] = [
  { key: "ticket_number", label: "Ticket#", width: 110, minWidth: 80, type: "text" },
  { key: "short_description", label: "Description", width: 200, minWidth: 120, type: "text" },
  { key: "channel", label: "Channel", width: 120, minWidth: 80, type: "text" },
  { key: "assignment_group", label: "Assignment Group", width: 180, minWidth: 100, type: "text" },
  { key: "resolved_by", label: "Resolved By", width: 150, minWidth: 80, type: "text" },
  { key: "priority", label: "Pri", width: 70, minWidth: 50, type: "text" },
  { key: "mttr_hours", label: "MTTR(h)", width: 75, minWidth: 55, type: "text" },
  { key: "reassignment_count", label: "Reassign", width: 70, minWidth: 50, type: "text" },
  { key: "aio_tower", label: "Tower", width: 110, minWidth: 70, type: "editable", editable: true, editField: "aio_tower", isAIO: true },
  { key: "aio_category", label: "Category", width: 130, minWidth: 80, type: "editable", editable: true, editField: "aio_category", isAIO: true },
  { key: "aio_subcategory", label: "Sub Category", width: 150, minWidth: 90, type: "editable", editable: true, editField: "aio_subcategory", isAIO: true },
  { key: "aio_detail", label: "Sub Category 1", width: 140, minWidth: 80, type: "editable", editable: true, editField: "aio_detail", isAIO: true },
  { key: "automation_status", label: "Automation Status", width: 130, minWidth: 90, type: "badge", editable: true, editField: "automation_status", isAIO: true },
  { key: "action", label: "Action", width: 180, minWidth: 100, type: "editable", editable: true, editField: "action", isAIO: true },
  { key: "aio_summary", label: "Summary", width: 220, minWidth: 120, type: "editable", editable: true, editField: "aio_summary", isAIO: true },
  { key: "evidence", label: "Evidence", width: 200, minWidth: 100, type: "evidence" },
  { key: "cluster_count", label: "Cluster", width: 80, minWidth: 60, type: "cluster" },
  { key: "est_savings", label: "Saving (₹)", width: 80, minWidth: 60, type: "savings" },
  { key: "aio_confidence", label: "Conf", width: 70, minWidth: 50, type: "confidence" },
];

// ============================================================
// MAIN COMPONENT
// ============================================================

export function AIODataTable({ uploadId, filters, taxonomy, onOverrideSaved }: AIODataTableProps) {
  const [rows, setRows] = useState<TicketRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [sortBy, setSortBy] = useState("ticket_number");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [loading, setLoading] = useState(true);
  const [columns, setColumns] = useState<ColumnDef[]>(DEFAULT_COLUMNS);
  const [editingCell, setEditingCell] = useState<{ rowId: number; field: string } | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [resizingCol, setResizingCol] = useState<number | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}` };

  // --- Fetch data ---
  useEffect(() => {
    fetchData();
  }, [uploadId, page, sortBy, sortDir, filters]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      if (filters.search) params.set("search", filters.search);
      if (filters.aio_tower) params.set("aio_tower", filters.aio_tower);
      if (filters.aio_category) params.set("aio_category", filters.aio_category);
      if (filters.automation_status) params.set("automation_status", filters.automation_status);
      if (filters.channel) params.set("channel", filters.channel);
      if (filters.priority) params.set("priority", filters.priority);
      if (filters.assignment_group) params.set("assignment_group", filters.assignment_group);
      if (filters.solution_lever) params.set("solution_lever", filters.solution_lever);
      if (filters.needs_review) params.set("needs_review", "true");
      if (filters.mttr_min) params.set("mttr_min", filters.mttr_min);
      if (filters.mttr_max) params.set("mttr_max", filters.mttr_max);

      const res = await fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/table?${params}`, { headers });
      if (!res.ok) throw new Error("Failed to load");
      const data = await res.json();
      setRows(data.rows);
      setTotal(data.total);
    } catch (err) {
      console.error("Table load error:", err);
    } finally {
      setLoading(false);
    }
  };

  // --- Sort ---
  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortDir("asc");
    }
    setPage(1);
  };

  // --- Column resize ---
  const handleResizeStart = (colIndex: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setResizingCol(colIndex);

    const startX = e.clientX;
    const startWidth = columns[colIndex].width;

    const onMouseMove = (ev: MouseEvent) => {
      const diff = ev.clientX - startX;
      const newWidth = Math.max(columns[colIndex].minWidth, startWidth + diff);
      setColumns((prev) => {
        const updated = [...prev];
        updated[colIndex] = { ...updated[colIndex], width: newWidth };
        return updated;
      });
    };

    const onMouseUp = () => {
      setResizingCol(null);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  // --- Override save ---
  const handleOverrideSave = async (ticketId: number, field: string, value: string) => {
    try {
      await fetch(`${API_BASE}/api/ticket-intelligence/override`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ ticket_id: ticketId, field, value }),
      });
      setEditingCell(null);
      fetchData();
      onOverrideSaved();
    } catch (err) {
      console.error("Override error:", err);
    }
  };

  // --- Pagination ---
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Row count */}
      <div style={{ display: "flex", justifyContent: "flex-end", fontSize: 11, color: "#9ca3af" }}>
        {total.toLocaleString()} tickets
      </div>

      {/* Top scrollbar */}
      <div
        onScroll={(e) => { if (tableRef.current) tableRef.current.scrollLeft = (e.target as HTMLElement).scrollLeft; }}
        style={{ overflow: "auto", borderTop: "1px solid #e5e7eb", borderLeft: "1px solid #e5e7eb", borderRight: "1px solid #e5e7eb", borderRadius: "8px 8px 0 0" }}
      >
        <div style={{ height: 1, width: columns.reduce((sum, c) => sum + c.width, 0) }} />
      </div>

      {/* Table */}
      <div
        ref={tableRef}
        onScroll={(e) => {
          const prev = (e.target as HTMLElement).previousElementSibling as HTMLElement;
          if (prev) prev.scrollLeft = (e.target as HTMLElement).scrollLeft;
        }}
        style={{ overflow: "auto", border: "1px solid #e5e7eb", borderRadius: "0 0 8px 8px", background: "white", maxHeight: "65vh" }}
      >
        <table style={{ borderCollapse: "collapse", minWidth: columns.reduce((sum, c) => sum + c.width, 0) }}>
          {/* Header */}
          <thead style={{ position: "sticky", top: 0, zIndex: 10 }}>
            <tr>
              {columns.map((col, colIdx) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    width: col.width,
                    minWidth: col.minWidth,
                    padding: "8px 10px",
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: "left",
                    cursor: "pointer",
                    userSelect: "none",
                    whiteSpace: "nowrap",
                    borderBottom: "2px solid #e5e7eb",
                    position: "relative",
                    background: col.isAIO ? "#2563eb" : "#f3f4f6",
                    color: col.isAIO ? "white" : "#374151",
                  }}
                >
                  {col.label}
                  {sortBy === col.key && (
                    <span style={{ marginLeft: 4, fontSize: 10 }}>
                      {sortDir === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                  {/* Resize handle */}
                  <div
                    onMouseDown={(e) => handleResizeStart(colIdx, e)}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      position: "absolute", right: 0, top: 0, bottom: 0, width: 6,
                      cursor: "col-resize",
                      background: resizingCol === colIdx ? "#2563eb" : "transparent",
                      zIndex: 1,
                    }}
                    onMouseEnter={(e) => { if (resizingCol === null) (e.target as HTMLElement).style.background = col.isAIO ? "#1d4ed8" : "#d1d5db"; }}
                    onMouseLeave={(e) => { if (resizingCol === null) (e.target as HTMLElement).style.background = "transparent"; }}
                  />
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>
                  No tickets match filters
                </td>
              </tr>
            ) : (
              rows.map((row, rowIdx) => (
                <tr
                  key={row.id}
                  onClick={() => setSelectedTicketId(row.id)}
                  style={{
                    cursor: "pointer",
                    background: row.aio_needs_review
                      ? "#fffbeb"
                      : rowIdx % 2 === 0 ? "white" : "#f9fafb",
                    borderBottom: "1px solid #f3f4f6",
                    transition: "background 0.1s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#eff6ff")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = row.aio_needs_review ? "#fffbeb" : rowIdx % 2 === 0 ? "white" : "#f9fafb")}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        width: col.width,
                        minWidth: col.minWidth,
                        maxWidth: col.width,
                        padding: "6px 10px",
                        fontSize: 11,
                        color: "#374151",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        borderRight: col.isAIO ? "1px solid #dbeafe" : "none",
                      }}
                      title={String(row[col.key as keyof TicketRow] ?? "")}
                    >
                      {renderCell(row, col, editingCell, setEditingCell, handleOverrideSave, taxonomy)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11, color: "#6b7280" }}>
        <span>
          Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()}
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          <PaginationButton label="" disabled={page <= 1} onClick={() => setPage(1)} />
          <PaginationButton label="◀" disabled={page <= 1} onClick={() => setPage(page - 1)} />
          <span style={{ padding: "4px 10px", fontSize: 11, color: "#374151", fontWeight: 600 }}>
            Page {page} of {totalPages}
          </span>
          <PaginationButton label="▶" disabled={page >= totalPages} onClick={() => setPage(page + 1)} />
          <PaginationButton label="" disabled={page >= totalPages} onClick={() => setPage(totalPages)} />
        </div>
      </div>

      {/* Ticket Detail Modal */}
      {selectedTicketId && (
        <TicketDetailModal
          uploadId={uploadId}
          ticketId={selectedTicketId}
          onClose={() => setSelectedTicketId(null)}
          onOverride={(field, value) => handleOverrideSave(selectedTicketId, field, value)}
        />
      )}
    </div>
  );
}


// ============================================================
// CELL RENDERERS
// ============================================================

function renderCell(
  row: TicketRow, col: ColumnDef,
  editingCell: any, setEditingCell: any,
  handleOverrideSave: any, taxonomy: any
) {
  const value = row[col.key as keyof TicketRow];

  // Editing mode
  if (editingCell && editingCell.rowId === row.id && editingCell.field === col.editField) {
    return (
      <AIOCellEditor
        field={col.editField!}
        currentValue={String(value || "")}
        taxonomy={taxonomy}
        onSave={(val) => handleOverrideSave(row.id, col.editField!, val)}
        onCancel={() => setEditingCell(null)}
      />
    );
  }

  switch (col.type) {
    case "badge":
      return <AutoStatusBadge status={String(value || "Manual")} />;

    case "confidence":
      const conf = Number(value || 0);
      const confColor = conf >= 80 ? "#16a34a" : conf >= 60 ? "#f59e0b" : "#ef4444";
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 30, height: 5, background: "#e5e7eb", borderRadius: 3 }}>
            <div style={{ width: `${conf}%`, height: 5, background: confColor, borderRadius: 3 }} />
          </div>
          <span style={{ fontSize: 10, color: confColor, fontWeight: 600 }}>{conf}%</span>
        </div>
      );

    case "evidence":
      return <span style={{ fontSize: 10, color: "#6b7280", fontStyle: "italic" }}>{String(value || "—")}</span>;

    case "cluster":
      const count = Number(value || 0);
      if (count === 0) return <span style={{ color: "#d1d5db" }}>—</span>;
      return <span style={{ fontSize: 10, color: "#8b5cf6", fontWeight: 600 }}>{count} similar</span>;

    case "savings":
      const savings = Number(value || 0);
      if (savings === 0) return <span style={{ color: "#d1d5db" }}>—</span>;
      return <span style={{ fontSize: 10, color: "#059669", fontWeight: 600 }}>₹{savings.toLocaleString()}</span>;

    case "editable":
      return (
        <div
          onDoubleClick={(e) => { e.stopPropagation(); setEditingCell({ rowId: row.id, field: col.editField }); }}
          style={{ cursor: "text", minHeight: 16 }}
          title="Double-click to edit"
        >
          {String(value || "—")}
        </div>
      );

    default:
      if (col.key === "mttr_hours" && value !== null && value !== undefined) {
        return <span>{Number(value).toFixed(1)}</span>;
      }
      if (col.key === "short_description") {
        return <span title={String(value || "")}>{String(value || "").slice(0, 60)}{String(value || "").length > 60 ? "..." : ""}</span>;
      }
      return <span>{String(value ?? "—")}</span>;
  }
}


// ============================================================
// AUTO STATUS BADGE
// ============================================================

function AutoStatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; color: string; border: string }> = {
    "Already Automated": { bg: "#d1fae5", color: "#065f46", border: "#a7f3d0" },
    "Can Be Automated": { bg: "#dbeafe", color: "#1e40af", border: "#93c5fd" },
    "Manual": { bg: "#fee2e2", color: "#991b1b", border: "#fca5a5" },
    "Excluded": { bg: "#f3f4f6", color: "#6b7280", border: "#d1d5db" },
  };
  const c = config[status] || config["Manual"];
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4,
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      whiteSpace: "nowrap",
    }}>
      {status}
    </span>
  );
}


// ============================================================
// PAGINATION BUTTON
// ============================================================

function PaginationButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "4px 10px", fontSize: 11, border: "1px solid #e5e7eb", borderRadius: 4,
        background: disabled ? "#f9fafb" : "white", color: disabled ? "#d1d5db" : "#374151",
        cursor: disabled ? "default" : "pointer",
      }}
    >
      {label}
    </button>
  );
}


// ============================================================
// TICKET DETAIL MODAL (single-click from row)
// ============================================================

function TicketDetailModal({ uploadId, ticketId, onClose, onOverride }: {
  uploadId: number;
  ticketId: number;
  onClose: () => void;
  onOverride: (field: string, value: string) => void;
}) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetchDetail();
  }, [ticketId]);

  const fetchDetail = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ticket-intelligence/ticket/${ticketId}`, { headers });
      if (res.ok) setDetail(await res.json());
    } catch (err) {
      console.error("Detail load error:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={modalOverlay}>
        <div style={{ ...modalBox, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ color: "#9ca3af" }}>Loading ticket detail...</span>
        </div>
      </div>
    );
  }

  if (!detail) return null;

  const d = detail;

  return (
    <div style={modalOverlay} onClick={onClose}>
      <div style={modalBox} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 20px", borderBottom: "1px solid #e5e7eb" }}>
          <div>
            <span style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>{d.ticket_number}</span>
            <AutoStatusBadge status={d.automation_status} />
          </div>
          <button onClick={onClose} style={{ fontSize: 18, color: "#9ca3af", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>

        {/* Body — Two panels */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, maxHeight: "70vh", overflow: "auto" }}>
          {/* LEFT: Original Ticket */}
          <div style={{ padding: 20, borderRight: "1px solid #e5e7eb", fontSize: 12, overflow: "auto" }}>
            <SectionTitle title="DESCRIPTION" />
            <p style={{ color: "#374151", lineHeight: 1.5, marginBottom: 12 }}>{d.short_description}</p>
            {d.description && d.description !== d.short_description && (
              <p style={{ color: "#6b7280", fontSize: 11, lineHeight: 1.5, marginBottom: 12 }}>{d.description.slice(0, 500)}</p>
            )}

            {d.resolution_notes && (
              <>
                <SectionTitle title="RESOLUTION" />
                <p style={{ color: "#374151", lineHeight: 1.5, marginBottom: 12 }}>{d.resolution_notes}</p>
              </>
            )}

            {d.work_notes && (
              <>
                <SectionTitle title="WORK NOTES" />
                <p style={{ color: "#6b7280", fontSize: 11, lineHeight: 1.4, marginBottom: 12 }}>{d.work_notes.slice(0, 500)}</p>
              </>
            )}

            <SectionTitle title="ROUTING" />
            <DetailRow label="Channel" value={d.channel} />
            <DetailRow label="Category" value={`${d.category} → ${d.subcategory}`} />
            <DetailRow label="Assignment Group" value={d.assignment_group} />
            <DetailRow label="Assigned To" value={d.assigned_to} />
            <DetailRow label="Resolved By" value={d.resolved_by} highlight />
            <DetailRow label="Priority" value={d.priority} />

            <SectionTitle title="TIMING" />
            <DetailRow label="Opened" value={d.opened ? new Date(d.opened).toLocaleString() : "—"} />
            <DetailRow label="Resolved" value={d.resolved ? new Date(d.resolved).toLocaleString() : "—"} />
            <DetailRow label="MTTR" value={d.mttr_hours ? `${d.mttr_hours}h (${Math.round(d.mttr_hours * 60)} min)` : "—"} highlight />
            <DetailRow label="Business Duration" value={d.business_duration ? `${d.business_duration}h` : "—"} />

            <SectionTitle title="COMPLEXITY" />
            <DetailRow label="Reassignments" value={String(d.reassignment_count)} highlight={d.reassignment_count >= 3} />
            <DetailRow label="Reopens" value={String(d.reopen_count)} highlight={d.reopen_count > 0} />

            {(d.configuration_item || d.location || d.company) && (
              <>
                <SectionTitle title="INFRASTRUCTURE" />
                <DetailRow label="Config Item" value={d.configuration_item} />
                <DetailRow label="Location" value={d.location} />
                <DetailRow label="Company" value={d.company} />
              </>
            )}
          </div>

          {/* RIGHT: ML Intelligence */}
          <div style={{ padding: 20, fontSize: 12, overflow: "auto", background: "#fafbfc" }}>
            <SectionTitle title="AUTOMATION VERDICT" />
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <AutoStatusBadge status={d.automation_status} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>{d.automation_score}% confidence</span>
            </div>
            <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3, marginBottom: 12 }}>
              <div style={{ height: 6, background: d.automation_score >= 80 ? "#16a34a" : d.automation_score >= 60 ? "#f59e0b" : "#ef4444", borderRadius: 3, width: `${d.automation_score}%` }} />
            </div>

            <DetailRow label="Solution" value={d.action} highlight />
            <DetailRow label="Evidence" value={d.evidence} />
            <DetailRow label="Reasoning" value={d.reasoning} />

            <SectionTitle title="CLASSIFICATION" />
            <DetailRow label="Tower" value={d.aio_tower} />
            <DetailRow label="Category" value={d.aio_category} />
            <DetailRow label="Sub Category" value={d.aio_subcategory} />
            <DetailRow label="Sub Category 1" value={d.aio_detail} />
            <DetailRow label="Summary" value={d.aio_summary} />
            <DetailRow label="Classified By" value={d.aio_classified_by} />

            {d.cluster_info && (
              <>
                <SectionTitle title="BERT CLUSTER" />
                <DetailRow label="Cluster ID" value={`#${d.cluster_info.cluster_id}`} />
                <DetailRow label="Total in Cluster" value={`${d.cluster_info.total_tickets} tickets`} highlight />
                <DetailRow label="Automation %" value={`${d.cluster_info.automation_pct}%`} />
                <DetailRow label="Avg MTTR" value={`${d.cluster_info.avg_mttr}h`} />

              </>
            )}

            <SimilarTickets uploadId={uploadId} ticketId={ticketId} />

            <SectionTitle title="ESTIMATED VALUE" />
            <DetailRow label="Automating this ticket" value={d.ticket_savings > 0 ? `₹${d.ticket_savings.toLocaleString()} of analyst effort` : "No saving (manual or already automated)"} />
            {d.cluster_savings > 0 && (
              <DetailRow label="Automatable tickets in this cluster" value={`₹${d.cluster_savings.toLocaleString()} over this dataset`} highlight />
            )}

            {/* Override */}
            <SectionTitle title="ACTIONS" />
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {["Already Automated", "Can Be Automated", "Manual"].map((status) => (
                <button
                  key={status}
                  onClick={() => { onOverride("automation_status", status); onClose(); }}
                  style={{
                    padding: "4px 10px", fontSize: 10, fontWeight: 600, borderRadius: 4, cursor: "pointer",
                    background: d.automation_status === status ? "#2563eb" : "white",
                    color: d.automation_status === status ? "white" : "#374151",
                    border: `1px solid ${d.automation_status === status ? "#2563eb" : "#d1d5db"}`,
                  }}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


// ============================================================
// SHARED COMPONENTS
// ============================================================

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af", letterSpacing: 1, marginTop: 16, marginBottom: 6, textTransform: "uppercase" }}>
      {title}
    </div>
  );
}

function DetailRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  if (!value || value === "—" || value === "") return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid #f3f4f6" }}>
      <span style={{ fontSize: 11, color: "#6b7280" }}>{label}</span>
      <span style={{ fontSize: 11, color: highlight ? "#2563eb" : "#374151", fontWeight: highlight ? 600 : 400, maxWidth: "60%", textAlign: "right", wordBreak: "break-word" }}>{value}</span>
    </div>
  );
}

// Modal styles
const modalOverlay: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 50,
  display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
};
const modalBox: React.CSSProperties = {
  background: "white", borderRadius: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
  width: "90vw", maxWidth: 1100, maxHeight: "85vh", overflow: "hidden",
};
/** Nearest tickets by meaning (description + closure notes), with how each was resolved. */
function SimilarTickets({ uploadId, ticketId }: { uploadId: number; ticketId: number }) {
  const [rows, setRows] = useState<any[] | null>(null);
  const [indexed, setIndexed] = useState(true);
  useEffect(() => {
    setRows(null);
    fetch(`${API_BASE}/api/rag/similar/${uploadId}/${ticketId}?k=5`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => r.json())
      .then((j) => { setIndexed(j.indexed !== false); setRows(j.tickets || []); })
      .catch(() => setRows([]));
  }, [uploadId, ticketId]);
  return (
    <>
      <SectionTitle title="SIMILAR TICKETS" />
      {rows === null ? (
        <div style={{ fontSize: 11, color: "#9ca3af" }}>Searching</div>
      ) : !indexed ? (
        <div style={{ fontSize: 11, color: "#9ca3af" }}>Search index not built for this dataset (Copilot page builds it).</div>
      ) : rows.length === 0 ? (
        <div style={{ fontSize: 11, color: "#9ca3af" }}>No similar tickets found.</div>
      ) : (
        rows.map((s) => (
          <div key={s.id} style={{ padding: "6px 0", borderBottom: "1px solid #f3f4f6", fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <span style={{ color: "#111827" }}><span style={{ fontFamily: "monospace" }}>{s.number}</span> {s.short_description}</span>
              <span style={{ color: "#6b7280", whiteSpace: "nowrap" }}>{s.mttr_hours != null ? `${s.mttr_hours}h` : "—"}</span>
            </div>
            <div style={{ color: "#6b7280", marginTop: 2 }}>
              {s.close_notes ? `Fixed: ${s.close_notes.slice(0, 160)}` : "No closure notes"}
              {s.resolved_by ? ` · ${s.resolved_by}` : ""}
            </div>
          </div>
        ))
      )}
    </>
  );
}
