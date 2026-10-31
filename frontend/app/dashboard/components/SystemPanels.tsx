"use client";
/** Activity log and settings: both read live from /api/system. */
import { useEffect, useState } from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function useSystem<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const token = localStorage.getItem("token");
    fetch(`${API}/api/system/${path}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => (r.ok ? setData(await r.json()) : setError(`${r.status} ${r.statusText}`)))
      .catch((e) => setError(String(e)));
  }, [path]);
  return { data, error };
}

const EVENT_ICON = {
  success: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
  error: <XCircle className="w-4 h-4 text-red-600" />,
  info: <Info className="w-4 h-4 text-blue-600" />,
};

export function ActivityLog() {
  const { data, error } = useSystem<{ events: any[] }>("activity");
  return (
    <div className="max-w-3xl">
      {error && <p className="text-sm text-red-600">Could not load activity: {error}</p>}
      {data?.events.length === 0 && <p className="text-sm text-gray-500">No activity yet.</p>}
      <ol className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
        {data?.events.map((e, i) => (
          <li key={i} className="flex gap-3 px-4 py-3">
            <div className="mt-0.5">{EVENT_ICON[e.type as keyof typeof EVENT_ICON] ?? EVENT_ICON.info}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900">{e.title}</div>
              <div className="text-xs text-gray-500 mt-0.5">{e.desc}</div>
            </div>
            <time className="text-xs text-gray-400 whitespace-nowrap">
              {e.time ? new Date(e.time).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : ""}
            </time>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function SettingsPanel() {
  const { data, error } = useSystem<{ settings: { label: string; value: string; desc: string }[] }>("config");
  return (
    <div className="max-w-3xl">
      <p className="text-sm text-gray-500 mb-4">Pipeline configuration as the backend is running it.</p>
      {error && <p className="text-sm text-red-600">Could not load configuration: {error}</p>}
      <dl className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
        {data?.settings.map((s) => (
          <div key={s.label} className="grid grid-cols-3 gap-4 px-4 py-3">
            <dt className="text-sm font-medium text-gray-900">{s.label}</dt>
            <dd className="col-span-2">
              <div className="text-sm text-gray-800 font-mono">{s.value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{s.desc}</div>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
