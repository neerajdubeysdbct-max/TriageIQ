/**
 * PPTExportConfig.tsx (v2)
 * =========================
 * Modal for configuring PPT export.
 * - Pick which slides to include
 * - Set client name / date
 * - Download generated .pptx
 *
 * Changes: auth headers, clean labels, better slide descriptions
 */

"use client";

import React, { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SlideOption {
  id: string;
  label: string;
  description: string;
  default: boolean;
}

const SLIDE_OPTIONS: SlideOption[] = [
  { id: "title", label: "Title Slide", description: "Client name, date, ticket count", default: true },
  { id: "exec_summary", label: "Executive Summary", description: "KPI cards + key findings + estimated savings", default: true },
  { id: "tower_split", label: "Volume by Tower", description: "Bar chart — ticket distribution by technology tower", default: true },
  { id: "category_split", label: "Volume by Category", description: "Bar chart — issue category breakdown", default: true },
  { id: "top_subcats", label: "Top Sub Categories", description: "Table — top 15 specific issues with volumes", default: false },
  { id: "automation_overview", label: "Automation Overview", description: "Big numbers — Already Automated vs Can Be vs Manual", default: true },
  { id: "automation_tower", label: "Automation × Tower", description: "Stacked bar — automation status per tower", default: true },
  { id: "mttr_analysis", label: "MTTR Analysis", description: "Table — resolution time by tower (avg/min/max)", default: false },
  { id: "quick_wins", label: "Quick Wins", description: "Top automatable sub categories sorted by ROI", default: true },
  { id: "solution_roadmap", label: "Solution Roadmap", description: "3-phase plan: Quick Wins → Core → Advanced", default: true },
  { id: "roi_projection", label: "ROI Projection", description: "12/24 month savings estimate with assumptions", default: true },
  { id: "appendix", label: "Appendix", description: "Full data summary, ML confidence, tower distribution", default: false },
];

interface PPTExportConfigProps {
  uploadId: number;
  stats: any;
  onClose: () => void;
}

export function PPTExportConfig({ uploadId, stats, onClose }: PPTExportConfigProps) {
  const [selectedSlides, setSelectedSlides] = useState<string[]>(
    SLIDE_OPTIONS.filter((s) => s.default).map((s) => s.id)
  );
  const [clientName, setClientName] = useState("");
  const [dateStr, setDateStr] = useState(
    new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })
  );
  const [generating, setGenerating] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const toggleSlide = (id: string) => {
    setSelectedSlides((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedSlides(SLIDE_OPTIONS.map((s) => s.id));
  const selectNone = () => setSelectedSlides([]);

  const handleGenerate = async () => {
    if (selectedSlides.length === 0) return;
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/ticket-intelligence/${uploadId}/export/ppt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          slides: selectedSlides,
          client_name: clientName || "Client",
          date_str: dateStr,
          include_appendix: selectedSlides.includes("appendix"),
        }),
      });

      if (!res.ok) throw new Error("PPT generation failed");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Automation_Report_${clientName || "Client"}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>PowerPoint Export</div>
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>Configure your client presentation</div>
          </div>
          <button onClick={onClose} style={{ fontSize: 18, color: "#9ca3af", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
          {/* Client Info */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#374151", marginBottom: 4 }}>Client Name</label>
              <input
                type="text"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. Northwind Retail"
                style={{ width: "100%", padding: "8px 12px", fontSize: 12, border: "1px solid #d1d5db", borderRadius: 6, outline: "none" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#374151", marginBottom: 4 }}>Report Date</label>
              <input
                type="text"
                value={dateStr}
                onChange={(e) => setDateStr(e.target.value)}
                style={{ width: "100%", padding: "8px 12px", fontSize: 12, border: "1px solid #d1d5db", borderRadius: 6, outline: "none" }}
              />
            </div>
          </div>

          {/* Slide Selector */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>
              Select Slides ({selectedSlides.length}/{SLIDE_OPTIONS.length})
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={selectAll} style={{ fontSize: 11, color: "#2563eb", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>Select All</button>
              <button onClick={selectNone} style={{ fontSize: 11, color: "#9ca3af", background: "none", border: "none", cursor: "pointer" }}>Clear</button>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {SLIDE_OPTIONS.map((slide, idx) => {
              const isSelected = selectedSlides.includes(slide.id);
              return (
                <div
                  key={slide.id}
                  onClick={() => toggleSlide(slide.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                    border: isSelected ? "1px solid #93c5fd" : "1px solid #e5e7eb",
                    background: isSelected ? "#eff6ff" : "white",
                    transition: "all 0.15s",
                  }}
                >
                  {/* Checkbox */}
                  <div style={{
                    width: 20, height: 20, borderRadius: 4, display: "flex",
                    alignItems: "center", justifyContent: "center",
                    fontSize: 12, fontWeight: 700,
                    background: isSelected ? "#2563eb" : "white",
                    color: isSelected ? "white" : "transparent",
                    border: isSelected ? "2px solid #2563eb" : "2px solid #d1d5db",
                  }}>
                    ✓
                  </div>

                  {/* Number */}
                  <span style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace", width: 16 }}>{idx + 1}</span>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>{slide.label}</div>
                    <div style={{ fontSize: 11, color: "#9ca3af" }}>{slide.description}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "14px 24px", borderTop: "1px solid #e5e7eb",
          display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f9fafb",
        }}>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {stats?.total_tickets?.toLocaleString()} tickets • {selectedSlides.length} slides
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={onClose}
              style={{ padding: "8px 16px", fontSize: 12, color: "#6b7280", background: "white", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}
            >
              Cancel
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating || selectedSlides.length === 0}
              style={{
                padding: "8px 20px", fontSize: 12, fontWeight: 700,
                background: selectedSlides.length === 0 ? "#d1d5db" : "#2563eb",
                color: "white", border: "none", borderRadius: 6,
                cursor: selectedSlides.length === 0 ? "not-allowed" : "pointer",
                opacity: generating ? 0.6 : 1,
              }}
            >
              {generating ? "Generating..." : "Download .pptx"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 50,
  display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
};

const modalStyle: React.CSSProperties = {
  background: "white", borderRadius: 12, boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
  width: "100%", maxWidth: 640, maxHeight: "85vh", display: "flex", flexDirection: "column",
  overflow: "hidden",
};