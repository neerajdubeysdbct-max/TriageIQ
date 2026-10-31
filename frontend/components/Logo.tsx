import { Sparkles } from "lucide-react";

/** TriageIQ mark: indigo gradient tile with a spark, plus the wordmark. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-[10px] bg-gradient-to-br from-indigo-500 to-violet-600 shadow-sm shadow-indigo-500/30"
      style={{ width: size, height: size }}
    >
      <Sparkles className="text-white" style={{ width: size * 0.5, height: size * 0.5 }} strokeWidth={2.25} />
    </div>
  );
}

export default function Logo({ tagline, light = false }: { tagline?: string; light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <div className="leading-tight">
        <div className={`text-[15px] font-semibold tracking-tight ${light ? "text-white" : "text-zinc-900"}`}>
          Triage<span className="text-indigo-500">IQ</span>
        </div>
        {tagline && <div className={`text-[11px] ${light ? "text-zinc-400" : "text-zinc-500"}`}>{tagline}</div>}
      </div>
    </div>
  );
}
