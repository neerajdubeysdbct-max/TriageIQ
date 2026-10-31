"use client";

import { ScanSearch } from "lucide-react";
import Drawer from "../components/Drawer";
import XGBoostXRay from "../components/XGBoostXRay";

interface XGBoostDrillDownProps {
  uploadId: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function XGBoostDrillDown({ uploadId, isOpen, onClose }: XGBoostDrillDownProps) {
  return (
    <Drawer
      dark
      isOpen={isOpen}
      onClose={onClose}
      icon={ScanSearch}
      title="Automation classifier X-Ray"
      subtitle="Model explainability · SHAP · What-if simulator"
      onPopOut={() => window.open(`/dashboard/xgboost-xray?upload_id=${uploadId}`, "_blank")}
    >
      <XGBoostXRay uploadId={uploadId} />
    </Drawer>
  );
}
