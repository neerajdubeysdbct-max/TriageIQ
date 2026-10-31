'use client';

import React, { useState, useEffect, useCallback } from 'react';

// ============================================================
// TYPES
// ============================================================
interface Metrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number;
  confusion_matrix: number[][];
}

interface TrainingInfo {
  total_samples: number;
  positive_samples: number;
  negative_samples: number;
  class_ratio: string;
  cv_folds: number;
  params: Record<string, any>;
}

interface FeatureImportance {
  top_features: [string, number][];
  all_features: { gain: number[]; features: string[] };
}

interface ShapData {
  top_shap: { feature: string; importance: number }[];
  mean_abs_shap: number[];
  features: string[];
  sample_size: number;
  expected_value: number;
}

interface RocData {
  fpr: number[];
  tpr: number[];
  auc: number;
}

interface PrData {
  precision: number[];
  recall: number[];
}

interface CalibrationData {
  fraction_of_positives: number[];
  mean_predicted_value: number[];
}

interface FrontierData {
  automatable: { count: number; avg_confidence: number; score_distribution: number[] };
  manual: { count: number; avg_confidence: number; score_distribution: number[] };
  threshold: number;
  total: number;
}

interface XRayResults {
  status: string;
  label_source?: 'automation_classifier' | 'heuristic_rules';
  metric_meaning?: string;
  metrics: Metrics;
  training: TrainingInfo;
  feature_importance: FeatureImportance;
  shap: ShapData | null;
  roc_curve: RocData;
  pr_curve: PrData;
  calibration: CalibrationData | null;
  confidence_distribution: { counts: number[]; bin_edges: number[] };
  frontier: FrontierData;
  feature_stats: Record<string, { mean: number; std: number; min: number; max: number; median: number }>;
  trained_at: string;
  classification?: { total: number; already_automated: number; can_be_automated: number; manual: number };
}

interface WhatIfResult {
  base_prediction: { probability: number; label: string; confidence: number };
  modified_prediction: { probability: number; label: string; confidence: number };
  delta: number;
}

// ============================================================
// API HELPERS
// ============================================================
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getToken(): string {
  return localStorage.getItem('token') || '';
}

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API Error ${res.status}`);
  return res.json();
}

// ============================================================
// TABS CONFIG
// ============================================================
const TABS = [
  { id: 'overview', label: 'Model Overview', icon: '' },
  { id: 'features', label: 'Feature Importance', icon: '' },
  { id: 'shap', label: 'SHAP Explainability', icon: '' },
  { id: 'curves', label: 'ROC & PR Curves', icon: '' },
  { id: 'frontier', label: 'Automation Frontier', icon: '' },
  { id: 'whatif', label: 'What-If Simulator', icon: '' },
  { id: 'calibration', label: 'Confidence Analysis', icon: '' },
] as const;

type TabId = (typeof TABS)[number]['id'];

// ============================================================
// MAIN COMPONENT
// ============================================================
export default function XGBoostXRay({ uploadId }: { uploadId: number }) {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [results, setResults] = useState<XRayResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Check if results exist
  useEffect(() => {
    checkStatus();
  }, [uploadId]);

  const checkStatus = async () => {
    try {
      const status = await apiFetch(`/api/xgboost-xray/status/${uploadId}`);
      if (status.status === 'completed') {
        loadResults();
      }
    } catch {
      // Not trained yet
    }
  };

  const loadResults = async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/api/xgboost-xray/results/${uploadId}`);
      setResults(data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const triggerTraining = async () => {
    setTraining(true);
    setError(null);
    try {
      await apiFetch(`/api/xgboost-xray/train/${uploadId}`, { method: 'POST' });

      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const status = await apiFetch(`/api/xgboost-xray/status/${uploadId}`);
          if (status.status === 'completed') {
            clearInterval(poll);
            setTraining(false);
            loadResults();
          } else if (status.status === 'failed') {
            clearInterval(poll);
            setTraining(false);
            setError(status.error || 'Training failed');
          }
        } catch {
          // keep polling
        }
      }, 3000);

      // Timeout after 10 minutes
      setTimeout(() => {
        clearInterval(poll);
        if (training) {
          setTraining(false);
          setError('Training timeout — check backend logs');
        }
      }, 600000);
    } catch (e: any) {
      setTraining(false);
      setError(e.message);
    }
  };

  // ---- Not Trained Yet ----
  if (!results && !loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-white p-8">
        <div className="max-w-3xl mx-auto text-center py-20">
          <div className="text-6xl mb-6"></div>
          <h1 className="text-3xl font-bold mb-4 bg-gradient-to-r from-indigo-400 to-violet-500 bg-clip-text text-transparent">
            XGBoost X-Ray
          </h1>
          <p className="text-slate-400 mb-8 text-lg">
            Train a real XGBoost model on your ticket data. Get SHAP explainability, 
            feature importance, ROC curves, calibration analysis, and a What-If simulator.
          </p>
          {error && (
            <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-4 mb-6 text-red-300">
              {error}
            </div>
          )}
          <button
            onClick={triggerTraining}
            disabled={training}
            className="px-8 py-4 bg-gradient-to-r from-indigo-500 to-violet-600 rounded-xl font-semibold text-lg
                       hover:from-indigo-400 hover:to-violet-500 transition-all disabled:opacity-50 disabled:cursor-wait
                       shadow-lg shadow-indigo-500/20"
          >
            {training ? (
              <span className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Training Model...
              </span>
            ) : (
              'Train XGBoost Model'
            )}
          </button>
          <p className="text-slate-500 text-sm mt-4">
            Takes 30-90 seconds depending on dataset size
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-12 w-12 mx-auto mb-4 text-indigo-500" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-slate-400">Loading X-Ray results...</p>
        </div>
      </div>
    );
  }

  if (!results) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-3">
                <span className="bg-gradient-to-r from-indigo-400 to-violet-500 bg-clip-text text-transparent">
                  XGBoost X-Ray
                </span>
                <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full font-medium">
                  Model Trained
                </span>
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                {results.training.total_samples.toLocaleString()} tickets • 
                {results.training.cv_folds}-fold CV • 
                Trained {new Date(results.trained_at).toLocaleDateString()}
              </p>
              <p className="text-xs text-indigo-300/80 mt-1 max-w-2xl">
                {results.label_source === 'automation_classifier'
                  ? 'Surrogate model: explains the supervised automation classifier using operational features (resolution time, reassignments, timing, cluster). Its scores are fidelity, how often it agrees with that classifier, not accuracy against true labels. See Advanced → Model Evaluation for the tested accuracy of the classifier.'
                  : 'Trained on heuristic pseudo-labels (no supervised classifier has scored this upload). Its scores measure agreement with those rules, not accuracy against true labels.'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <MetricBadge label={results.label_source === 'automation_classifier' ? 'Fidelity' : 'Agreement'} value={`${(results.metrics.accuracy * 100).toFixed(1)}%`} color="blue" />
              <MetricBadge label="F1 Score" value={`${(results.metrics.f1_score * 100).toFixed(1)}%`} color="green" />
              <MetricBadge label="ROC AUC" value={`${(results.metrics.roc_auc * 100).toFixed(1)}%`} color="amber" />
              <button
                onClick={triggerTraining}
                disabled={training}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors border border-slate-700"
              >
                {training ? 'Retraining...' : '↻ Retrain'}
              </button>
            </div>
          </div>
          {/* Inline Search Bar */}
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"></span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && searchQuery.trim()) setSearchOpen(true); }}
                onFocus={() => { if (searchQuery.trim()) setSearchOpen(true); }}
                placeholder="Search any ticket... type INC number, keyword like 'disk space', 'password reset', 'VM down' and press Enter"
                className="w-full bg-slate-900/80 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
              />
            </div>
            <button
              onClick={() => { if (searchQuery.trim()) setSearchOpen(true); }}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-violet-600 rounded-xl text-sm font-semibold hover:from-indigo-400 hover:to-violet-500 transition-all whitespace-nowrap"
            >
              Analyze Ticket
            </button>
          </div>
          {/* Tabs */}
          <div className="flex gap-1 overflow-x-auto pb-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                  activeTab === tab.id
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right Drawer for Search Results */}
      <TicketSearchDrawer
        uploadId={uploadId}
        isOpen={searchOpen}
        query={searchQuery}
        onClose={() => setSearchOpen(false)}
        onQueryChange={setSearchQuery}
      />

      {/* Tab Content */}
      <div className="max-w-[1600px] mx-auto px-6 py-6">
        {activeTab === 'overview' && <OverviewTab results={results} uploadId={uploadId} />}
        {activeTab === 'features' && <FeatureImportanceTab results={results} />}
        {activeTab === 'shap' && <ShapTab results={results} />}
        {activeTab === 'curves' && <CurvesTab results={results} />}
        {activeTab === 'frontier' && <FrontierTab results={results} />}
        {activeTab === 'whatif' && <WhatIfTab uploadId={uploadId} results={results} />}
        {activeTab === 'calibration' && <CalibrationTab results={results} />}
      </div>
    </div>
  );
}

