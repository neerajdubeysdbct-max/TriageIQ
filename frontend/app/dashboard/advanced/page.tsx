"use client";
// The former separate "Advanced" app now lives in the main dashboard navigation.
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdvancedRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard?view=evaluation");
  }, [router]);
  return null;
}
