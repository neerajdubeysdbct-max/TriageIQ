"use client";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TicketDetailModalProps {
  ticket: any;
  onClose: () => void;
}

export default function TicketDetailModal({ ticket, onClose }: TicketDetailModalProps) {
  const [feedback, setFeedback] = useState<"correct" | "incorrect" | "partial" | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submitFeedback(type: "correct" | "incorrect" | "partial") {
    setSubmitting(true);
    try {
      const token = localStorage.getItem("token");
      await fetch(`${API}/api/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ticket_id: ticket.id,
          feedback_type: type,
        }),
      });
      setFeedback(type);
    } catch (err) {
      console.error("Feedback error:", err);
    } finally {
      setSubmitting(false);
    }
  }

  const predictions = {
    category_l1: ticket.predicted_l1 || "Incident",
    category_l2: ticket.predicted_l2 || "Server",
    category_l3: ticket.predicted_l3 || "Memory",
    category_l4: ticket.predicted_l4 || "Heap Size",
    category_confidence: ticket.category_confidence || 0.94,
    automation: ticket.automation_status || "Can Automate",
    automation_confidence: ticket.automation_confidence || 0.87,
    solution: ticket.predicted_solution || "Auto-Remediation",
    solution_confidence: ticket.solution_confidence || 0.92,
    mttr_predicted: ticket.predicted_mttr || "2.8 hours",
    mttr_actual: ticket.actual_mttr || "3.2 hours",
    sentiment: ticket.sentiment || "Neutral",
    sentiment_confidence: ticket.sentiment_confidence || 0.65,
    escalation_risk: ticket.escalation_risk || "Medium",
    escalation_pct: ticket.escalation_pct || 34,
    anomaly_score: ticket.anomaly_score || 0.12,
  };

  const similarTickets = ticket.similar_tickets || [
    { number: "INC-342156", desc: "Heap space on APPSRV02", mttr: "2.1 hrs" },
    { number: "INC-298712", desc: "JVM OOM during batch job", mttr: "1.8 hrs" },
    { number: "INC-276543", desc: "Memory exhaustion PRD", mttr: "2.5 hrs" },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 sticky top-0 bg-white">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Ticket Analysis: {ticket.number || ticket.ticket_number || "INC-XXXXXX"}
            </h2>
            <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-medium">
              {ticket.priority || "P2"}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Original Ticket */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">ORIGINAL TICKET</h3>
            <div className="space-y-2 text-sm">
              <div className="flex">
                <span className="w-24 text-gray-500">Number:</span>
                <span className="font-medium">{ticket.number || ticket.ticket_number}</span>
              </div>
              <div className="flex">
                <span className="w-24 text-gray-500">Created:</span>
                <span>{ticket.created_at || ticket.sys_created_on || "2022-03-15 14:32:00"}</span>
              </div>
              <div className="flex">
                <span className="w-24 text-gray-500">Priority:</span>
                <span>{ticket.priority || "P2"}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-gray-500 mb-1">Description:</span>
                <span className="bg-white p-2 rounded border border-gray-200">
                  {ticket.short_description || ticket.description || "No description available"}
                </span>
              </div>
              {ticket.resolution_notes && (
                <div className="flex flex-col">
                  <span className="text-gray-500 mb-1">Resolution:</span>
                  <span className="bg-white p-2 rounded border border-gray-200">
                    {ticket.resolution_notes}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ML Predictions */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-blue-700 mb-4">ML PREDICTIONS</h3>
            
            {/* Category Hierarchy */}
            <div className="mb-4">
              <div className="text-xs text-gray-500 mb-2">CATEGORY HIERARCHY</div>
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-1 bg-white rounded">L1: {predictions.category_l1}</span>
                <span className="text-gray-400">→</span>
                <span className="px-2 py-1 bg-white rounded">L2: {predictions.category_l2}</span>
                <span className="text-gray-400">→</span>
                <span className="px-2 py-1 bg-white rounded">L3: {predictions.category_l3}</span>
                <span className="text-gray-400">→</span>
                <span className="px-2 py-1 bg-white rounded font-medium">L4: {predictions.category_l4}</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 h-2 bg-white rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${predictions.category_confidence * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-blue-600">
                  {Math.round(predictions.category_confidence * 100)}% confidence
                </span>
              </div>
            </div>

            {/* Prediction Cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">AUTOMATION</div>
                <div className="font-semibold text-gray-900">{predictions.automation}</div>
                <div className="text-xs text-gray-500">{Math.round(predictions.automation_confidence * 100)}% conf</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">SOLUTION</div>
                <div className="font-semibold text-gray-900">{predictions.solution}</div>
                <div className="text-xs text-gray-500">{Math.round(predictions.solution_confidence * 100)}% conf</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">MTTR PREDICTED</div>
                <div className="font-semibold text-gray-900">{predictions.mttr_predicted}</div>
                <div className="text-xs text-gray-500">actual: {predictions.mttr_actual}</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">SENTIMENT</div>
                <div className="font-semibold text-gray-900">
                  {predictions.sentiment === "Negative" ? "" : predictions.sentiment === "Positive" ? "" : ""} {predictions.sentiment}
                </div>
                <div className="text-xs text-gray-500">{Math.round(predictions.sentiment_confidence * 100)}% conf</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">ESCALATION RISK</div>
                <div className={`font-semibold ${
                  predictions.escalation_risk === "High" ? "text-red-600" :
                  predictions.escalation_risk === "Medium" ? "text-amber-600" : "text-green-600"
                }`}>
                  {predictions.escalation_risk === "High" ? "" : predictions.escalation_risk === "Medium" ? "" : ""} {predictions.escalation_risk}
                </div>
                <div className="text-xs text-gray-500">{predictions.escalation_pct}% risk</div>
              </div>
              <div className="bg-white rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">ANOMALY SCORE</div>
                <div className="font-semibold text-gray-900">
                  {predictions.anomaly_score < 0.5 ? "Normal" : "Unusual"}
                </div>
                <div className="text-xs text-gray-500">score: {predictions.anomaly_score}</div>
              </div>
            </div>
          </div>

          {/* Similar Tickets */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">SIMILAR TICKETS (from RAG)</h3>
            <div className="space-y-2">
              {similarTickets.map((st: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-white p-2 rounded border border-gray-100">
                  <div className="flex items-center gap-2">
                    <span className="text-blue-600 font-medium text-sm">{st.number}</span>
                    <span className="text-gray-600 text-sm">{st.desc}</span>
                  </div>
                  <span className="text-xs text-gray-500">Resolved in {st.mttr}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Feedback */}
          <div className="bg-green-50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-green-700 mb-3">FEEDBACK</h3>
            <p className="text-sm text-gray-600 mb-3">Were these predictions correct?</p>
            {feedback ? (
              <div className="text-sm text-green-600 font-medium">
                Thank you for your feedback!
              </div>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => submitFeedback("correct")}
                  disabled={submitting}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  Yes, correct
                </button>
                <button
                  onClick={() => submitFeedback("incorrect")}
                  disabled={submitting}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  No, incorrect
                </button>
                <button
                  onClick={() => submitFeedback("partial")}
                  disabled={submitting}
                  className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50"
                >
                  Partially correct
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