// ============================================================
// METRIC BADGE
// ============================================================
function MetricBadge({ label, value, color }: { label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    amber: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  return (
    <div className={`px-3 py-1.5 rounded-lg border text-sm ${colors[color]}`}>
      <span className="opacity-60 text-xs">{label}</span>
      <span className="ml-2 font-bold">{value}</span>
    </div>
  );
}

// ============================================================
// CARD WRAPPER
// ============================================================
function Card({ title, children, className = '' }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-slate-900/60 border border-slate-800 rounded-xl p-6 ${className}`}>
      {title && <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>}
      {children}
    </div>
  );
}

// ============================================================
// BAR CHART (SVG)
// ============================================================
function HorizontalBarChart({
  data,
  maxValue,
  color = '#6366f1',
  height = 28,
}: {
  data: { label: string; value: number }[];
  maxValue?: number;
  color?: string;
  height?: number;
}) {
  const max = maxValue || Math.max(...data.map((d) => d.value), 0.001);
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs text-slate-400 w-44 truncate text-right" title={d.label}>
            {d.label}
          </span>
          <div className="flex-1 bg-slate-800 rounded-full overflow-hidden" style={{ height }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.max((d.value / max) * 100, 1)}%`,
                background: `linear-gradient(90deg, ${color}88, ${color})`,
              }}
            />
          </div>
          <span className="text-xs text-slate-300 font-mono w-16 text-right">
            {d.value >= 0.01 ? d.value.toFixed(4) : d.value.toExponential(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// SVG LINE CHART
// ============================================================
function SVGLineChart({
  data,
  xLabel,
  yLabel,
  color = '#6366f1',
  diagonal = false,
  width = 400,
  height = 300,
}: {
  data: { x: number; y: number }[];
  xLabel: string;
  yLabel: string;
  color?: string;
  diagonal?: boolean;
  width?: number;
  height?: number;
}) {
  if (!data.length) return <p className="text-slate-500">No data available</p>;

  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const w = width - pad.left - pad.right;
  const h = height - pad.top - pad.bottom;

  const xMin = Math.min(...data.map((d) => d.x));
  const xMax = Math.max(...data.map((d) => d.x));
  const yMin = 0;
  const yMax = Math.max(...data.map((d) => d.y), 1);

  const scaleX = (v: number) => pad.left + ((v - xMin) / (xMax - xMin || 1)) * w;
  const scaleY = (v: number) => pad.top + h - ((v - yMin) / (yMax - yMin || 1)) * h;

  const path = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${scaleX(d.x)},${scaleY(d.y)}`).join(' ');

  // Area fill
  const areaPath = `${path} L${scaleX(data[data.length - 1].x)},${scaleY(0)} L${scaleX(data[0].x)},${scaleY(0)} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: height }}>
      {/* Grid */}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={pad.left} y1={scaleY(t * yMax)} x2={width - pad.right} y2={scaleY(t * yMax)} stroke="#334155" strokeWidth="1" />
          <text x={pad.left - 8} y={scaleY(t * yMax) + 4} fill="#64748b" fontSize="10" textAnchor="end">
            {(t * yMax).toFixed(1)}
          </text>
        </g>
      ))}

      {/* Diagonal reference */}
      {diagonal && (
        <line x1={pad.left} y1={scaleY(0)} x2={width - pad.right} y2={scaleY(yMax)} stroke="#475569" strokeWidth="1" strokeDasharray="4,4" />
      )}

      {/* Area */}
      <path d={areaPath} fill={`${color}15`} />

      {/* Line */}
      <path d={path} fill="none" stroke={color} strokeWidth="2.5" />

      {/* Axes labels */}
      <text x={width / 2} y={height - 4} fill="#94a3b8" fontSize="11" textAnchor="middle">
        {xLabel}
      </text>
      <text x={14} y={height / 2} fill="#94a3b8" fontSize="11" textAnchor="middle" transform={`rotate(-90,14,${height / 2})`}>
        {yLabel}
      </text>
    </svg>
  );
}

