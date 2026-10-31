"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CheckCircle2, FileSpreadsheet, Loader2, UploadCloud, XCircle } from "lucide-react";
import Logo from "@/components/Logo";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) router.push("/login");
  }, [router]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus("");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && ['.csv','.xlsx','.xls'].some(ext => dropped.name.endsWith(ext))) {
      setFile(dropped);
      setStatus("");
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus("Uploading file...");

    const formData = new FormData();
    formData.append("file", file);
    const token = localStorage.getItem("token");

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();

        if (data.status === "existing") {
          setStatus(`✓ File already analyzed — loading existing results...`);
        } else {
          setStatus(`✓ Saved ${data.total_tickets.toLocaleString()} tickets — opening dashboard...`);
        }

        // Instant redirect — no waiting
        setTimeout(() => {
          router.push(`/dashboard?upload_id=${data.upload_id}`);
        }, 1500);

      } else {
        const err = await response.json();
        setStatus(`✗ ${err.detail || "Upload failed"}`);
        setUploading(false);
      }
    } catch {
      setStatus("✗ Connection error. Is the backend running?");
      setUploading(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  const ok = status.includes("✓");

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50">
      <header className="flex h-16 items-center justify-between border-b border-zinc-200 bg-white/80 px-6 backdrop-blur">
        <Logo />
        <button
          onClick={() => router.push("/dashboard")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-[13px] font-medium text-zinc-700 transition hover:bg-zinc-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
        </button>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-xl">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">Upload your tickets</h1>
            <p className="mt-2 text-sm text-zinc-500">
              Add an incident, request, change or problem export to analyse.
            </p>
          </div>

          <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
                dragOver ? "border-indigo-500 bg-indigo-50"
                : file ? "border-emerald-300 bg-emerald-50/50"
                : "border-zinc-200 bg-zinc-50/60 hover:border-zinc-300 hover:bg-zinc-50"
              }`}
            >
              <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleFileChange} className="hidden" />
              <div className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl ${
                file ? "bg-emerald-100 text-emerald-600" : "bg-white text-indigo-500 ring-1 ring-zinc-200"
              }`}>
                {file ? <FileSpreadsheet className="h-6 w-6" /> : <UploadCloud className="h-6 w-6" />}
              </div>
              {file ? (
                <>
                  <p className="text-sm font-medium text-zinc-900">{file.name}</p>
                  <p className="mt-0.5 text-[13px] text-zinc-500">{formatSize(file.size)}</p>
                  <p className="mt-2 text-xs text-emerald-600">Click to choose a different file</p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-zinc-800">Drop your file here, or click to browse</p>
                  <p className="mt-1 text-[13px] text-zinc-400">CSV or Excel (.csv, .xlsx, .xls), up to 200 MB</p>
                </>
              )}
            </div>

            <p className="mt-4 text-[13px] leading-relaxed text-zinc-500">
              The dashboard opens as soon as the tickets are saved. Clustering and classification keep running in the
              background and the page updates when they finish.
            </p>

            {status && (
              <div className={`mt-4 flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-[13px] ${
                ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : uploading ? "border-zinc-200 bg-zinc-50 text-zinc-600"
                : "border-red-200 bg-red-50 text-red-700"
              }`}>
                {ok ? <CheckCircle2 className="mt-px h-4 w-4 shrink-0" />
                  : uploading ? <Loader2 className="mt-px h-4 w-4 shrink-0 animate-spin" />
                  : <XCircle className="mt-px h-4 w-4 shrink-0" />}
                <span>{status.replace(/^[✓✗]\s*/, "")}</span>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="mt-5 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 text-sm font-medium text-white shadow-sm transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {uploading ? <><Loader2 className="h-4 w-4 animate-spin" /> Uploading</> : <>Upload and analyse <ArrowRight className="h-4 w-4" /></>}
            </button>
          </div>

          <p className="mt-4 text-center text-xs text-zinc-400">
            Works with ServiceNow-style exports. Other ticketing tools may need their columns mapped.
          </p>
        </div>
      </main>
    </div>
  );
}
