"use client";
/** Right-hand slide-over used for model drill-downs. `dark` suits content that is styled for a dark ground. */
import { useEffect, useState, type ReactNode } from "react";
import { ExternalLink, X, type LucideIcon } from "lucide-react";

export default function Drawer({ isOpen, onClose, title, subtitle, icon: Icon, dark = false, onPopOut, children }: {
  isOpen: boolean; onClose: () => void; title: string; subtitle?: string; icon: LucideIcon;
  dark?: boolean; onPopOut?: () => void; children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setMounted(true);
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
      const timer = setTimeout(() => setMounted(false), 300);
      return () => clearTimeout(timer);
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!mounted) return null;

  const surface = dark ? "bg-zinc-950 text-white border-white/10" : "bg-zinc-50 text-zinc-900 border-zinc-200";
  const bar = dark ? "bg-zinc-950/90 border-white/10" : "bg-white/90 border-zinc-200";
  const ghost = dark
    ? "border-white/10 bg-white/5 text-zinc-300 hover:bg-white/10 hover:text-white"
    : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900";

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-zinc-900/40 backdrop-blur-sm transition-opacity duration-300 ${isOpen ? "opacity-100" : "opacity-0"}`}
      />
      <aside
        role="dialog"
        aria-label={title}
        className={`fixed right-0 top-0 z-50 flex h-screen w-[88vw] max-w-[1400px] flex-col overflow-hidden border-l shadow-2xl shadow-zinc-900/30 transition-transform duration-300 ${surface} ${isOpen ? "translate-x-0" : "translate-x-full"}`}
      >
        <header className={`flex shrink-0 items-center justify-between gap-4 border-b px-6 py-4 backdrop-blur ${bar}`}>
          <div className="flex min-w-0 items-center gap-3.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm shadow-indigo-500/30">
              <Icon className="h-5 w-5" strokeWidth={1.75} />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold tracking-tight">{title}</h2>
              {subtitle && <p className={`truncate text-xs ${dark ? "text-zinc-400" : "text-zinc-500"}`}>{subtitle}</p>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {onPopOut && (
              <button onClick={onPopOut} className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-[13px] font-medium transition ${ghost}`}>
                <ExternalLink className="h-3.5 w-3.5" /> Open in tab
              </button>
            )}
            <button onClick={onClose} aria-label="Close" className={`flex h-9 w-9 items-center justify-center rounded-lg border transition ${ghost}`}>
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </aside>
    </>
  );
}
