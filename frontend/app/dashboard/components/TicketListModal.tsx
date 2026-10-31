"use client";
import { useState, useEffect } from "react";
import TicketDetailModal from "./TicketDetailModal";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TicketListModalProps {
  uploadId: number;
  filter: any;
  onClose: () => void;
}

export default function TicketListModal({ uploadId, filter, onClose }: TicketListModalProps) {
  const [tickets, setTickets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedTicket, setSelectedTicket] = useState<any>(null);

  useEffect(() => {
    fetchTickets();
  }, [uploadId, filter, page]);

  async function fetchTickets() {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      const params = new URLSearchParams({
        page: page.toString(),
        limit: "20",
        ...filter,
      });
      
      const res = await fetch(`${API}/api/tickets/${uploadId}?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        const data = await res.json();
        setTickets(data.tickets || []);
        setTotalPages(data.total_pages || 1);
      }
    } catch (err) {
      console.error("Failed to fetch tickets:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    try {
      const token = localStorage.getItem("token");
      // Enriched CSV of the whole upload (the list filter is not applied to the export)
      const res = await fetch(`${API}/api/ticket-intelligence/${uploadId}/export/csv`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "tickets_export.csv";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      }
    } catch (err) {
      console.error("Export failed:", err);
    }
  }

  const filterTitle = filter?.category || filter?.solution || filter?.cluster_id 
    ? `Filtered: ${filter.category || filter.solution || `Cluster ${filter.cluster_id}`}`
    : "All Tickets";

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{filterTitle}</h2>
              <p className="text-sm text-gray-500">
                {tickets.length > 0 ? `Showing ${tickets.length} tickets` : "Loading..."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExport}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                Export CSV
              </button>
              <button
                onClick={onClose}
                className="p-1.5 text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="p-4 border-b border-gray-100">
            <div className="flex gap-2">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search tickets..."
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <select className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option>All Priorities</option>
                <option>P1</option>
                <option>P2</option>
                <option>P3</option>
                <option>P4</option>
              </select>
              <select className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option>Sort by Date</option>
                <option>Sort by Priority</option>
                <option>Sort by Confidence</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center h-48 text-gray-500">
                Loading tickets...
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="pb-3 font-medium">Ticket</th>
                    <th className="pb-3 font-medium">Description</th>
                    <th className="pb-3 font-medium">Category</th>
                    <th className="pb-3 font-medium">Solution</th>
                    <th className="pb-3 font-medium text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((ticket, i) => (
                    <tr
                      key={i}
                      onClick={() => setSelectedTicket(ticket)}
                      className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                    >
                      <td className="py-3">
                        <span className="font-medium text-blue-600">
                          {ticket.number || ticket.ticket_number || `TKT-${i + 1}`}
                        </span>
                      </td>
                      <td className="py-3 text-gray-600 max-w-md truncate">
                        {ticket.short_description || ticket.description?.slice(0, 80)}...
                      </td>
                      <td className="py-3">
                        <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                          {ticket.predicted_category || ticket.category || "Incident"}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
                          {ticket.predicted_solution || ticket.solution || "Auto-Remed"}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-green-500 rounded-full"
                              style={{ width: `${(ticket.confidence || 0.85) * 100}%` }}
                            />
                          </div>
                          <span className="text-gray-600">
                            {Math.round((ticket.confidence || 0.85) * 100)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between p-4 border-t border-gray-200">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              ← Previous
            </button>
            <span className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Ticket Detail Modal */}
      {selectedTicket && (
        <TicketDetailModal
          ticket={selectedTicket}
          onClose={() => setSelectedTicket(null)}
        />
      )}
    </>
  );
}
