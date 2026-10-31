"use client";
import { useState } from "react";

interface Ticket {
  id: string;
  summary: string;
  l1: string;
  l2: string;
  score: number;
  cluster: string;
  action: string;
  status: "Automate" | "Semi-Auto" | "Complex" | "Manual";
}

const STATUS_STYLES: Record<string, string> = {
  "Automate": "tag-green",
  "Semi-Auto": "tag-blue",
  "Complex": "tag-amber",
  "Manual": "tag-gray",
};

const L1_STYLES: Record<string, string> = {
  "Access Mgmt": "tag-blue",
  "Software": "tag-blue",
  "Network": "tag-blue",
  "Hardware": "tag-amber",
  "Security": "tag-red",
};

const FILTERS = ["All", "High Score", "Access Mgmt", "Software"];

export default function TicketTable({ tickets: propTickets }: { tickets?: any[] }) {
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");

  // Real tickets only; an empty upload shows an empty table
  const SOURCE = propTickets && propTickets.length > 0 ? propTickets.map((t) => ({
    id: t.id || "N/A",
    summary: t.summary || "N/A",
    l1: t.l1 || "Other",
    l2: t.l2 || "N/A",
    score: t.score ?? 0,
    cluster: t.cluster != null ? `Cluster ${t.cluster}` : "N/A",
    action: t.l4 || "Manual",
    status: t.score >= 75 ? "Automate" : t.score >= 50 ? "Semi-Auto" : "Complex",
  })) : [];

  const filtered = SOURCE.filter((t) => {
    const matchSearch =
      t.id.toLowerCase().includes(search.toLowerCase()) ||
      t.summary.toLowerCase().includes(search.toLowerCase());
    const matchFilter =
      activeFilter === "All" ||
      (activeFilter === "High Score" && t.score >= 80) ||
      t.l1 === activeFilter;
    return matchSearch && matchFilter;
  });

  return (
    <div className="table-card">
      {/* Header */}
      <div className="table-header">
        <div className="table-title-row">
          <span className="table-title">Automation Opportunity Workbench</span>
          <span className="table-count">{filtered.length.toLocaleString()} tickets</span>
        </div>
        <div className="table-controls">
          <div className="search-box">
            <span></span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tickets..."
              className="search-input"
            />
          </div>
          <div className="filter-row">
            {FILTERS.map((f) => (
              <button
                key={f}
                className={`filter-chip ${activeFilter === f ? "filter-active" : ""}`}
                onClick={() => setActiveFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
          <button className="export-btn">Export CSV</button>
        </div>
      </div>

      {/* Table */}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Ticket ID</th>
              <th>Summary</th>
              <th>L1 Category</th>
              <th>L2 Subcategory</th>
              <th>Auto Score</th>
              <th>Cluster</th>
              <th>Recommended Action</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id}>
                <td><span className="ticket-id">{t.id}</span></td>
                <td className="summary-cell">{t.summary}</td>
                <td>
                  <span className={`tag ${L1_STYLES[t.l1] || "tag-gray"}`}>{t.l1}</span>
                </td>
                <td>{t.l2}</td>
                <td>
                  <div className="score-wrap">
                    <div className="score-bar-bg">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${t.score}%`,
                          background: t.score >= 75 ? "#10B981" : t.score >= 50 ? "#4F46E5" : "#F59E0B",
                        }}
                      />
                    </div>
                    <span className="score-num">{t.score}</span>
                  </div>
                </td>
                <td><span className="tag tag-gray">{t.cluster}</span></td>
                <td>
                  <span className={`tag ${STATUS_STYLES[t.status]}`}>{t.action}</span>
                </td>
                <td>
                  <span className={`tag ${STATUS_STYLES[t.status]}`}>{t.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style jsx>{`
        .table-card {
          background: white;
          border: 1px solid #E5E7EB;
          border-radius: 10px;
          overflow: hidden;
        }
        .table-header {
          padding: 14px 18px;
          border-bottom: 1px solid #E5E7EB;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
        }
        .table-title-row {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .table-title { font-size: 13px; font-weight: 700; color: #111827; }
        .table-count { font-size: 11px; color: #6B7280; }
        .table-controls {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }
        .search-box {
          display: flex;
          align-items: center;
          gap: 8px;
          background: #F9FAFB;
          border: 1px solid #E5E7EB;
          border-radius: 7px;
          padding: 7px 12px;
          font-size: 12px;
        }
        .search-input {
          border: none;
          background: transparent;
          outline: none;
          font-size: 12px;
          color: #374151;
          width: 180px;
          font-family: inherit;
        }
        .filter-row { display: flex; gap: 6px; }
        .filter-chip {
          font-size: 11px;
          padding: 5px 12px;
          border-radius: 20px;
          border: 1px solid #E5E7EB;
          background: white;
          cursor: pointer;
          color: #6B7280;
          font-family: inherit;
          transition: all 0.15s;
        }
        .filter-chip:hover { border-color: #BFDBFE; color: #4F46E5; }
        .filter-active {
          background: #EFF6FF;
          border-color: #BFDBFE;
          color: #4338CA;
          font-weight: 600;
        }
        .export-btn {
          font-size: 12px;
          padding: 7px 12px;
          border-radius: 7px;
          border: 1px solid #E5E7EB;
          background: white;
          cursor: pointer;
          color: #374151;
          font-family: inherit;
          font-weight: 500;
        }
        .table-scroll { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        thead th {
          padding: 10px 16px;
          text-align: left;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.6px;
          color: #6B7280;
          background: #FAFAFA;
          border-bottom: 1px solid #E5E7EB;
          white-space: nowrap;
        }
        tbody tr {
          border-bottom: 1px solid #F3F4F6;
          cursor: pointer;
          transition: background 0.1s;
        }
        tbody tr:hover { background: #F8FAFF; }
        tbody tr:last-child { border-bottom: none; }
        td {
          padding: 10px 16px;
          color: #111827;
          white-space: nowrap;
        }
        .summary-cell {
          max-width: 220px;
          overflow: hidden;
          text-overflow: ellipsis;
          color: #374151;
        }
        .ticket-id {
          font-family: 'JetBrains Mono', monospace;
          color: #6B7280;
          font-size: 11px;
        }
        .score-wrap {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .score-bar-bg {
          width: 56px; height: 4px;
          background: #E5E7EB;
          border-radius: 2px;
          overflow: hidden;
        }
        .score-bar-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
        .score-num {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          font-weight: 700;
          color: #111827;
        }
        .tag {
          display: inline-flex;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 600;
          white-space: nowrap;
        }
        .tag-green { background: #ECFDF5; color: #065F46; }
        .tag-blue { background: #EFF6FF; color: #4338CA; }
        .tag-amber { background: #FFFBEB; color: #92400E; }
        .tag-red { background: #FEF2F2; color: #991B1B; }
        .tag-gray { background: #F3F4F6; color: #374151; }
      `}</style>
    </div>
  );
}
