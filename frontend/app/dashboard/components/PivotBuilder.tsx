/**
 * PivotBuilder.tsx (v2)
 * ======================
 * Drag-and-drop custom pivot builder.
 *
 * Changes:
 *   - Preset templates (1-click common pivots)
 *   - Cleaner 2-row layout instead of messy 4-panel
 *   - Dynamic fields include new columns (channel, resolved_by, aio_detail)
 *   - Clean labels (no "AIO" prefix)
 *   - Smart value formatting in results table
 */

"use client";

import React, { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// FIELD DEFINITIONS
// ============================================================

interface FieldDef {
  key: string;
  label: string;
  group: string;
}

const AVAILABLE_FIELDS: FieldDef[] = [
  { key: "aio_tower", label: "Tower", group: "Classification" },
  { key: "aio_category", label: "Category", group: "Classification" },
  { key: "aio_subcategory", label: "Sub Category", group: "Classification" },
  { key: "aio_detail", label: "Sub Category 1", group: "Classification" },
  { key: "aiops_solution_lever", label: "Solution Lever", group: "Classification" },
  { key: "aiops_automation_status", label: "Automation Status", group: "Automation" },
  { key: "is_already_automated", label: "Already Automated", group: "Automation" },
  { key: "can_be_automated", label: "Can Be Automated", group: "Automation" },
  { key: "assignment_group", label: "Assignment Group", group: "Ticket" },
  { key: "resolved_by", label: "Resolved By", group: "Ticket" },
  { key: "category", label: "SN Category", group: "Ticket" },
  { key: "subcategory", label: "SN SubCategory", group: "Ticket" },
  { key: "priority", label: "Priority", group: "Ticket" },
  { key: "channel", label: "Channel", group: "Ticket" },
  { key: "state", label: "State", group: "Ticket" },
  { key: "cluster_id", label: "BERT Cluster", group: "ML" },
];

const VALUE_OPTIONS = [
  { key: "count", label: "Count of Tickets" },
  { key: "avg_mttr", label: "Avg MTTR (hours)" },
  { key: "sum_mttr", label: "Total MTTR (hours)" },
];

// ============================================================
// PRESET TEMPLATES
// ============================================================

interface Preset {
  name: string;
  icon: string;
  rows: string[];
  columns: string[];
  values: string;
}

const PRESETS: Preset[] = [
  { name: "Tower × Automation", icon: "", rows: ["aio_tower"], columns: ["aiops_automation_status"], values: "count" },
  { name: "Category × Tower", icon: "", rows: ["aio_category"], columns: ["aio_tower"], values: "count" },
  { name: "Channel × Automation", icon: "", rows: ["channel"], columns: ["aiops_automation_status"], values: "count" },
  { name: "Assignment Group × MTTR", icon: "", rows: ["assignment_group"], columns: [], values: "avg_mttr" },
  { name: "Sub Category × Automation", icon: "", rows: ["aio_subcategory"], columns: ["aiops_automation_status"], values: "count" },
  { name: "Priority × Tower", icon: "", rows: ["priority"], columns: ["aio_tower"], values: "count" },
  { name: "Resolved By × Category", icon: "", rows: ["resolved_by"], columns: ["aio_category"], values: "count" },
  { name: "Cluster × Tower", icon: "", rows: ["cluster_id", "aio_tower"], columns: ["aio_subcategory"], values: "count" },
];

// ============================================================
// MAIN COMPONENT
// ============================================================

interface PivotBuilderProps {
  uploadId: number;
}

export function PivotBuilder({ uploadId }: PivotBuilderProps) {
  const [rowFields, setRowFields] = useState<string[]>([]);
  const [colFields, setColFields] = useState<string[]>([]);
  const [valueType, setValueType] = useState("count");
  const [pivotResult, setPivotResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const usedFields = [...rowFields, ...colFields];

  const getFieldLabel = (key: string) => AVAILABLE_FIELDS.find((f) => f.key === key)?.label || key;

  const handleAddToRows = (key: string) => {
    if (rowFields.length < 3 && !usedFields.includes(key)) setRowFields([...rowFields, key]);
  };

  const handleAddToCols = (key: string) => {
    if (colFields.length < 2 && !usedFields.includes(key)) setColFields([...colFields, key]);
  };

  const handleRemoveRow = (key: string) => setRowFields(rowFields.filter((f) => f !== key));
  const handleRemoveCol = (key: string) => setColFields(colFields.filter((f) => f !== key));

  const handlePreset = (preset: Preset) => {
    setRowFields(preset.rows);
    setColFields(preset.columns);
    setValueType(preset.values);
    setPivotResult(null);
    setError(null);
  };

  const handleGenerate = async () => {
    if (rowFields.length === 0) { setError("Select at least one row field"); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/custom-pivot`, {
        method: "POST",
        headers,
        body: JSON.stringify({ rows: rowFields, columns: colFields, values: valueType, filters: {} }),
      });
      if (!res.ok) throw new Error("Pivot generation failed");
      setPivotResult(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setRowFields([]);
    setColFields([]);
    setValueType("count");
    setPivotResult(null);
    setError(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 4 }}>

      {/* ── Presets ── */}
      <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 10 }}>Quick Presets</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {PRESETS.map((preset) => (
            <button
              key={preset.name}
              onClick={() => handlePreset(preset)}
              style={{
                padding: "8px 14px", fontSize: 11, fontWeight: 500,
                border: "1px solid #e5e7eb", borderRadius: 6, background: "white",
                cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#eff6ff"; (e.target as HTMLElement).style.borderColor = "#93c5fd"; }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "white"; (e.target as HTMLElement).style.borderColor = "#e5e7eb"; }}
            >
              <span>{preset.icon}</span>
              <span>{preset.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Builder ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 200px", gap: 12 }}>

        {/* Available Fields */}
        <div style={{ background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 10, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            Available Fields
          </div>
          {["Classification", "Automation", "Ticket", "ML"].map((group) => {
            const fields = AVAILABLE_FIELDS.filter((f) => f.group === group && !usedFields.includes(f.key));
            if (fields.length === 0) return null;
            return (
              <div key={group} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 9, color: "#9ca3af", fontWeight: 600, marginBottom: 4 }}>{group}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {fields.map((field) => (
                    <div key={field.key} style={{
                      padding: "4px 8px", background: "white", border: "1px solid #e5e7eb",
                      borderRadius: 4, fontSize: 11, display: "flex", alignItems: "center", gap: 6,
                      cursor: "default",
                    }}>
                      <span>{field.label}</span>
                      <button onClick={() => handleAddToRows(field.key)}
                        style={{ fontSize: 9, color: "#2563eb", background: "#eff6ff", border: "none", borderRadius: 3, padding: "1px 4px", cursor: "pointer", fontWeight: 700 }}>
                        +Row
                      </button>
                      <button onClick={() => handleAddToCols(field.key)}
                        style={{ fontSize: 9, color: "#7c3aed", background: "#f5f3ff", border: "none", borderRadius: 3, padding: "1px 4px", cursor: "pointer", fontWeight: 700 }}>
                        +Col
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Row Fields */}
        <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 10, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            Rows {rowFields.length > 0 && `(${rowFields.length})`}
          </div>
          {rowFields.length === 0 ? (
            <div style={{ fontSize: 11, color: "#93c5fd", fontStyle: "italic" }}>Click +Row to add fields</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {rowFields.map((key) => (
                <div key={key} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "6px 10px", background: "white", border: "1px solid #bfdbfe",
                  borderRadius: 6, fontSize: 12, fontWeight: 500,
                }}>
                  <span>{getFieldLabel(key)}</span>
                  <button onClick={() => handleRemoveRow(key)}
                    style={{ color: "#ef4444", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 700 }}>✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Column Fields */}
        <div style={{ background: "#f5f3ff", border: "1px solid #c4b5fd", borderRadius: 10, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#7c3aed", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            Columns {colFields.length > 0 && `(${colFields.length})`}
          </div>
          {colFields.length === 0 ? (
            <div style={{ fontSize: 11, color: "#c4b5fd", fontStyle: "italic" }}>Click +Col to add (optional)</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {colFields.map((key) => (
                <div key={key} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "6px 10px", background: "white", border: "1px solid #c4b5fd",
                  borderRadius: 6, fontSize: 12, fontWeight: 500,
                }}>
                  <span>{getFieldLabel(key)}</span>
                  <button onClick={() => handleRemoveCol(key)}
                    style={{ color: "#ef4444", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 700 }}>✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Values + Generate */}
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10, padding: 14, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
              Values
            </div>
            <select
              value={valueType}
              onChange={(e) => setValueType(e.target.value)}
              style={{ width: "100%", padding: "6px 8px", fontSize: 11, border: "1px solid #bbf7d0", borderRadius: 6, background: "white", outline: "none" }}
            >
              {VALUE_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
            <button
              onClick={handleGenerate}
              disabled={loading || rowFields.length === 0}
              style={{
                padding: "10px 14px", fontSize: 12, fontWeight: 700, borderRadius: 6,
                background: rowFields.length === 0 ? "#d1d5db" : "#2563eb",
                color: "white", border: "none", cursor: rowFields.length === 0 ? "not-allowed" : "pointer",
                opacity: loading ? 0.6 : 1,
              }}
            >
              {loading ? "Generating..." : "Generate Pivot"}
            </button>
            <button
              onClick={handleReset}
              style={{ padding: "6px 14px", fontSize: 11, color: "#6b7280", background: "white", border: "1px solid #e5e7eb", borderRadius: 6, cursor: "pointer" }}
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{ padding: "10px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 6, color: "#991b1b", fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* ── Live Preview / Results ── */}
      {rowFields.length > 0 && !pivotResult && !loading && (
        <div style={{ padding: "12px 16px", background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 11, color: "#6b7280" }}>
          Preview: <strong>{rowFields.map(getFieldLabel).join(" × ")}</strong>
          {colFields.length > 0 && <> by <strong>{colFields.map(getFieldLabel).join(" × ")}</strong></>}
          {" → "}{VALUE_OPTIONS.find((v) => v.key === valueType)?.label}
        </div>
      )}

      {/* ── Result Table ── */}
      {pivotResult && pivotResult.data && pivotResult.data.length > 0 && (
        <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid #f3f4f6", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f9fafb" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>{pivotResult.title}</span>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>{pivotResult.total_rows} rows</span>
          </div>
          <div style={{ overflow: "auto", maxHeight: 450 }}>
            <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
              <thead style={{ position: "sticky", top: 0 }}>
                <tr>
                  {Object.keys(pivotResult.data[0]).map((col) => (
                    <th key={col} style={{
                      padding: "8px 12px", textAlign: "left", background: "#f3f4f6",
                      borderBottom: "2px solid #e5e7eb", fontWeight: 700, color: "#374151",
                      whiteSpace: "nowrap", fontSize: 10,
                    }}>
                      {col.replace(/aio_|aiops_/g, "").replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pivotResult.data.map((row: any, i: number) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? "white" : "#f9fafb" }}>
                    {Object.keys(pivotResult.data[0]).map((col) => (
                      <td key={col} style={{
                        padding: "6px 12px", borderBottom: "1px solid #f3f4f6",
                        whiteSpace: "nowrap", color: "#374151",
                      }}>
                        {typeof row[col] === "number"
                          ? row[col].toLocaleString(undefined, { maximumFractionDigits: 2 })
                          : row[col] || "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}