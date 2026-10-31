/**
 * AIOCellEditor.tsx (v2)
 * ========================
 * Inline cell editor for AIO fields.
 * 
 * Changes:
 *   - Supports aio_detail (Sub Category 1) field
 *   - Dynamic options from taxonomy (not hardcoded)
 *   - Freetext for subcategory, detail, summary, action
 *   - Dropdown for tower, category, automation_status
 *   - Escape to cancel, Enter to save, blur to save
 */

"use client";

import React, { useState, useRef, useEffect } from "react";

interface AIOCellEditorProps {
  field: string;
  currentValue: string;
  taxonomy: any;
  onSave: (value: string) => void;
  onCancel: () => void;
}

// Fields that use dropdown vs freetext
const DROPDOWN_FIELDS = ["aio_tower", "aio_category", "automation_status"];
const FREETEXT_FIELDS = ["aio_subcategory", "aio_detail", "aio_summary", "action"];

export function AIOCellEditor({ field, currentValue, taxonomy, onSave, onCancel }: AIOCellEditorProps) {
  const [value, setValue] = useState(currentValue);
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onCancel();
    } else if (e.key === "Enter") {
      if (value !== currentValue && value.trim()) {
        onSave(value.trim());
      } else {
        onCancel();
      }
    }
  };

  const handleBlur = () => {
    if (value !== currentValue && value.trim()) {
      onSave(value.trim());
    } else {
      onCancel();
    }
  };

  // Get options from taxonomy
  const getOptions = (): string[] => {
    if (!taxonomy) return [];
    switch (field) {
      case "aio_tower":
        return (taxonomy.towers || []).map((t: any) => t.value || t);
      case "aio_category":
        return (taxonomy.categories || []).map((t: any) => t.value || t);
      case "automation_status":
        return ["Already Automated", "Can Be Automated", "Manual"];
      default:
        return [];
    }
  };

  const isDropdown = DROPDOWN_FIELDS.includes(field);

  if (isDropdown) {
    const options = getOptions();
    return (
      <select
        ref={inputRef as React.RefObject<HTMLSelectElement>}
        value={value}
        onChange={(e) => {
          const newVal = e.target.value;
          setValue(newVal);
          if (newVal !== currentValue && newVal) {
            onSave(newVal);
          }
        }}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          padding: "3px 6px",
          fontSize: 11,
          border: "2px solid #3b82f6",
          borderRadius: 4,
          outline: "none",
          background: "white",
          color: "#111827",
        }}
      >
        <option value="">— Select —</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
        {/* Allow custom value if current value not in options */}
        {value && !options.includes(value) && (
          <option value={value}>{value} (custom)</option>
        )}
      </select>
    );
  }

  // Freetext input
  return (
    <input
      ref={inputRef as React.RefObject<HTMLInputElement>}
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleBlur}
      onClick={(e) => e.stopPropagation()}
      placeholder={getPlaceholder(field)}
      style={{
        width: "100%",
        padding: "3px 6px",
        fontSize: 11,
        border: "2px solid #3b82f6",
        borderRadius: 4,
        outline: "none",
        background: "white",
        color: "#111827",
      }}
    />
  );
}

function getPlaceholder(field: string): string {
  switch (field) {
    case "aio_subcategory": return "e.g. Disk Space, Password Reset";
    case "aio_detail": return "e.g. Volume Capacity, SAP GUI/SSO";
    case "aio_summary": return "Crisp 1-line summary...";
    case "action": return "e.g. Auto-Remediation — Disk Cleanup";
    default: return "Enter value...";
  }
}