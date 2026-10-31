'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import XGBoostXRay from '../components/XGBoostXRay';

function XGBoostXRayContent() {
  const searchParams = useSearchParams();
  const uploadId = parseInt(searchParams.get('upload_id') || '0');
  const searchQuery = searchParams.get('search') || '';

  if (!uploadId) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-2">Missing upload_id</h1>
          <p className="text-slate-400">Add ?upload_id=X to the URL</p>
        </div>
      </div>
    );
  }

  return <XGBoostXRay uploadId={uploadId} />;
}

export default function XGBoostXRayPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="animate-spin text-3xl"></div>
      </div>
    }>
      <XGBoostXRayContent />
    </Suspense>
  );
}