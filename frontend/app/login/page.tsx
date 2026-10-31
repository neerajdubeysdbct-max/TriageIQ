"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import Logo from "@/components/Logo";

const POINTS = [
  { icon: Workflow, text: "Find which tickets are already automated, and which could be" },
  { icon: Sparkles, text: "Recurring themes and a copilot that answers with cited evidence" },
  { icon: ShieldCheck, text: "Team-scoped data: every query is filtered to your team" },
];

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/login`, {
        method: "POST",
        body: formData,
      });
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("token", data.access_token);
        router.push("/dashboard");
      } else {
        const errorData = await response.json();
        setError(errorData.detail || "Invalid credentials");
      }
    } catch {
      setError("Connection error. Ensure backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const input =
    "w-full h-11 rounded-lg border border-zinc-200 bg-white px-3.5 text-sm text-zinc-900 placeholder:text-zinc-400 " +
    "outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10";

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr] bg-white">
      {/* Brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-zinc-950 p-12 text-white">
        <div className="pointer-events-none absolute -top-40 -left-32 h-[28rem] w-[28rem] rounded-full bg-indigo-600/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-48 -right-24 h-[30rem] w-[30rem] rounded-full bg-violet-600/20 blur-3xl" />
        <div className="relative"><Logo light /></div>

        <div className="relative max-w-md">
          <h2 className="text-4xl font-semibold leading-[1.15] tracking-tight">
            Know which tickets <span className="text-indigo-400">to automate</span> before you triage another one.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-zinc-400">
            Upload a service desk export and get automation opportunities, themes, SLA risk and answers you can trace back to tickets.
          </p>
          <ul className="mt-10 space-y-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm text-zinc-300">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/5 ring-1 ring-white/10">
                  <Icon className="h-3.5 w-3.5 text-indigo-300" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative text-xs text-zinc-500">© 2026 TriageIQ</div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-10"><Logo /></div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Welcome back</h1>
          <p className="mt-1.5 text-sm text-zinc-500">Sign in to your analytics workspace.</p>

          <form onSubmit={handleLogin} className="mt-8 space-y-5">
            <div>
              <label htmlFor="username" className="mb-1.5 block text-[13px] font-medium text-zinc-700">Username</label>
              <input id="username" type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username" autoComplete="username" required className={input} />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-[13px] font-medium text-zinc-700">Password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password" autoComplete="current-password" required className={input} />
            </div>

            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13px] text-red-700">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 text-sm font-medium text-white shadow-sm transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60">
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Signing in</> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
