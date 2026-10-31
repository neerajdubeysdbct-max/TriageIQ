"use client";

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  change?: string;
  changeType?: "positive" | "negative" | "neutral";
  icon?: string;
}

export default function StatCard({
  label,
  value,
  subValue,
  change,
  changeType = "neutral",
  icon,
}: StatCardProps) {
  const changeColors = {
    positive: "text-green-600 bg-green-50",
    negative: "text-red-600 bg-red-50",
    neutral: "text-gray-600 bg-gray-50",
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm shadow-zinc-900/[0.03] p-4">
      <div className="flex items-start justify-between mb-2">
        <span className="text-sm text-gray-500">{label}</span>
        {icon && <span className="text-xl">{icon}</span>}
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {subValue && (
        <div className="text-xs text-gray-500 mt-1">{subValue}</div>
      )}
      {change && (
        <div className={`inline-flex items-center px-2 py-0.5 rounded text-xs mt-2 ${changeColors[changeType]}`}>
          {changeType === "positive" && "↑"}
          {changeType === "negative" && "↓"}
          {change}
        </div>
      )}
    </div>
  );
}