// ============================================================
// EXPLAINER MODAL
// ============================================================
function ExplainerModal({ isOpen, onClose, title, children }: { isOpen: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ============================================================
// WIDE MODAL (for ticket tables)
// ============================================================
function WideModal({ isOpen, onClose, title, children }: { isOpen: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ============================================================
// FEATURE EXPLANATIONS FOR SHAP TOOLTIPS
// ============================================================
const FEATURE_EXPLANATIONS: Record<string, { name: string; why: string }> = {
  mttr_hours: { name: 'Resolution Time (Hours)', why: 'How long the ticket took to resolve. Fast resolution (< 1h) strongly indicates automation — scripts run in minutes, humans take hours.' },
  cluster_mttr_var: { name: 'Cluster Resolution Consistency', why: 'How consistent the resolution time is within the ticket\'s semantic cluster. Zero variance = every similar ticket resolves identically = highly automatable.' },
  mttr_log: { name: 'Resolution Time (Log Scale)', why: 'Log-transformed MTTR captures patterns across orders of magnitude. Differentiates 5-min tickets from 5-hour tickets more effectively.' },
  desc_entropy: { name: 'Description Uniqueness', why: 'Shannon entropy of the ticket text. Low entropy = templated/repetitive text (like monitoring alerts). High entropy = unique/complex description needing human judgment.' },
  resolution_length: { name: 'Resolution Notes Length', why: 'Number of characters in resolution notes. Short notes (e.g. "restarted service") suggest simple fixes. Long notes suggest complex troubleshooting.' },
  cluster_size: { name: 'Cluster Size', why: 'How many similar tickets exist in this semantic cluster. Large cluster = this ticket type repeats frequently = high ROI for automation.' },
  desc_length: { name: 'Description Length', why: 'Length of the ticket description. Short, templated descriptions typically come from monitoring tools. Long descriptions suggest human-reported complex issues.' },
  desc_word_count: { name: 'Description Word Count', why: 'Number of words in the description. Monitoring alerts are concise (5-15 words). Complex issues are verbose (50+ words).' },
  kw_password: { name: 'Password Keyword', why: 'Whether the ticket mentions "password" or "pwd". Password reset tickets are classic automation candidates — standard process, no judgment needed.' },
  kw_disk: { name: 'Disk/Storage Keyword', why: 'Whether the ticket mentions "disk", "storage", "volume". Disk space alerts are prime auto-remediation candidates (cleanup scripts, threshold adjustments).' },
  kw_alert: { name: 'Alert/Monitoring Keyword', why: 'Whether the ticket mentions "alert", "threshold", "monitor". Monitoring alerts are typically machine-generated and follow standard response patterns.' },
  kw_network: { name: 'Network Keyword', why: 'Whether the ticket mentions "network", "connectivity", "DNS". Network issues range from simple (restart adapter) to complex (intermittent latency investigation).' },
  kw_backup: { name: 'Backup Keyword', why: 'Whether the ticket mentions "backup", "restore". Backup failures often have standard remediation procedures.' },
  hour_of_day: { name: 'Hour Ticket Was Opened', why: 'What hour the ticket was created. Off-hours tickets (nights/weekends) are often monitoring alerts. Business-hours tickets are more likely human-reported.' },
  day_of_week: { name: 'Day of Week', why: 'What day the ticket was opened. Weekend tickets are predominantly automated alerts. Weekday tickets have a mix of human and machine-generated.' },
  is_business_hours: { name: 'Business Hours Flag', why: 'Whether the ticket was opened during standard business hours (9am-5pm weekdays). Off-hours = likely monitoring alert = more automatable.' },
  is_weekend: { name: 'Weekend Flag', why: 'Whether the ticket was opened on Saturday/Sunday. Weekend tickets are almost exclusively automated monitoring alerts.' },
  reassignment_count: { name: 'Number of Team Handoffs', why: 'How many times the ticket was reassigned between teams. Zero = simple enough for one team. Multiple = complex cross-team investigation needed.' },
  reopen_count: { name: 'Number of Reopens', why: 'How many times the ticket was reopened after being resolved. Reopens suggest the initial fix didn\'t work — not a good automation candidate.' },
  zero_reassignment: { name: 'Zero Reassignment Flag', why: 'Whether the ticket was resolved without any reassignment. Single-team resolution strongly indicates a standard process that can be scripted.' },
  high_reassignment: { name: 'High Reassignment Flag', why: 'Whether the ticket was reassigned 3+ times. Multiple handoffs mean complex cross-team troubleshooting that needs human coordination.' },
  mttr_is_fast: { name: 'Fast Resolution Flag', why: 'Whether the ticket was resolved in under 1 hour. Fast resolution = standard procedure = prime automation candidate.' },
  repeatability: { name: 'Repeatability Score', why: 'How often this exact ticket pattern repeats. High repeatability = same problem, same solution, every time = automate it.' },
  has_resolution: { name: 'Has Resolution Notes', why: 'Whether resolution notes exist. Missing resolution notes sometimes indicate auto-resolved tickets or tickets closed without action.' },
  is_event: { name: 'Event Channel Flag', why: 'Whether the ticket came through the Event/Monitoring channel. Event-driven tickets are machine-generated and typically follow standard response playbooks.' },
  is_email: { name: 'Email Channel Flag', why: 'Whether the ticket was created via email. Email tickets are human-initiated and often contain unique requests requiring judgment.' },
  cluster_id: { name: 'BERT Cluster ID', why: 'Which semantic cluster this ticket belongs to (identified by BERT). Tickets in the same cluster share similar descriptions and often have similar automation potential.' },
};

function FeatureTooltip({ feature, value, shap }: { feature: string; value: number; shap: number }) {
  const [show, setShow] = useState(false);
  const info = FEATURE_EXPLANATIONS[feature];
  const isPositive = shap > 0;

  return (
    <div className="relative group" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      <span className="text-[10px] text-slate-400 w-28 text-right truncate font-mono cursor-help underline decoration-dotted decoration-slate-600" title={feature}>
        {feature}
      </span>
      {show && info && (
        <div className="fixed z-[200] pointer-events-none" style={{ top: 'var(--mouse-y, 50%)', left: 'var(--mouse-x, 50%)' }}>
          <div className="absolute bottom-2 right-0 w-80 bg-slate-800 border border-slate-600 rounded-xl p-3 shadow-2xl pointer-events-auto">
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <span className="text-xs font-semibold text-indigo-400">{info.name}</span>
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-semibold ${isPositive ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                {isPositive ? '↑ Automatable' : '↓ Manual'}
              </span>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed mb-2">{info.why}</p>
            <div className="flex items-center gap-4 text-[10px] text-slate-400 border-t border-slate-700 pt-1.5">
              <span>Value: <strong className="text-white">{value}</strong></span>
              <span>SHAP: <strong className={isPositive ? 'text-green-400' : 'text-red-400'}>{isPositive ? '+' : ''}{shap.toFixed(3)}</strong></span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// TICKET SEARCH DRAWER (right side panel — resizable)
// ============================================================
function TicketSearchDrawer({ uploadId, isOpen, query, onClose, onQueryChange }: {
  uploadId: number; isOpen: boolean; query: string; onClose: () => void; onQueryChange: (q: string) => void;
}) {
  const [results, setResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | 'auto' | 'manual' | 'high' | 'low'>('all');
  const [sortBy, setSortBy] = useState<'confidence' | 'mttr' | 'reassign'>('confidence');
  const [lastQuery, setLastQuery] = useState('');
  const [drawerWidth, setDrawerWidth] = useState(520);
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (isOpen && query.trim() && query !== lastQuery) {
      search();
    }
  }, [isOpen, query]);

  // Resizable drag handler
  useEffect(() => {
    if (!isResizing) return;
    const onMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      setDrawerWidth(Math.max(400, Math.min(newWidth, window.innerWidth - 100)));
    };
    const onMouseUp = () => setIsResizing(false);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => { window.removeEventListener('mousemove', onMouseMove); window.removeEventListener('mouseup', onMouseUp); };
  }, [isResizing]);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setExpandedIdx(null);
    setLastQuery(query);
    try {
      const data = await apiFetch(`/api/xgboost-xray/ticket-lookup/${uploadId}`, {
        method: 'POST',
        body: JSON.stringify({ query: query.trim() }),
      });
      setResults(data.tickets || []);
    } catch (e) {
      console.error('Search failed:', e);
    } finally {
      setSearching(false);
    }
  };

  const toggleFullWidth = () => {
    setDrawerWidth(drawerWidth > 800 ? 520 : window.innerWidth - 50);
  };

  // Filter & sort
  const filtered = results.filter(t => {
    if (filter === 'auto') return t.prediction === 'Automatable';
    if (filter === 'manual') return t.prediction === 'Manual';
    if (filter === 'high') return t.confidence >= 90;
    if (filter === 'low') return t.confidence < 60;
    return true;
  }).sort((a, b) => {
    if (sortBy === 'confidence') return b.confidence - a.confidence;
    if (sortBy === 'mttr') return (b.mttr_hours || 0) - (a.mttr_hours || 0);
    return (b.reassignment_count || 0) - (a.reassignment_count || 0);
  });

  const autoCount = results.filter(t => t.prediction === 'Automatable').length;
  const manualCount = results.filter(t => t.prediction === 'Manual').length;

  // 3-state classification
  const getAutomationStatus = (t: any) => {
    if (t.is_already_automated) return { label: 'Already Automated', color: 'text-green-400', bg: 'bg-green-500/20', icon: '', desc: 'No action needed — this is working' };
    if (t.prediction === 'Automatable') return { label: 'Can Be Automated', color: 'text-indigo-400', bg: 'bg-indigo-500/20', icon: '', desc: 'ACTION: Build automation for this' };
    return { label: 'Manual Required', color: 'text-red-400', bg: 'bg-red-500/20', icon: '', desc: 'Needs human judgment' };
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} className="fixed inset-0 bg-black/30 z-30" />

      {/* Resize handle */}
      <div
        onMouseDown={() => setIsResizing(true)}
        className="fixed top-0 h-full w-1.5 z-50 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60 transition-colors"
        style={{ right: drawerWidth - 2 }}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 h-full bg-slate-950 border-l border-slate-800 z-40 flex flex-col shadow-2xl transition-[width] duration-100"
        style={{ width: drawerWidth }}
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg"></span>
              <h3 className="text-base font-bold text-white">Ticket Intelligence</h3>
            </div>
            <div className="flex items-center gap-1.5">
              <button onClick={toggleFullWidth} className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs border border-slate-700 transition-colors" title="Toggle full width">
                {drawerWidth > 800 ? '◫ Collapse' : 'Expand'}
              </button>
              <button
                onClick={() => window.open(`/dashboard/xgboost-xray?upload_id=${uploadId}&search=${encodeURIComponent(query)}`, '_blank')}
                className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs border border-slate-700 transition-colors"
                title="Open in new tab"
              >
                ↗ New Tab
              </button>
              <button onClick={onClose} className="text-slate-400 hover:text-white text-lg ml-1">✕</button>
            </div>
          </div>

          {/* Search inside drawer */}
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') search(); }}
              placeholder="Ticket number or keyword..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button onClick={search} disabled={searching} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium disabled:opacity-40">
              {searching ? '' : '→'}
            </button>
          </div>

          {/* Result stats */}
          {results.length > 0 && (
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs text-slate-400">{results.length} found</span>
              <span className="text-xs text-green-400">✓ {autoCount} automatable</span>
              <span className="text-xs text-red-400">✗ {manualCount} manual</span>
            </div>
          )}

          {/* Quick Filters */}
          <div className="flex gap-1.5 flex-wrap">
            {[
              { id: 'all' as const, label: 'All', count: results.length },
              { id: 'auto' as const, label: '✓ Automatable', count: autoCount },
              { id: 'manual' as const, label: '✗ Manual', count: manualCount },
              { id: 'high' as const, label: 'High Conf', count: results.filter(t => t.confidence >= 90).length },
              { id: 'low' as const, label: 'Low Conf', count: results.filter(t => t.confidence < 60).length },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  filter === f.id
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-white'
                }`}
              >
                {f.label} ({f.count})
              </button>
            ))}
          </div>

          {/* Sort */}
          <div className="flex gap-1.5 mt-2">
            <span className="text-[10px] text-slate-500 self-center mr-1">Sort:</span>
            {[
              { id: 'confidence' as const, label: 'Confidence' },
              { id: 'mttr' as const, label: 'MTTR' },
              { id: 'reassign' as const, label: 'Reassignments' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => setSortBy(s.id)}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                  sortBy === s.id ? 'bg-slate-700 text-white' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {searching && (
            <div className="text-center py-8">
              <div className="animate-spin text-2xl mb-2"></div>
              <p className="text-sm text-slate-500">Analyzing tickets with XGBoost + SHAP...</p>
            </div>
          )}

          {!searching && filtered.length === 0 && results.length > 0 && (
            <p className="text-sm text-slate-500 text-center py-4">No tickets match the current filter</p>
          )}

          {!searching && results.length === 0 && lastQuery && (
            <div className="text-center py-8">
              <div className="text-3xl mb-2"></div>
              <p className="text-sm text-slate-500">No tickets found for "{lastQuery}"</p>
              <p className="text-xs text-slate-600 mt-1">Try a different keyword or ticket number</p>
            </div>
          )}

          {filtered.map((t, idx) => {
            const status = getAutomationStatus(t);
            return (
              <div key={idx} className="bg-slate-900/80 rounded-xl border border-slate-800 overflow-hidden hover:border-slate-700 transition-colors">
                {/* Ticket row */}
                <div
                  onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                  className="flex items-start gap-3 p-3 cursor-pointer"
                >
                  <div className={`mt-1 w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${status.bg}`}>
                    {status.icon === '' ? '' : status.icon === '' ? '' : ''}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="text-xs font-mono text-indigo-400 font-semibold">{t.ticket_number}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${status.bg} ${status.color}`}>
                        {status.label}
                      </span>
                      {t.correct === true && <span className="text-[9px] px-1 py-0.5 rounded bg-green-500/20 text-green-400">✓ Correct</span>}
                      {t.correct === false && <span className="text-[9px] px-1 py-0.5 rounded bg-red-500/20 text-red-400">✗ Wrong</span>}
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">{t.short_description}</p>
                    <div className="flex gap-3 mt-1.5 text-[10px] text-slate-500">
                      <span>MTTR: {t.mttr_hours != null ? t.mttr_hours + 'h' : '—'}</span>
                      <span>Reassign: {t.reassignment_count}</span>
                      <span>{t.assignment_group}</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className={`text-lg font-bold ${status.color}`}>
                      {t.confidence}%
                    </div>
                    <div className={`text-[10px] ${status.color}`}>
                      {t.prediction}
                    </div>
                  </div>
                </div>

                {/* Expanded SHAP waterfall + Cluster Intelligence */}
                {expandedIdx === idx && t.shap_waterfall && t.shap_waterfall.length > 0 && (
                  <div className="border-t border-slate-800 p-3 bg-slate-950/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">SHAP Waterfall</span>
                      <span className="text-[10px] text-slate-600">Hover any feature for explanation</span>
                    </div>
                    <div className="space-y-1">
                      {t.shap_waterfall.slice(0, 10).map((s: any, si: number) => {
                        const maxShap = Math.max(...t.shap_waterfall.map((x: any) => Math.abs(x.shap)));
                        const pct = Math.abs(s.shap) / maxShap * 100;
                        const isPositive = s.shap > 0;
                        return (
                          <div key={si} className="flex items-center gap-1.5">
                            <FeatureTooltip feature={s.feature} value={s.value} shap={s.shap} />
                            <span className="text-[9px] text-slate-600 w-14 text-right font-mono">{s.value}</span>
                            <div className="flex-1 flex items-center h-3">
                              <div className="w-full flex">
                                <div className="w-1/2 flex justify-end">
                                  {!isPositive && <div className="h-2.5 rounded-l bg-red-500/70" style={{ width: `${pct}%` }} />}
                                </div>
                                <div className="w-px bg-slate-700" />
                                <div className="w-1/2">
                                  {isPositive && <div className="h-2.5 rounded-r bg-green-500/70" style={{ width: `${pct}%` }} />}
                                </div>
                              </div>
                            </div>
                            <span className={`text-[9px] font-mono w-12 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                              {isPositive ? '+' : ''}{s.shap.toFixed(2)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-2 flex gap-3 text-[9px] text-slate-600">
                      <span>→ Automatable</span>
                      <span>→ Manual</span>
                    </div>

                    {/* Cluster Intelligence + LLM Recommendations */}
                    <TicketIntelligencePanel uploadId={uploadId} ticket={t} status={status} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ============================================================
// TICKET INTELLIGENCE PANEL (cluster stats + LLM recommendations)
// ============================================================
function TicketIntelligencePanel({ uploadId, ticket, status }: { uploadId: number; ticket: any; status: any }) {
  const [context, setContext] = useState<any>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [recSource, setRecSource] = useState<string>('');
  const [loadingCtx, setLoadingCtx] = useState(true);
  const [loadingRec, setLoadingRec] = useState(false);
  const [hoursSaveable, setHoursSaveable] = useState<number | null>(null);
  const [overrideStatus, setOverrideStatus] = useState<string | null>(null);
  const [overrideSaving, setOverrideSaving] = useState(false);

  useEffect(() => {
    loadContext();
  }, [ticket.ticket_number]);

  const loadContext = async () => {
    setLoadingCtx(true);
    try {
      const data = await apiFetch(`/api/xgboost-xray/ticket-context/${uploadId}/${ticket.ticket_number}`);
      setContext(data);
      loadRecommendations(data);
    } catch (e) {
      console.error('Context failed:', e);
    } finally {
      setLoadingCtx(false);
    }
  };

  const saveOverride = async (newStatus: string) => {
    setOverrideSaving(true);
    try {
      await apiFetch(`/api/xgboost-xray/ticket-override/${uploadId}`, {
        method: 'POST',
        body: JSON.stringify({
          ticket_number: ticket.ticket_number,
          override_status: newStatus,
        }),
      });
      setOverrideStatus(newStatus);
    } catch (e) {
      console.error('Override failed:', e);
    } finally {
      setOverrideSaving(false);
    }
  };

  const loadRecommendations = async (ctx: any) => {
    setLoadingRec(true);
    try {
      const cs = ctx?.cluster_stats;
      const data = await apiFetch(`/api/xgboost-xray/ticket-recommend/${uploadId}`, {
        method: 'POST',
        body: JSON.stringify({
          ticket_number: ticket.ticket_number,
          short_description: ticket.short_description,
          assignment_group: ticket.assignment_group,
          mttr_hours: ticket.mttr_hours,
          reassignment_count: ticket.reassignment_count,
          cluster_total: cs?.total || 0,
          automated_count: cs?.automated_count || 0,
          not_automated_count: cs?.not_automated_count || 0,
          avg_auto_mttr: cs?.avg_auto_mttr,
          avg_manual_mttr: cs?.avg_manual_mttr,
          top_tools: (cs?.tools || []).map((t: any) => t.tool).slice(0, 5),
          aiops_solution_lever: ctx?.aiops_solution_lever,
        }),
      });
      setRecommendations(data.recommendations || []);
      setRecSource(data.source || 'unknown');
      setHoursSaveable(data.hours_saveable);
    } catch (e) {
      console.error('Recommendations failed:', e);
      setRecSource('error');
    } finally {
      setLoadingRec(false);
    }
  };

  const cs = context?.cluster_stats;

  return (
    <div className="mt-3 space-y-2.5">
      {/* Status + Evidence */}
      <div className={`border rounded-lg p-2.5 ${
        status.label === 'Already Automated' ? 'bg-green-500/5 border-green-500/20' :
        status.label === 'Can Be Automated' ? 'bg-indigo-500/5 border-indigo-500/20' :
        'bg-red-500/5 border-red-500/20'
      }`}>
        <div className={`text-[10px] font-semibold mb-1.5 ${status.color}`}>{status.icon} {status.label}</div>
        {loadingCtx ? (
          <p className="text-[10px] text-slate-500">Loading ticket evidence...</p>
        ) : context ? (
          <div className="space-y-1 text-[11px]">
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {context.aiops_solution_lever && (
                <div><span className="text-slate-500">Tool: </span><span className="text-white font-semibold">{context.aiops_solution_lever}</span></div>
              )}
              {context.aiops_automation_status && (
                <div><span className="text-slate-500">Status: </span><span className="text-white">{context.aiops_automation_status}</span></div>
              )}
              {context.resolved_by && (
                <div><span className="text-slate-500">Resolved by: </span><span className="text-white">{context.resolved_by}</span></div>
              )}
              {context.resolved_by_group && (
                <div><span className="text-slate-500">Team: </span><span className="text-white">{context.resolved_by_group}</span></div>
              )}
              {context.opened && (
                <div><span className="text-slate-500">Opened: </span><span className="text-slate-300">{context.opened}</span></div>
              )}
              {context.resolved && (
                <div><span className="text-slate-500">Resolved: </span><span className="text-slate-300">{context.resolved}</span></div>
              )}
            </div>
            {!context.aiops_solution_lever && status.label !== 'Already Automated' && (
              <div className="mt-1 text-[10px] text-red-400/80 italic">
                No automation tool assigned — resolved_by: {context.resolved_by || 'unknown'} (human) | MTTR: {ticket.mttr_hours}h | Reassignments: {ticket.reassignment_count}
              </div>
            )}
          </div>
        ) : null}

        {/* Human-in-the-Loop Feedback */}
        {!loadingCtx && (
          <div className="mt-2 pt-2 border-t border-slate-700/50">
            {overrideStatus ? (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-green-400">✓ Corrected to: <strong>{overrideStatus}</strong></span>
                <button onClick={() => setOverrideStatus(null)} className="text-[9px] text-slate-500 hover:text-slate-300 underline">undo</button>
                <span className="text-[9px] text-slate-600 ml-auto">Will improve next training run</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[9px] text-slate-500 mr-1">Correct?</span>
                <button
                  onClick={() => saveOverride('Already Automated')}
                  disabled={overrideSaving}
                  className={`px-2 py-0.5 rounded text-[9px] font-medium transition-colors ${
                    status.label === 'Already Automated'
                      ? 'bg-green-500/30 text-green-400 border border-green-500/40'
                      : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-green-400 hover:border-green-500/30'
                  }`}
                >
                  Already Automated
                </button>
                <button
                  onClick={() => saveOverride('Can Be Automated')}
                  disabled={overrideSaving}
                  className={`px-2 py-0.5 rounded text-[9px] font-medium transition-colors ${
                    status.label === 'Can Be Automated'
                      ? 'bg-indigo-500/30 text-indigo-400 border border-indigo-500/40'
                      : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-indigo-400 hover:border-indigo-500/30'
                  }`}
                >
                  Can Be Automated
                </button>
                <button
                  onClick={() => saveOverride('Manual')}
                  disabled={overrideSaving}
                  className={`px-2 py-0.5 rounded text-[9px] font-medium transition-colors ${
                    status.label === 'Manual Required'
                      ? 'bg-red-500/30 text-red-400 border border-red-500/40'
                      : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-red-400 hover:border-red-500/30'
                  }`}
                >
                  Manual
                </button>
                {overrideSaving && <span className="text-[9px] text-slate-500 animate-pulse">Saving...</span>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Cluster Intelligence */}
      {cs && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2.5">
          <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-2">Cluster Intelligence ({cs.total?.toLocaleString()} similar tickets)</div>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="bg-green-500/10 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-green-400">{cs.automated_count?.toLocaleString()}</div>
              <div className="text-[9px] text-green-400/80">Automated ({cs.automated_pct}%)</div>
              {cs.avg_auto_mttr != null && <div className="text-[9px] text-slate-500">avg {cs.avg_auto_mttr}h MTTR</div>}
            </div>
            <div className="bg-red-500/10 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-red-400">{cs.not_automated_count?.toLocaleString()}</div>
              <div className="text-[9px] text-red-400/80">Not Automated</div>
              {cs.avg_manual_mttr != null && <div className="text-[9px] text-slate-500">avg {cs.avg_manual_mttr}h MTTR</div>}
            </div>
          </div>
          {/* Tools in use */}
          {cs.tools && cs.tools.length > 0 && (
            <div className="space-y-1">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">Tools in this cluster:</div>
              {cs.tools.slice(0, 5).map((tool: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-[10px]">
                  <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div className="h-full bg-purple-500/60 rounded-full" style={{ width: `${tool.percentage}%` }} />
                  </div>
                  <span className="text-slate-300 w-32 truncate" title={tool.tool}>{tool.tool}</span>
                  <span className="text-slate-500 w-10 text-right">{tool.count}</span>
                  <span className="text-slate-500 w-10 text-right">{tool.percentage}%</span>
                  {tool.avg_mttr != null && <span className="text-slate-500 w-12 text-right">{tool.avg_mttr}h</span>}
                </div>
              ))}
            </div>
          )}
          {/* Hours saveable */}
          {cs.hours_saveable_per_year != null && cs.hours_saveable_per_year > 0 && (
            <div className="mt-2 bg-indigo-500/10 rounded-lg p-2 flex items-center gap-3">
              <span className="text-xl"></span>
              <div>
                <div className="text-sm font-bold text-indigo-400">{cs.hours_saveable_per_year.toLocaleString()} hours/year saveable</div>
                <div className="text-[10px] text-slate-400">
                  {cs.not_automated_count} tickets × ({cs.avg_manual_mttr}h - {cs.avg_auto_mttr}h) per ticket
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Recommendations */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2.5">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">Automation Recommendations</div>
          {recSource && (
            <span className={`text-[8px] px-1.5 py-0.5 rounded-full ${
              recSource === 'llm' ? 'bg-cyan-500/20 text-cyan-400' :
              recSource === 'data-driven' ? 'bg-purple-500/20 text-purple-400' :
              'bg-red-500/20 text-red-400'
            }`}>
              {recSource === 'llm' ? 'AI Generated' : recSource === 'data-driven' ? 'Data-Driven' : 'Unavailable'}
            </span>
          )}
        </div>
        {loadingRec ? (
          <div className="flex items-center gap-2 py-2">
            <div className="animate-spin text-sm"></div>
            <span className="text-[11px] text-slate-500">Generating recommendations{recSource !== 'llm' ? '...' : ' with AI Copilot...'}</span>
          </div>
        ) : recommendations.length > 0 ? (
          <div className="space-y-1.5">
            {recommendations.map((rec: any, i: number) => (
              <div key={i} className="flex gap-2 text-[11px] bg-slate-800/40 rounded-lg p-2">
                <span className="text-cyan-400 font-bold w-4 flex-shrink-0">{i + 1}.</span>
                <div className="flex-1">
                  <span className="text-white font-semibold">{rec.tool}</span>
                  <span className="text-slate-400"> — {rec.approach}</span>
                  {rec.expected_mttr && <span className="text-green-400 text-[9px] ml-1">(→ {rec.expected_mttr})</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[10px] text-slate-500">No recommendations available</p>
        )}
        {hoursSaveable != null && hoursSaveable > 0 && (
          <div className="mt-1.5 text-[10px] text-indigo-400/80">
            Automating remaining tickets could save ~{hoursSaveable.toLocaleString()} hours/year
          </div>
        )}
        {recSource === 'data-driven' && (
          <div className="mt-1.5 text-[9px] text-slate-600 italic">
            Start AI Copilot (Ollama) for more detailed, context-aware recommendations
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// SAMPLE TICKETS PANEL (inside CM modal)
// ============================================================
function SampleTicketsPanel({ uploadId, category }: { uploadId: number; category: string }) {
  const [tickets, setTickets] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 10;

  useEffect(() => {
    loadTickets(0);
  }, [category]);

  const loadTickets = async (newOffset: number) => {
    setLoading(true);
    try {
      const data = await apiFetch(`/api/xgboost-xray/sample-tickets/${uploadId}?category=${category}&offset=${newOffset}&limit=${limit}`);
      if (newOffset === 0) {
        setTickets(data.tickets || []);
      } else {
        setTickets(prev => [...prev, ...(data.tickets || [])]);
      }
      setTotal(data.total || 0);
      setOffset(newOffset);
    } catch (e) {
      console.error('Failed to load sample tickets:', e);
    } finally {
      setLoading(false);
    }
  };

  const categoryColors: Record<string, string> = {
    tp: 'text-blue-400', tn: 'text-green-400', fp: 'text-red-400', fn: 'text-violet-400'
  };

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">
          Sample Tickets ({total.toLocaleString()} total)
        </span>
        {loading && <span className="text-xs text-slate-500">Loading...</span>}
      </div>

      {tickets.length === 0 && !loading && (
        <p className="text-xs text-slate-500 text-center py-2">No tickets in this category</p>
      )}

      <div className="space-y-1.5 max-h-60 overflow-y-auto">
        {tickets.map((t, i) => (
          <div key={i} className="flex items-center gap-3 bg-slate-800/40 rounded-lg px-3 py-2 text-xs">
            <span className="font-mono text-indigo-400 w-24 flex-shrink-0">{t.ticket_number}</span>
            <span className="text-slate-300 flex-1 truncate" title={t.short_description}>{t.short_description}</span>
            <span className="text-slate-500 w-14 text-right">{t.mttr_hours != null ? t.mttr_hours + 'h' : '—'}</span>
            <span className={`w-12 text-right font-semibold ${categoryColors[category] || 'text-slate-300'}`}>{t.confidence}%</span>
          </div>
        ))}
      </div>

      {tickets.length < total && (
        <button
          onClick={() => loadTickets(offset + limit)}
          disabled={loading}
          className="mt-2 w-full py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-slate-400 transition-colors border border-slate-700"
        >
          {loading ? 'Loading...' : `Load More (${tickets.length} of ${total.toLocaleString()})`}
        </button>
      )}
    </div>
  );
}

// ============================================================
// METRIC EXPLAINER CONTENT
// ============================================================
function getMetricExplainer(label: string, value: number, cm: number[][]) {
  const total = cm ? cm[0][0] + cm[0][1] + cm[1][0] + cm[1][1] : 0;
  const tn = cm?.[0]?.[0] || 0;
  const fp = cm?.[0]?.[1] || 0;
  const fn = cm?.[1]?.[0] || 0;
  const tp = cm?.[1]?.[1] || 0;
  const pct = (value * 100).toFixed(1);

  const explainers: Record<string, { meaning: string; formula: string; example: string; business: string }> = {
    'Accuracy': {
      meaning: `Out of every 100 tickets, the model correctly classifies ${Math.round(value * 100)} as either automatable or manual.`,
      formula: `(True Positives + True Negatives) / Total = (${tp.toLocaleString()} + ${tn.toLocaleString()}) / ${total.toLocaleString()} = ${pct}%`,
      example: `The model looked at ${total.toLocaleString()} tickets. It got ${(tp + tn).toLocaleString()} right and ${(fp + fn).toLocaleString()} wrong. Think of it like a test score — ${pct}% correct answers.`,
      business: `For every 1,000 tickets analyzed, approximately ${Math.round((1 - value) * 1000)} will be misclassified. This is the overall error rate your team should expect.`,
    },
    'Precision': {
      meaning: `When the model says "this ticket can be automated," it's correct ${pct}% of the time. Only ${fp.toLocaleString()} tickets were wrongly flagged as automatable.`,
      formula: `True Positives / (True Positives + False Positives) = ${tp.toLocaleString()} / (${tp.toLocaleString()} + ${fp.toLocaleString()}) = ${pct}%`,
      example: `Imagine the model hands you a list of ${(tp + fp).toLocaleString()} tickets saying "automate these." ${tp.toLocaleString()} of them truly can be automated. Only ${fp.toLocaleString()} would fail if you tried — that's a ${((fp / Math.max(tp + fp, 1)) * 100).toFixed(2)}% waste rate.`,
      business: `This directly impacts your automation ROI. High precision means almost zero wasted implementation effort — every ticket we recommend for automation will actually work.`,
    },
    'Recall': {
      meaning: `The model finds ${pct}% of ALL automatable tickets in your data. It misses ${fn.toLocaleString()} tickets that could have been automated.`,
      formula: `True Positives / (True Positives + False Negatives) = ${tp.toLocaleString()} / (${tp.toLocaleString()} + ${fn.toLocaleString()}) = ${pct}%`,
      example: `There are ${(tp + fn).toLocaleString()} truly automatable tickets. The model correctly identifies ${tp.toLocaleString()} of them. The remaining ${fn.toLocaleString()} are missed opportunities — tickets that COULD be automated but the model was conservative about.`,
      business: `The ${fn.toLocaleString()} missed tickets are cases the model scores as manual although its training labels say automatable; review them before treating them as automation potential.`,
    },
    'F1 Score': {
      meaning: `The balance between Precision (${(cm ? tp / Math.max(tp + fp, 1) * 100 : 0).toFixed(1)}%) and Recall (${(cm ? tp / Math.max(tp + fn, 1) * 100 : 0).toFixed(1)}%). If either drops, F1 drops sharply.`,
      formula: `2 × (Precision × Recall) / (Precision + Recall) = ${pct}%`,
      example: `A model could get 100% Precision by only flagging the 10 most obvious tickets (but missing thousands). Or 100% Recall by flagging everything (but half being wrong). F1 of ${pct}% means the model is excellent at BOTH — it finds most opportunities AND rarely makes wrong recommendations.`,
      business: `F1 here is measured against the labels this model was trained on (see the note at the top of the page), so it shows how faithfully it reproduces them, not real-world accuracy.`,
    },
  };

  return explainers[label] || { meaning: '', formula: '', example: '', business: '' };
}

function getCMExplainer(cell: string, count: number, cm: number[][]) {
  const total = cm[0][0] + cm[0][1] + cm[1][0] + cm[1][1];
  const explainers: Record<string, { meaning: string; realWorld: string; icon: string }> = {
    'True Negative': {
      meaning: `${count.toLocaleString()} tickets are genuinely MANUAL, and the model correctly said "manual." These are complex tickets that need human judgment — investigation, troubleshooting, vendor coordination.`,
      realWorld: `Example: A ticket like "Investigate intermittent network latency affecting multiple sites" — the model correctly recognizes this needs a human engineer, not a script.`,
      icon: '',
    },
    'False Positive': {
      meaning: `${count.toLocaleString()} tickets are actually MANUAL but the model wrongly said "automatable." These would fail if you tried to automate them. That's only ${(count / total * 100).toFixed(2)}% of all tickets.`,
      realWorld: `Example: A ticket might look like a standard password reset, but it involves a legacy system with special security requirements. The model saw "password reset" keywords and over-predicted automation.`,
      icon: '',
    },
    'False Negative': {
      meaning: `${count.toLocaleString()} tickets CAN be automated but the model missed them. These are hidden opportunities. The model was too conservative — perhaps because these tickets had unusual descriptions or longer-than-average resolution times.`,
      realWorld: `Example: A monitoring alert ticket that takes 2 hours because it was queued overnight, not because it's complex. The high MTTR made the model think "manual," but it's actually a simple auto-remediation candidate.`,
      icon: '',
    },
    'True Positive': {
      meaning: `${count.toLocaleString()} tickets CAN be automated, and the model correctly identified them. This is your automation goldmine — ${(count / total * 100).toFixed(1)}% of all tickets, ready for implementation.`,
      realWorld: `Example: "Disk space alert on server XYZ exceeded 90% threshold" — short MTTR, zero reassignments, event-driven, part of a large cluster of identical alerts. The model is highly confident this can be scripted.`,
      icon: '',
    },
  };
  return explainers[cell] || { meaning: '', realWorld: '', icon: '' };
}

// ============================================================
// TAB: OVERVIEW (with click-to-explain)
// ============================================================
function OverviewTab({ results, uploadId }: { results: XRayResults; uploadId: number }) {
  const m = results.metrics;
  const t = results.training;
  const cm = m.confusion_matrix;
  const [explainer, setExplainer] = useState<{ type: 'metric' | 'cm'; key: string } | null>(null);

  const metrics = [
    { label: 'Accuracy', value: m.accuracy, color: '#3b82f6' },
    { label: 'Precision', value: m.precision, color: '#10b981' },
    { label: 'Recall', value: m.recall, color: '#8b5cf6' },
    { label: 'F1 Score', value: m.f1_score, color: '#6366f1' },
  ];

  const cmCells = cm && cm.length === 2 ? [
    { label: 'True Negative', value: cm[0][0], color: 'green', bg: 'bg-green-500/20', border: 'border-green-500/30', text: 'text-green-400' },
    { label: 'False Positive', value: cm[0][1], color: 'red', bg: 'bg-red-500/20', border: 'border-red-500/30', text: 'text-red-400' },
    { label: 'False Negative', value: cm[1][0], color: 'orange', bg: 'bg-violet-500/20', border: 'border-violet-500/30', text: 'text-violet-400' },
    { label: 'True Positive', value: cm[1][1], color: 'blue', bg: 'bg-blue-500/20', border: 'border-blue-500/30', text: 'text-blue-400' },
  ] : [];

  // Get current explainer content
  const currentMetricExp = explainer?.type === 'metric' ? getMetricExplainer(explainer.key, metrics.find(mm => mm.label === explainer.key)?.value || 0, cm) : null;
  const currentCMExp = explainer?.type === 'cm' ? getCMExplainer(explainer.key, cmCells.find(c => c.label === explainer.key)?.value || 0, cm) : null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Metrics Grid */}
      <Card title="Model Performance (5-Fold CV)">
        <p className="text-xs text-slate-500 mb-4">Click any metric to see what it means, how it's calculated, and real examples</p>
        <div className="grid grid-cols-2 gap-4 mb-6">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              onClick={() => setExplainer({ type: 'metric', key: metric.label })}
              className="bg-slate-800/50 rounded-xl p-4 text-center cursor-pointer hover:ring-2 hover:ring-indigo-500/40 transition-all group relative"
            >
              <div className="absolute top-2 right-2 text-slate-600 group-hover:text-indigo-400 text-xs transition-colors">ⓘ</div>
              <div className="text-3xl font-bold" style={{ color: metric.color }}>
                {(metric.value * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-slate-400 mt-1">{metric.label}</div>
              <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${metric.value * 100}%`, background: metric.color }} />
              </div>
            </div>
          ))}
        </div>
        <div
          onClick={() => setExplainer({ type: 'metric', key: 'ROC AUC' })}
          className="bg-slate-800/50 rounded-xl p-4 cursor-pointer hover:ring-2 hover:ring-indigo-500/40 transition-all group relative"
        >
          <div className="absolute top-3 right-3 text-slate-600 group-hover:text-indigo-400 text-xs transition-colors">ⓘ Click to learn more</div>
          <div className="text-sm text-slate-400 mb-1">ROC AUC Score</div>
          <div className="text-4xl font-bold text-indigo-400">{(m.roc_auc * 100).toFixed(1)}%</div>
          <div className="text-xs text-slate-500 mt-1">Area under ROC curve — {m.roc_auc > 0.85 ? 'Excellent' : m.roc_auc > 0.75 ? 'Good' : 'Fair'} discriminative power</div>
        </div>
      </Card>

      {/* Confusion Matrix */}
      <Card title="Confusion Matrix">
        <p className="text-xs text-slate-500 mb-4">Click any cell to understand what these tickets look like</p>
        {cm && cm.length === 2 ? (
          <div className="flex flex-col items-center">
            <div className="grid grid-cols-2 gap-2 w-80">
              {cmCells.map((cell) => (
                <div
                  key={cell.label}
                  onClick={() => setExplainer({ type: 'cm', key: cell.label })}
                  className={`${cell.bg} border ${cell.border} rounded-xl p-4 text-center cursor-pointer hover:ring-2 hover:ring-indigo-500/40 transition-all group relative`}
                >
                  <div className="absolute top-1.5 right-2 text-slate-600 group-hover:text-indigo-400 text-[10px] transition-colors">ⓘ</div>
                  <div className={`text-2xl font-bold ${cell.text}`}>{cell.value.toLocaleString()}</div>
                  <div className="text-xs text-slate-400 mt-1">{cell.label}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-8 mt-4 text-xs text-slate-500">
              <span>← Predicted →</span>
            </div>
          </div>
        ) : (
          <p className="text-slate-500">No confusion matrix data</p>
        )}
      </Card>

      {/* Training Config */}
      <Card title="Training Configuration">
        <p className="text-xs text-slate-500 mb-3">XGBoost hyperparameters used for model training</p>
        <div className="space-y-3">
          {Object.entries(t.params).map(([key, val]) => (
            <div
              key={key}
              onClick={() => setExplainer({ type: 'metric', key: `param_${key}` })}
              className="flex justify-between items-center border-b border-slate-800 pb-2 cursor-pointer hover:bg-slate-800/30 rounded px-2 -mx-2 transition-colors group"
            >
              <span className="text-sm text-slate-400 font-mono group-hover:text-slate-200">{key}</span>
              <span className="text-sm text-white font-mono">{String(val)}</span>
            </div>
          ))}
          <div className="flex justify-between items-center border-b border-slate-800 pb-2">
            <span className="text-sm text-slate-400 font-mono">cross_validation</span>
            <span className="text-sm text-white font-mono">Stratified {t.cv_folds}-Fold</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-slate-400 font-mono">class_balance</span>
            <span className="text-sm text-white font-mono">{t.class_ratio}</span>
          </div>
        </div>
      </Card>

      
      {/* Dataset Summary */}
      <Card title="Dataset Summary">
        {/* Stage 1: Signal-Based Classification */}
        <div className="text-[10px] uppercase tracking-wider text-indigo-400 font-semibold mb-2">Stage 1 — Signal-Based Classification</div>
        <div className="grid grid-cols-4 gap-3 text-center mb-4">
          <div className="bg-slate-800/50 rounded-xl p-3">
            <div className="text-xl font-bold text-white">{t.total_samples.toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Total Tickets</div>
          </div>
          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3">
            <div className="text-xl font-bold text-green-400">{(results.classification?.already_automated || 0).toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Already Automated</div>
          </div>
          <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3">
            <div className="text-xl font-bold text-indigo-400">{(results.classification?.can_be_automated || 0).toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Can Be Automated</div>
          </div>
          <div className="bg-slate-500/10 border border-slate-500/20 rounded-xl p-3">
            <div className="text-xl font-bold text-slate-300">{(results.classification?.manual || 0).toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Manual</div>
          </div>
        </div>

        {/* Stage 2: XGBoost Validation */}
        <div className="text-[10px] uppercase tracking-wider text-blue-400 font-semibold mb-2">Stage 2 — XGBoost Validation</div>
        <div className="grid grid-cols-3 gap-3 text-center mb-4">
          <div className="bg-slate-800/50 rounded-xl p-3">
            <div className="text-xl font-bold text-green-400">{t.positive_samples.toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Training: Automatable</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3">
            <div className="text-xl font-bold text-slate-300">{t.negative_samples.toLocaleString()}</div>
            <div className="text-[10px] text-slate-400">Training: Manual</div>
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3">
            <div className="text-xl font-bold text-blue-400">{(m.accuracy * 100).toFixed(1)}%</div>
            <div className="text-[10px] text-slate-400">Model Accuracy</div>
          </div>
        </div>

        {/* Progress bar using classification data */}
        <div className="flex h-3 rounded-full overflow-hidden">
          <div className="bg-green-500 transition-all" style={{ width: `${((results.classification?.already_automated || 0) / t.total_samples) * 100}%` }} />
          <div className="bg-indigo-500 transition-all" style={{ width: `${((results.classification?.can_be_automated || 0) / t.total_samples) * 100}%` }} />
          <div className="bg-slate-600 flex-1" />
        </div>
        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
          <span className="text-green-400">Already Automated: {((results.classification?.already_automated || 0) / t.total_samples * 100).toFixed(1)}%</span>
          <span className="text-indigo-400">Can Automate: {((results.classification?.can_be_automated || 0) / t.total_samples * 100).toFixed(1)}%</span>
          <span>Manual: {((results.classification?.manual || 0) / t.total_samples * 100).toFixed(1)}%</span>
        </div>
      </Card>

      {/* ---- METRIC EXPLAINER MODAL ---- */}
      <ExplainerModal
        isOpen={explainer?.type === 'metric' && !!currentMetricExp?.meaning}
        onClose={() => setExplainer(null)}
        title={`${explainer?.key || ''}`}
      >
        {currentMetricExp && (
          <div className="space-y-5">
            <div>
              <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">What it means</div>
              <p className="text-sm text-slate-300 leading-relaxed">{currentMetricExp.meaning}</p>
            </div>
            <div className="bg-slate-800/60 rounded-lg p-3">
              <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-1">Formula (from your data)</div>
              <p className="text-sm text-slate-300 font-mono leading-relaxed">{currentMetricExp.formula}</p>
            </div>
            <div>
              <div className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-1">Real-world example</div>
              <p className="text-sm text-slate-300 leading-relaxed">{currentMetricExp.example}</p>
            </div>
            <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-3">
              <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">Business impact</div>
              <p className="text-sm text-slate-300 leading-relaxed">{currentMetricExp.business}</p>
            </div>
          </div>
        )}
      </ExplainerModal>

      {/* ---- ROC AUC EXPLAINER MODAL ---- */}
      <ExplainerModal
        isOpen={explainer?.key === 'ROC AUC'}
        onClose={() => setExplainer(null)}
        title="ROC AUC Score"
      >
        <div className="space-y-5">
          <div>
            <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">What it means</div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Pick one random automatable ticket and one random manual ticket. ROC AUC of {(m.roc_auc * 100).toFixed(1)}% means there's a {(m.roc_auc * 100).toFixed(1)}% chance the model gives the automatable ticket a higher score.
            </p>
          </div>
          <div className="bg-slate-800/60 rounded-lg p-3">
            <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-1">Why it matters more than accuracy</div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Your data is {((t.positive_samples / t.total_samples) * 100).toFixed(0)}% automatable. A dumb model that always says "automatable" gets {((t.positive_samples / t.total_samples) * 100).toFixed(0)}% accuracy but ROC AUC of 50% (coin flip). Your model achieves {(m.roc_auc * 100).toFixed(1)}% — it genuinely understands the difference between the two classes.
            </p>
          </div>
          <div>
            <div className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-1">Industry benchmarks</div>
            <p className="text-sm text-slate-300 leading-relaxed">
              50% = random guessing • 70-80% = fair • 80-90% = good • 90-95% = very good • 95%+ = excellent. Your model at {(m.roc_auc * 100).toFixed(1)}% is in the excellent range.
            </p>
          </div>
        </div>
      </ExplainerModal>

      {/* ---- CONFUSION MATRIX EXPLAINER MODAL ---- */}
      <WideModal
        isOpen={explainer?.type === 'cm' && !!currentCMExp?.meaning}
        onClose={() => setExplainer(null)}
        title={`${currentCMExp?.icon || ''} ${explainer?.key || ''}`}
      >
        {currentCMExp && (
          <div className="space-y-5">
            <div>
              <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">What these tickets are</div>
              <p className="text-sm text-slate-300 leading-relaxed">{currentCMExp.meaning}</p>
            </div>
            <div className="bg-slate-800/60 rounded-lg p-3">
              <div className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-1">Real ticket example</div>
              <p className="text-sm text-slate-300 leading-relaxed italic">{currentCMExp.realWorld}</p>
            </div>
            <SampleTicketsPanel
              uploadId={uploadId}
              category={
                explainer?.key === 'True Positive' ? 'tp' :
                explainer?.key === 'True Negative' ? 'tn' :
                explainer?.key === 'False Positive' ? 'fp' : 'fn'
              }
            />
          </div>
        )}
      </WideModal>

      {/* ---- PARAM EXPLAINER MODAL ---- */}
      <ExplainerModal
        isOpen={explainer?.key?.startsWith('param_') || false}
        onClose={() => setExplainer(null)}
        title={`${explainer?.key?.replace('param_', '') || ''}`}
      >
        {explainer?.key && (
          <div className="space-y-4">
            <p className="text-sm text-slate-300 leading-relaxed">
              {getParamExplainer(explainer.key.replace('param_', ''), t.params[explainer.key.replace('param_', '')])}
            </p>
          </div>
        )}
      </ExplainerModal>
    </div>
  );
}

function getParamExplainer(key: string, value: any): string {
  const explainers: Record<string, string> = {
    max_depth: `Each decision tree goes ${value} levels deep — like ${value} yes/no questions. "Is MTTR < 1hr? → Is reassignment 0? → Is it event channel? → ..." Deeper trees learn more complex patterns but risk overfitting. ${value} is the industry sweet spot.`,
    learning_rate: `How aggressively each new tree corrects mistakes. At ${value}, the model takes small, careful steps rather than big leaps. Lower = more stable but needs more trees. Higher = faster but might overshoot.`,
    n_estimators: `${value} decision trees built sequentially. Each tree fixes mistakes the previous ones made. Tree 1 might get 70% right, by tree ${value} we're at 93%+. This is the "boosting" in XGBoost.`,
    subsample: `Each tree only sees ${(value * 100).toFixed(0)}% of tickets (randomly sampled). This prevents overfitting — like training doctors at different hospitals so they don't memorize one hospital's patients.`,
    colsample_bytree: `Each tree only sees ${(value * 100).toFixed(0)}% of features. One tree might use MTTR + channel, another uses reassignment + cluster_size. Forces the model to learn diverse patterns.`,
    min_child_weight: `A tree branch must affect at least ${value} tickets to exist. Prevents the model from creating rules for one-off edge cases that won't generalize.`,
    scale_pos_weight: `Your data is imbalanced — many more automatable than manual tickets. This weight (${Number(value).toFixed(4)}) tells the model "a manual ticket matters ~${Math.round(1/Number(value))}× more" so it doesn't just predict everything as automatable.`,
    eval_metric: `The model optimizes for ${value} (log loss / binary cross-entropy). This heavily penalizes confident wrong predictions — being 99% sure about a wrong answer is much worse than being 51% sure.`,
    random_state: `Fixed seed (${value}) for reproducibility. Run the training again tomorrow and you get the exact same results. Standard practice for production ML.`,
  };
  return explainers[key] || `Configuration parameter: ${key} = ${value}`;
}

// ============================================================
// TAB: FEATURE IMPORTANCE
// ============================================================
function FeatureImportanceTab({ results }: { results: XRayResults }) {
  const top = results.feature_importance.top_features.slice(0, 15);
  const data = top.map(([label, value]) => ({ label, value }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card title="Feature Importance (Gain)" className="lg:col-span-2">
        <HorizontalBarChart data={data} color="#6366f1" height={24} />
      </Card>
      <Card title="Feature Insights">
        <div className="space-y-4">
          {top.slice(0, 5).map(([name, importance], i) => (
            <div key={name} className="bg-slate-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg font-bold text-indigo-400">#{i + 1}</span>
                <span className="text-sm font-medium text-white">{name}</span>
              </div>
              <p className="text-xs text-slate-400">
                {getFeatureInsight(name, importance)}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function getFeatureInsight(name: string, importance: number): string {
  const pct = (importance * 100).toFixed(0);
  const insights: Record<string, string> = {
    mttr_hours: `Resolution time accounts for ${pct}% of prediction power. Fast resolution strongly indicates automatable tickets.`,
    reassignment_count: `Routing complexity explains ${pct}% of decisions. Zero reassignments suggest clean, scriptable workflows.`,
    desc_entropy: `Text diversity contributes ${pct}%. Low entropy = templated descriptions = highly automatable patterns.`,
    desc_length: `Description length explains ${pct}%. Short, formulaic descriptions indicate standard procedures.`,
    kw_alert: `Alert keyword presence contributes ${pct}%. Monitoring alerts are prime automation candidates.`,
    cluster_size: `Cluster membership contributes ${pct}%. Large clusters = repeated patterns = high automation ROI.`,
    repeatability: `Pattern repeatability explains ${pct}%. Frequently occurring ticket types justify automation investment.`,
    is_event: `Event channel indicator contributes ${pct}%. Event-driven tickets are inherently automatable.`,
    mttr_log: `Log-transformed MTTR adds ${pct}% signal. Captures resolution time patterns across orders of magnitude.`,
  };
  return insights[name] || `This feature contributes ${pct}% to the model's prediction power.`;
}

// ============================================================
// TAB: SHAP EXPLAINABILITY
// ============================================================
function ShapTab({ results }: { results: XRayResults }) {
  if (!results.shap) {
    return (
      <Card title="SHAP Not Available">
        <p className="text-slate-400">SHAP values require the shap library. Install with: pip install shap</p>
      </Card>
    );
  }

  const shapData = results.shap.top_shap.slice(0, 15).map((s) => ({
    label: s.feature,
    value: s.importance,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card title="SHAP Feature Importance (Mean |SHAP|)" className="lg:col-span-2">
        <p className="text-sm text-slate-400 mb-4">
          SHAP values show each feature's contribution to individual predictions. 
          Unlike gain-based importance, SHAP accounts for feature interactions.
        </p>
        <HorizontalBarChart data={shapData} color="#8b5cf6" height={24} />
      </Card>
      <Card title="SHAP vs Gain Comparison">
        <p className="text-xs text-slate-500 mb-4">
          Comparing SHAP importance with XGBoost gain importance. 
          Large differences reveal features with interaction effects.
        </p>
        <div className="space-y-3">
          {results.shap.top_shap.slice(0, 8).map((s) => {
            const gainFeatures = results.feature_importance.all_features;
            const gainIdx = gainFeatures.features.indexOf(s.feature);
            const gainVal = gainIdx >= 0 ? gainFeatures.gain[gainIdx] : 0;
            const diff = Math.abs(s.importance - gainVal);
            return (
              <div key={s.feature} className="bg-slate-800/50 rounded-lg p-2">
                <div className="text-xs text-white font-medium truncate">{s.feature}</div>
                <div className="flex gap-2 mt-1">
                  <span className="text-xs text-purple-400">SHAP: {s.importance.toFixed(4)}</span>
                  <span className="text-xs text-indigo-400">Gain: {gainVal.toFixed(4)}</span>
                  {diff > 0.02 && <span className="text-xs text-red-400"></span>}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
      <Card title="Model Base Value" className="lg:col-span-3">
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-purple-400">
              {results.shap.expected_value.toFixed(4)}
            </div>
            <div className="text-xs text-slate-400 mt-1">Expected Value (Base Rate)</div>
          </div>
          <div className="text-sm text-slate-400 flex-1">
            This is the model's average prediction before any features are considered.
            Each feature pushes the prediction higher (toward automatable) or lower (toward manual) from this base.
            Computed on a sample of {results.shap.sample_size.toLocaleString()} tickets.
          </div>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
// TAB: ROC & PR CURVES
// ============================================================
function CurvesTab({ results }: { results: XRayResults }) {
  const rocData = results.roc_curve.fpr.map((fpr, i) => ({
    x: fpr,
    y: results.roc_curve.tpr[i] || 0,
  }));

  const prData = results.pr_curve.recall.map((r, i) => ({
    x: r,
    y: results.pr_curve.precision[i] || 0,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title={`ROC Curve (AUC = ${(results.roc_curve.auc * 100).toFixed(1)}%)`}>
        <SVGLineChart data={rocData} xLabel="False Positive Rate" yLabel="True Positive Rate" color="#6366f1" diagonal width={500} height={350} />
        <p className="text-xs text-slate-500 mt-2">
          {results.roc_curve.auc > 0.9
            ? 'Excellent: The model has strong discriminative power.'
            : results.roc_curve.auc > 0.8
              ? 'Good: Reliable separation between automatable and manual tickets.'
              : 'Fair: Model shows moderate ability to distinguish classes.'}
        </p>
      </Card>
      <Card title="Precision-Recall Curve">
        <SVGLineChart data={prData} xLabel="Recall" yLabel="Precision" color="#10b981" width={500} height={350} />
        <p className="text-xs text-slate-500 mt-2">
          Shows the trade-off between finding all automatable tickets (recall) and avoiding false positives (precision).
        </p>
      </Card>
    </div>
  );
}

// ============================================================
// TAB: AUTOMATION FRONTIER
// ============================================================
function FrontierTab({ results }: { results: XRayResults }) {
  const f = results.frontier;
  const autoPct = ((f.automatable.count / f.total) * 100).toFixed(1);
  const manualPct = ((f.manual.count / f.total) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Automation Frontier">
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-5 text-center">
            <div className="text-4xl font-bold text-green-400">{f.automatable.count.toLocaleString()}</div>
            <div className="text-sm text-slate-400 mt-1">Automatable ({autoPct}%)</div>
            <div className="text-xs text-green-400/60 mt-1">Avg confidence: {(f.automatable.avg_confidence * 100).toFixed(0)}%</div>
          </div>
          <div className="bg-slate-500/10 border border-slate-500/20 rounded-xl p-5 text-center">
            <div className="text-4xl font-bold text-slate-300">{f.manual.count.toLocaleString()}</div>
            <div className="text-sm text-slate-400 mt-1">Manual ({manualPct}%)</div>
            <div className="text-xs text-slate-400/60 mt-1">Avg confidence: {(f.manual.avg_confidence * 100).toFixed(0)}%</div>
          </div>
        </div>
        {/* Stacked bar */}
        <div className="h-6 rounded-full overflow-hidden flex">
          <div className="bg-green-500 transition-all" style={{ width: `${autoPct}%` }} />
          <div className="bg-slate-600 flex-1" />
        </div>
      </Card>

      <Card title="Confidence Distribution">
        {results.confidence_distribution && (
          <div className="flex items-end gap-1 h-48">
            {results.confidence_distribution.counts.map((count, i) => {
              const max = Math.max(...results.confidence_distribution.counts, 1);
              const pct = (count / max) * 100;
              const binStart = results.confidence_distribution.bin_edges[i];
              const isHighConf = binStart >= 0.7;
              return (
                <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                  <div
                    className="w-full rounded-t transition-all"
                    style={{
                      height: `${pct}%`,
                      background: isHighConf ? '#10b981' : binStart >= 0.4 ? '#6366f1' : '#64748b',
                      minHeight: count > 0 ? '2px' : '0',
                    }}
                  />
                  {i % 4 === 0 && (
                    <span className="text-[9px] text-slate-500 mt-1">{binStart.toFixed(1)}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <div className="flex justify-between text-xs text-slate-500 mt-2">
          <span>0.0 (Manual)</span>
          <span>Prediction Confidence</span>
          <span>1.0 (Auto)</span>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
// TAB: WHAT-IF SIMULATOR
// ============================================================
function WhatIfTab({ uploadId, results }: { uploadId: number; results: XRayResults }) {
  const stats = results.feature_stats || {};
  const topFeatures = results.feature_importance.top_features.slice(0, 8).map(([name]) => name);

  const [featureValues, setFeatureValues] = useState<Record<string, number>>(() => {
    const defaults: Record<string, number> = {};
    topFeatures.forEach((name) => {
      defaults[name] = stats[name]?.median || stats[name]?.mean || 0;
    });
    return defaults;
  });

  const [modifications, setModifications] = useState<Record<string, number>>({});
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [simulating, setSimulating] = useState(false);

  const runSimulation = async () => {
    setSimulating(true);
    try {
      // Build full base features (use median for non-displayed features)
      const allFeatures: Record<string, number> = {};
      Object.keys(stats).forEach((name) => {
        allFeatures[name] = featureValues[name] ?? stats[name]?.median ?? 0;
      });

      const data = await apiFetch('/api/xgboost-xray/what-if', {
        method: 'POST',
        body: JSON.stringify({
          upload_id: uploadId,
          base_features: allFeatures,
          modifications,
        }),
      });
      setResult(data);
    } catch (e: any) {
      console.error('What-If error:', e);
    } finally {
      setSimulating(false);
    }
  };

  const updateFeature = (name: string, value: number) => {
    setFeatureValues((prev) => ({ ...prev, [name]: value }));
    setModifications((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card title="Adjust Features" className="lg:col-span-2">
        <p className="text-sm text-slate-400 mb-6">
          Modify feature values to see how the automation prediction changes. 
          Start from median values and experiment.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {topFeatures.map((name) => {
            const s = stats[name];
            if (!s) return null;
            const current = featureValues[name] ?? s.median;
            const isModified = modifications[name] !== undefined;
            return (
              <div key={name} className={`rounded-lg p-3 ${isModified ? 'bg-indigo-500/10 border border-indigo-500/20' : 'bg-slate-800/50'}`}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-medium text-white">{name}</span>
                  <span className="text-xs font-mono text-indigo-400">{current.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={s.min}
                  max={Math.max(s.max, s.min + 0.01)}
                  step={(s.max - s.min) / 100 || 0.01}
                  value={current}
                  onChange={(e) => updateFeature(name, parseFloat(e.target.value))}
                  className="w-full accent-indigo-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>{s.min.toFixed(1)}</span>
                  <span>med: {s.median.toFixed(1)}</span>
                  <span>{s.max.toFixed(1)}</span>
                </div>
              </div>
            );
          })}
        </div>
        <button
          onClick={runSimulation}
          disabled={simulating || Object.keys(modifications).length === 0}
          className="mt-6 px-6 py-3 bg-indigo-500 hover:bg-indigo-400 text-black font-semibold rounded-lg
                     transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {simulating ? 'Simulating...' : 'Run What-If Simulation'}
        </button>
      </Card>

      <Card title="Prediction Result">
        {result ? (
          <div className="space-y-6">
            <div className="bg-slate-800/50 rounded-xl p-4 text-center">
              <div className="text-xs text-slate-400 mb-1">Base Prediction</div>
              <div className={`text-3xl font-bold ${result.base_prediction.label === 'Automatable' ? 'text-green-400' : 'text-slate-400'}`}>
                {(result.base_prediction.probability * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-slate-400">{result.base_prediction.label}</div>
            </div>
            <div className="text-center text-2xl">
              {result.delta > 0 ? '' : result.delta < 0 ? '' : ''}
            </div>
            <div className={`rounded-xl p-4 text-center border ${
              result.modified_prediction.label === 'Automatable'
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-slate-800/50 border-slate-700'
            }`}>
              <div className="text-xs text-slate-400 mb-1">Modified Prediction</div>
              <div className={`text-3xl font-bold ${result.modified_prediction.label === 'Automatable' ? 'text-green-400' : 'text-slate-400'}`}>
                {(result.modified_prediction.probability * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-slate-400">{result.modified_prediction.label}</div>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <span className={`text-lg font-bold ${result.delta > 0 ? 'text-green-400' : result.delta < 0 ? 'text-red-400' : 'text-slate-400'}`}>
                {result.delta > 0 ? '+' : ''}{(result.delta * 100).toFixed(1)}%
              </span>
              <div className="text-xs text-slate-500">Change in automation probability</div>
            </div>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500">
            <div className="text-4xl mb-3"></div>
            <p>Adjust features on the left and run a simulation to see how predictions change.</p>
          </div>
        )}
      </Card>
    </div>
  );
}

// ============================================================
// TAB: CALIBRATION
// ============================================================
function CalibrationTab({ results }: { results: XRayResults }) {
  const cal = results.calibration;

  const calData = cal
    ? cal.mean_predicted_value.map((x, i) => ({
        x,
        y: cal.fraction_of_positives[i],
      }))
    : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Calibration Curve">
        {cal ? (
          <>
            <SVGLineChart
              data={calData}
              xLabel="Mean Predicted Probability"
              yLabel="Fraction of Positives"
              color="#8b5cf6"
              diagonal
              width={500}
              height={350}
            />
            <p className="text-xs text-slate-500 mt-2">
              A well-calibrated model follows the diagonal. Points above the diagonal mean the model is under-confident; 
              below means over-confident.
            </p>
          </>
        ) : (
          <p className="text-slate-500">Calibration data not available.</p>
        )}
      </Card>

      <Card title="Prediction Confidence Histogram">
        {results.confidence_distribution && (
          <>
            <div className="flex items-end gap-1 h-52">
              {results.confidence_distribution.counts.map((count, i) => {
                const max = Math.max(...results.confidence_distribution.counts, 1);
                const pct = (count / max) * 100;
                const binStart = results.confidence_distribution.bin_edges[i];
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                    <div className="absolute -top-6 bg-slate-700 text-xs px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                      {count.toLocaleString()}
                    </div>
                    <div
                      className="w-full rounded-t transition-all group-hover:opacity-80"
                      style={{
                        height: `${pct}%`,
                        background: `hsl(${binStart * 120}, 70%, 50%)`,
                        minHeight: count > 0 ? '2px' : '0',
                      }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-slate-500 mt-2">
              <span>0% (Confident Manual)</span>
              <span>50% (Uncertain)</span>
              <span>100% (Confident Auto)</span>
            </div>
            <p className="text-xs text-slate-500 mt-4">
              Bimodal distribution (peaks near 0 and 1) indicates the model makes confident predictions.
              Peaks around 0.5 suggest uncertainty.
            </p>
          </>
        )}
      </Card>
    </div>
  );
}