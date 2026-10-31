"""
XGBoost X-Ray Router
API endpoints for the XGBoost X-Ray dashboard panels.
"""

from config import LLM_MODEL, OLLAMA_URL
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Optional, List
import json
import os

from dependencies import get_current_user, require_upload_access

router = APIRouter(prefix="/api/xgboost-xray", tags=["XGBoost X-Ray"])

# Track training status per upload
_training_status = {}  # upload_id -> {"status": "training|completed|failed", "progress": 0-100}


class WhatIfRequest(BaseModel):
    upload_id: int
    base_features: Dict[str, float]
    modifications: Dict[str, float]


# ============================================================
# TRAINING ENDPOINT
# ============================================================

@router.post("/train/{upload_id}")
def trigger_xgboost_training(
    upload_id: int,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_upload_access)
):
    """Trigger XGBoost X-Ray training (runs in background)"""
    
    # Check if already training
    if upload_id in _training_status and _training_status[upload_id]['status'] == 'training':
        return {"message": "Training already in progress", "status": "training"}
    
    _training_status[upload_id] = {"status": "training", "progress": 10}
    
    background_tasks.add_task(_run_training_background, upload_id)
    
    return {
        "message": "XGBoost X-Ray training started",
        "status": "training",
        "upload_id": upload_id
    }


def _run_training_background(upload_id: int):
    """Background task for training"""
    try:
        _training_status[upload_id] = {"status": "training", "progress": 20}
        
        from services.xgboost_trainer import run_xgboost_xray
        results = run_xgboost_xray(upload_id)
        
        if 'error' in results:
            _training_status[upload_id] = {"status": "failed", "error": results['error']}
        else:
            _training_status[upload_id] = {"status": "completed", "progress": 100}
    except Exception as e:
        print(f"XGBoost training error: {e}")
        _training_status[upload_id] = {"status": "failed", "error": str(e)}


# ============================================================
# TRAINING STATUS
# ============================================================

@router.get("/status/{upload_id}")
def get_training_status(upload_id: int, user: dict = Depends(require_upload_access)):
    """Check training status"""
    # Check if results file exists (completed previously)
    results_path = f'models/xgboost_xray_results_{upload_id}.json'
    if os.path.exists(results_path):
        return {"status": "completed", "progress": 100}
    
    if upload_id in _training_status:
        return _training_status[upload_id]
    
    return {"status": "not_started", "progress": 0}


# ============================================================
# FULL RESULTS
# ============================================================

@router.get("/results/{upload_id}")
def get_xray_results(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get full XGBoost X-Ray results (after training)"""
    results_path = f'models/xgboost_xray_results_{upload_id}.json'
    
    if not os.path.exists(results_path):
        raise HTTPException(404, "XGBoost X-Ray not trained yet. Call POST /train first.")
    
    with open(results_path, 'r') as f:
        results = json.load(f)
    # Add dashboard-consistent counts for Dataset Summary
    from models import SessionLocal, Ticket
    db = SessionLocal()
    try:
        total = db.query(Ticket).filter(Ticket.upload_id == upload_id).count()
        already = db.query(Ticket).filter(Ticket.upload_id == upload_id, Ticket.is_already_automated == True).count()
        can_auto = db.query(Ticket).filter(Ticket.upload_id == upload_id, Ticket.can_be_automated == True, Ticket.is_already_automated == False).count()
        manual = total - already - can_auto
        results['classification'] = {
            'total': total,
            'already_automated': already,
            'can_be_automated': can_auto,
            'manual': manual,
        }
    finally:
        db.close()
    return results


# ============================================================
# INDIVIDUAL PANEL ENDPOINTS (lighter payloads)
# ============================================================

@router.get("/metrics/{upload_id}")
def get_metrics(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get training metrics only (accuracy, precision, recall, etc.)"""
    results = _load_results(upload_id)
    return {
        "metrics": results.get("metrics"),
        "training": results.get("training"),
        "trained_at": results.get("trained_at"),
    }


@router.get("/feature-importance/{upload_id}")
def get_feature_importance(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get feature importance rankings"""
    results = _load_results(upload_id)
    return results.get("feature_importance", {})


@router.get("/shap/{upload_id}")
def get_shap_values(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get SHAP explainability data"""
    results = _load_results(upload_id)
    shap_data = results.get("shap")
    if not shap_data:
        return {"error": "SHAP not available. Install shap: pip install shap"}
    return shap_data


@router.get("/roc-curve/{upload_id}")
def get_roc_curve(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get ROC curve data"""
    results = _load_results(upload_id)
    return {
        "roc_curve": results.get("roc_curve"),
        "pr_curve": results.get("pr_curve"),
    }


@router.get("/calibration/{upload_id}")
def get_calibration(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get calibration curve and confidence distribution"""
    results = _load_results(upload_id)
    return {
        "calibration": results.get("calibration"),
        "confidence_distribution": results.get("confidence_distribution"),
    }


@router.get("/frontier/{upload_id}")
def get_automation_frontier(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get automation frontier data"""
    results = _load_results(upload_id)
    return results.get("frontier", {})


@router.get("/feature-stats/{upload_id}")
def get_feature_stats(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get feature statistics for What-If simulator"""
    results = _load_results(upload_id)
    return {
        "feature_stats": results.get("feature_stats", {}),
        "feature_names": results.get("feature_importance", {}).get("all_features", {}).get("features", []),
    }


# ============================================================
# WHAT-IF SIMULATOR
# ============================================================

@router.post("/what-if")
def run_what_if(request: WhatIfRequest, user: dict = Depends(get_current_user)):
    """
    What-If simulator: modify features and see prediction change.
    """
    model_path = f'models/xgboost_xray_{request.upload_id}.pkl'
    if not os.path.exists(model_path):
        raise HTTPException(404, "Model not trained yet")
    
    results = _load_results(request.upload_id)
    feature_names = results.get("feature_importance", {}).get("all_features", {}).get("features", [])
    
    if not feature_names:
        raise HTTPException(500, "Feature names not found in results")
    
    from services.xgboost_trainer import what_if_simulate
    
    result = what_if_simulate(
        model_path=model_path,
        base_features=request.base_features,
        modifications=request.modifications,
        feature_names=feature_names,
    )
    
    return result


# ============================================================
# HELPERS
# ============================================================

def _load_results(upload_id: int) -> dict:
    results_path = f'models/xgboost_xray_results_{upload_id}.json'
    if not os.path.exists(results_path):
        raise HTTPException(404, "XGBoost X-Ray not trained. POST /api/xgboost-xray/train/{upload_id} first.")
    with open(results_path, 'r') as f:
        return json.load(f)


# ============================================================
# SAMPLE TICKETS BY CONFUSION MATRIX CATEGORY
# ============================================================

@router.get("/sample-tickets/{upload_id}")
def get_sample_tickets(
    upload_id: int,
    category: str = "tp",
    offset: int = 0,
    limit: int = 10,
    user: dict = Depends(require_upload_access)
):
    """
    Get real sample tickets from each confusion matrix quadrant.
    Uses cached predictions — first call computes, subsequent calls are instant.
    """
    import pickle
    import numpy as np
    import pandas as pd
    
    model_path = f'models/xgboost_xray_{upload_id}.pkl'
    cache_path = f'models/xgboost_predictions_{upload_id}.pkl'
    
    if not os.path.exists(model_path):
        raise HTTPException(404, "Model not trained yet")
    
    from models import SessionLocal, Ticket
    db = SessionLocal()
    
    try:
        # Check cache first
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                cache = pickle.load(f)
        else:
            # First call — compute and cache
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            model = model_data['model']
            feature_names = model_data.get('feature_names', [])
            
            tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
            if not tickets:
                return {"tickets": [], "total": 0, "category": category}
            
            from services.xgboost_trainer import engineer_features, generate_labels
            
            df = pd.DataFrame([{col.name: getattr(t, col.name, None) for col in Ticket.__table__.columns} for t in tickets])
            features_df, _ = engineer_features(df)
            for f in feature_names:
                if f not in features_df.columns:
                    features_df[f] = 0
            
            X = features_df[feature_names].values
            predictions = model.predict(X)
            probabilities = model.predict_proba(X)[:, 1]
            labels = generate_labels(df)
            
            # Build category index: {category: [(ticket_id, confidence), ...]}
            ticket_ids = [t.id for t in tickets]
            tp, tn, fp, fn = [], [], [], []
            for i in range(len(tickets)):
                entry = (ticket_ids[i], float(probabilities[i]))
                if labels[i] == 1 and predictions[i] == 1:
                    tp.append(entry)
                elif labels[i] == 0 and predictions[i] == 0:
                    tn.append(entry)
                elif labels[i] == 0 and predictions[i] == 1:
                    fp.append(entry)
                else:
                    fn.append(entry)
            
            # Sort: TP/FP by highest confidence, TN/FN by lowest
            tp.sort(key=lambda x: -x[1])
            fp.sort(key=lambda x: -x[1])
            tn.sort(key=lambda x: x[1])
            fn.sort(key=lambda x: x[1])
            
            cache = {"tp": tp, "tn": tn, "fp": fp, "fn": fn}
            with open(cache_path, 'wb') as f:
                pickle.dump(cache, f)
        
        # Serve from cache
        cat_data = cache.get(category.lower(), cache.get("tp", []))
        total = len(cat_data)
        page = cat_data[offset:offset + limit]
        
        if not page:
            return {"tickets": [], "total": total, "category": category,
                    "category_label": "", "offset": offset, "limit": limit, "has_more": False}
        
        # Fetch only the needed tickets by ID
        page_ids = [p[0] for p in page]
        page_confs = {p[0]: p[1] for p in page}
        tickets_by_id = {t.id: t for t in db.query(Ticket).filter(Ticket.id.in_(page_ids)).all()}
        
        category_labels = {
            "tp": "True Positive (Correctly Automatable)",
            "tn": "True Negative (Correctly Manual)",
            "fp": "False Positive (Wrongly Flagged Automatable)",
            "fn": "False Negative (Missed Automation Opportunity)",
        }
        
        result_tickets = []
        for tid, conf in page:
            t = tickets_by_id.get(tid)
            if not t:
                continue
            result_tickets.append({
                "ticket_number": t.ticket_number or f"T-{t.id}",
                "short_description": (t.short_description or "")[:120],
                "assignment_group": t.assignment_group or "Unknown",
                "priority": t.priority or "-",
                "channel": t.channel or t.contact_type or "Unknown",
                "mttr_hours": round(t.mttr_hours, 2) if t.mttr_hours else None,
                "reassignment_count": t.reassignment_count or 0,
                "reopen_count": t.reopen_count or 0,
                "confidence": round(conf * 100, 1),
                "predicted": "Automatable" if conf >= 0.5 else "Manual",
                "actual": "Automatable" if (category.lower() in ["tp", "fn"]) else "Manual",
                "is_already_automated": bool(t.is_already_automated) if t.is_already_automated is not None else False,
                "cluster_id": t.cluster_id,
            })
        
        return {
            "tickets": result_tickets,
            "total": total,
            "category": category,
            "category_label": category_labels.get(category.lower(), ""),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total,
        }
    finally:
        db.close()

# ============================================================
# TICKET LOOKUP WITH PER-TICKET SHAP
# ============================================================

class TicketLookupRequest(BaseModel):
    query: str  # ticket number or keyword


@router.post("/ticket-lookup/{upload_id}")
def lookup_ticket(
    upload_id: int,
    request: TicketLookupRequest,
    user: dict = Depends(require_upload_access)
):
    """
    Search for a ticket by number or keyword.
    Returns prediction, confidence, and per-ticket SHAP waterfall.
    """
    import pickle
    import numpy as np
    import pandas as pd
    
    model_path = f'models/xgboost_xray_{upload_id}.pkl'
    if not os.path.exists(model_path):
        raise HTTPException(404, "Model not trained yet")
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    model = model_data['model']
    feature_names = model_data.get('feature_names', [])
    
    from models import SessionLocal
    from models import Ticket
    from sqlalchemy import or_
    db = SessionLocal()
    
    try:
        query = request.query.strip()
        
        # Search by ticket number or short description keyword
        matching = db.query(Ticket).filter(
            Ticket.upload_id == upload_id
        ).filter(
            or_(
                Ticket.ticket_number.ilike(f"%{query}%"),
                Ticket.short_description.ilike(f"%{query}%"),
            )
        ).limit(10).all()
        
        if not matching:
            return {"tickets": [], "message": f"No tickets found matching '{query}'"}
        
        from services.xgboost_trainer import engineer_features, generate_labels
        
        results = []
        for t in matching:
            # Build single-ticket dataframe
            d = {}
            for col in Ticket.__table__.columns:
                d[col.name] = getattr(t, col.name, None)
            df = pd.DataFrame([d])
            
            features_df, used_features = engineer_features(df)
            for f in feature_names:
                if f not in features_df.columns:
                    features_df[f] = 0
            X = features_df[feature_names].values
            
            # Prediction
            pred = model.predict(X)[0]
            prob = float(model.predict_proba(X)[0][1])
            
            # Per-ticket SHAP
            shap_values_list = []
            try:
                import shap
                explainer = shap.TreeExplainer(model)
                shap_vals = explainer.shap_values(X)[0]
                base_value = float(explainer.expected_value)
                
                # Build waterfall: feature name, value, SHAP contribution
                feature_contribs = []
                for i, fname in enumerate(feature_names):
                    feature_contribs.append({
                        "feature": fname,
                        "value": round(float(X[0][i]), 4),
                        "shap": round(float(shap_vals[i]), 4),
                    })
                
                # Sort by absolute SHAP
                feature_contribs.sort(key=lambda x: abs(x['shap']), reverse=True)
                shap_values_list = feature_contribs[:15]  # Top 15
            except Exception as e:
                base_value = 0
                print(f"SHAP error for ticket: {e}")
            
            # True label
            label_df = pd.DataFrame([d])
            labels = generate_labels(label_df)
            true_label = int(labels[0]) if len(labels) > 0 else None
            
            results.append({
                "ticket_number": t.ticket_number or f"T-{t.id}",
                "short_description": (t.short_description or "")[:150],
                "assignment_group": t.assignment_group or "Unknown",
                "priority": t.priority or "—",
                "channel": t.channel or t.contact_type or "Unknown",
                "mttr_hours": round(t.mttr_hours, 2) if t.mttr_hours else None,
                "reassignment_count": t.reassignment_count or 0,
                "reopen_count": t.reopen_count or 0,
                "cluster_id": t.cluster_id,
                "is_already_automated": bool(t.is_already_automated) if t.is_already_automated is not None else False,
                "can_be_automated": bool(t.can_be_automated) if t.can_be_automated is not None else False,
                "resolved_by": t.resolved_by or None,
                "resolved_by_group": t.resolved_by_group or None,
                "sys_updated_by": t.sys_updated_by or None,
                "aiops_automation_status": t.aiops_automation_status or None,
                "aiops_solution_lever": t.aiops_solution_lever or None,
                "aiops_category": t.aiops_category or None,
                "opened": str(t.opened) if t.opened else None,
                "resolved": str(t.resolved) if t.resolved else None,
                "prediction": "Automatable" if pred == 1 else "Manual",
                "confidence": round(prob * 100, 1),
                "true_label": "Automatable" if true_label == 1 else "Manual" if true_label == 0 else "Unknown",
                "correct": bool(pred == true_label) if true_label is not None else None,
                "shap_waterfall": shap_values_list,
                "shap_base_value": base_value if shap_values_list else None,
            })
        
        return {
            "tickets": results,
            "query": query,
            "count": len(results),
        }
    finally:
        db.close()


# ============================================================
# TICKET CONTEXT — Cluster Intelligence (DB only, instant)
# ============================================================

@router.get("/ticket-context/{upload_id}/{ticket_number}")
def get_ticket_context(
    upload_id: int,
    ticket_number: str,
    user: dict = Depends(require_upload_access)
):
    """
    Get cluster intelligence for a ticket: automation tools in use,
    automated vs non-automated counts, avg MTTRs, hours saveable.
    Pure DB query — no LLM, instant response.
    """
    from models import SessionLocal, Ticket
    from sqlalchemy import func
    db = SessionLocal()
    
    try:
        # Find the ticket
        ticket = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.ticket_number == ticket_number
        ).first()
        
        if not ticket:
            return {"error": f"Ticket {ticket_number} not found"}
        
        cluster_id = ticket.cluster_id
        result = {
            "ticket_number": ticket_number,
            "resolved_by": ticket.resolved_by,
            "resolved_by_group": ticket.resolved_by_group,
            "sys_updated_by": ticket.sys_updated_by,
            "aiops_automation_status": ticket.aiops_automation_status,
            "aiops_solution_lever": ticket.aiops_solution_lever,
            "aiops_category": ticket.aiops_category,
            "aiops_subcategory": getattr(ticket, 'aiops_subcategory', None),
            "opened": str(ticket.opened) if ticket.opened else None,
            "resolved": str(ticket.resolved) if ticket.resolved else None,
            "cluster_id": cluster_id,
        }
        
        # Cluster intelligence
        if cluster_id is not None:
            cluster_tickets = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == cluster_id
            ).all()
            
            total = len(cluster_tickets)
            automated = [t for t in cluster_tickets if t.is_already_automated]
            not_automated = [t for t in cluster_tickets if not t.is_already_automated]
            
            # Avg MTTRs
            auto_mttrs = [t.mttr_hours for t in automated if t.mttr_hours is not None and t.mttr_hours > 0]
            manual_mttrs = [t.mttr_hours for t in not_automated if t.mttr_hours is not None and t.mttr_hours > 0]
            
            avg_auto_mttr = round(sum(auto_mttrs) / len(auto_mttrs), 3) if auto_mttrs else None
            avg_manual_mttr = round(sum(manual_mttrs) / len(manual_mttrs), 3) if manual_mttrs else None
            
            # Hours saveable
            hours_saveable = None
            if avg_auto_mttr is not None and avg_manual_mttr is not None and len(not_automated) > 0:
                hours_saveable = round(len(not_automated) * (avg_manual_mttr - avg_auto_mttr), 1)
            
            # Tools in use within this cluster
            tool_stats = {}
            for t in cluster_tickets:
                tool = t.aiops_solution_lever or t.resolved_by_group or "No tool (Manual)"
                if tool not in tool_stats:
                    tool_stats[tool] = {"count": 0, "mttrs": []}
                tool_stats[tool]["count"] += 1
                if t.mttr_hours is not None and t.mttr_hours > 0:
                    tool_stats[tool]["mttrs"].append(t.mttr_hours)
            
            tools_list = []
            for tool_name, stats in sorted(tool_stats.items(), key=lambda x: -x[1]["count"]):
                avg_mttr = round(sum(stats["mttrs"]) / len(stats["mttrs"]), 3) if stats["mttrs"] else None
                tools_list.append({
                    "tool": tool_name,
                    "count": stats["count"],
                    "percentage": round(stats["count"] / total * 100, 1),
                    "avg_mttr": avg_mttr,
                })
            
            result["cluster_stats"] = {
                "total": total,
                "automated_count": len(automated),
                "automated_pct": round(len(automated) / total * 100, 1) if total > 0 else 0,
                "not_automated_count": len(not_automated),
                "avg_auto_mttr": avg_auto_mttr,
                "avg_manual_mttr": avg_manual_mttr,
                "hours_saveable_per_year": hours_saveable,
                "tools": tools_list,
                "top_tool": tools_list[0]["tool"] if tools_list else None,
            }
        else:
            # No cluster — look at assignment group instead
            same_group = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.assignment_group == ticket.assignment_group
            ).all()
            
            total = len(same_group)
            automated = [t for t in same_group if t.is_already_automated]
            not_automated = [t for t in same_group if not t.is_already_automated]
            
            auto_mttrs = [t.mttr_hours for t in automated if t.mttr_hours is not None and t.mttr_hours > 0]
            manual_mttrs = [t.mttr_hours for t in not_automated if t.mttr_hours is not None and t.mttr_hours > 0]
            
            result["cluster_stats"] = {
                "total": total,
                "automated_count": len(automated),
                "automated_pct": round(len(automated) / total * 100, 1) if total > 0 else 0,
                "not_automated_count": len(not_automated),
                "avg_auto_mttr": round(sum(auto_mttrs) / len(auto_mttrs), 3) if auto_mttrs else None,
                "avg_manual_mttr": round(sum(manual_mttrs) / len(manual_mttrs), 3) if manual_mttrs else None,
                "hours_saveable_per_year": None,
                "tools": [],
                "top_tool": None,
                "note": f"No cluster assigned. Showing stats for assignment group: {ticket.assignment_group}",
            }
        
        return result
    finally:
        db.close()


# ============================================================
# TICKET RECOMMEND — LLM-powered (with DB fallback)
# ============================================================

class RecommendRequest(BaseModel):
    ticket_number: str
    short_description: str
    assignment_group: str = ""
    mttr_hours: Optional[float] = None
    reassignment_count: int = 0
    cluster_total: int = 0
    automated_count: int = 0
    not_automated_count: int = 0
    avg_auto_mttr: Optional[float] = None
    avg_manual_mttr: Optional[float] = None
    top_tools: List[str] = []
    aiops_solution_lever: Optional[str] = None


@router.post("/ticket-recommend/{upload_id}")
def get_ticket_recommendations(
    upload_id: int,
    request: RecommendRequest,
    user: dict = Depends(require_upload_access)
):
    """
    Get automation recommendations. Tries LLM first (Ollama),
    falls back to data-driven recommendations if LLM unavailable.
    """
    import requests as http_requests
    
    # Build context for LLM
    context = f"""ITSM Ticket Analysis:
- Ticket: {request.short_description}
- Assignment Group: {request.assignment_group}
- Current MTTR: {request.mttr_hours}h
- Reassignments: {request.reassignment_count}
- Cluster: {request.cluster_total} similar tickets
- Already automated: {request.automated_count} ({round(request.automated_count/max(request.cluster_total,1)*100)}%) via {', '.join(request.top_tools[:3]) if request.top_tools else 'unknown'}
- Not yet automated: {request.not_automated_count} tickets, avg {request.avg_manual_mttr}h MTTR
- Current automation tool: {request.aiops_solution_lever or 'None'}"""

    prompt = f"""{context}

Based on this ITSM ticket data, suggest exactly 5 specific automation approaches to handle this type of ticket. For each suggestion include:
1. Tool/platform name (real tools like ServiceNow Orchestrator, Ansible, SCCM, BMC Helix, custom scripts, self-heal agents, etc.)
2. One-line implementation approach
3. Expected MTTR after automation

Respond ONLY in this JSON format, no other text:
[
  {{"tool": "Tool Name", "approach": "One-line implementation", "expected_mttr": "0.05h"}},
  ...
]"""

    # Try LLM (Ollama)
    llm_response = None
    source = "llm"
    
    try:
        resp = http_requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1000}
            },
            timeout=15
        )
        
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            # Try to parse JSON from response
            import re
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                llm_response = json.loads(json_match.group())
    except Exception as e:
        print(f"Ollama not available: {e}")
    
    # Fallback: data-driven recommendations
    if not llm_response:
        source = "data-driven"
        llm_response = []
        
        # Recommend based on what's already working in the cluster
        if request.top_tools:
            for i, tool in enumerate(request.top_tools[:3]):
                llm_response.append({
                    "tool": tool,
                    "approach": f"Extend existing {tool} coverage to remaining {request.not_automated_count} tickets in this cluster",
                    "expected_mttr": f"{request.avg_auto_mttr or 0.05}h"
                })
        
        # Add generic but real recommendations based on ticket type
        desc_lower = (request.short_description or "").lower()
        
        if "disk" in desc_lower or "space" in desc_lower or "storage" in desc_lower:
            llm_response.append({"tool": "Auto-Remediation Script", "approach": "Disk cleanup script triggered by monitoring threshold (90%+ usage)", "expected_mttr": "0.02h"})
            llm_response.append({"tool": "ServiceNow Orchestrator", "approach": "Event-driven workflow: detect threshold → trigger cleanup → validate → auto-close", "expected_mttr": "0.05h"})
        elif "password" in desc_lower or "pwd" in desc_lower or "reset" in desc_lower or "unlock" in desc_lower:
            llm_response.append({"tool": "Self-Service Portal", "approach": "AD-integrated self-service password reset with MFA verification", "expected_mttr": "0.01h"})
            llm_response.append({"tool": "ServiceNow Virtual Agent", "approach": "Chatbot-driven password reset with LDAP integration", "expected_mttr": "0.02h"})
        elif "ping" in desc_lower or "unreachable" in desc_lower or "down" in desc_lower:
            llm_response.append({"tool": "Self-Heal Agent", "approach": "Auto-restart services, verify connectivity, escalate only if unresolved", "expected_mttr": "0.1h"})
            llm_response.append({"tool": "Ansible Playbook", "approach": "Automated diagnostics: ping → service check → restart → validate → close", "expected_mttr": "0.08h"})
        elif "backup" in desc_lower or "restore" in desc_lower:
            llm_response.append({"tool": "BMC Helix / Commvault", "approach": "Automated backup retry with error classification and escalation rules", "expected_mttr": "0.15h"})
            llm_response.append({"tool": "ServiceNow Orchestrator", "approach": "Backup failure workflow: classify error → retry → notify → auto-close on success", "expected_mttr": "0.1h"})
        elif "cpu" in desc_lower or "memory" in desc_lower or "performance" in desc_lower:
            llm_response.append({"tool": "Auto-Remediation (Netcool)", "approach": "Process kill for runaway processes, service restart, threshold-based scaling", "expected_mttr": "0.05h"})
            llm_response.append({"tool": "Ansible + Monitoring", "approach": "Auto-scaling playbook triggered by sustained CPU > 90% for 5 min", "expected_mttr": "0.08h"})
        else:
            llm_response.append({"tool": "ServiceNow Orchestrator", "approach": "Build event-driven workflow based on ticket pattern classification", "expected_mttr": "0.1h"})
            llm_response.append({"tool": "Ansible Automation Platform", "approach": "Create runbook automation with pre-built diagnostic steps", "expected_mttr": "0.15h"})
        
        # Always add these general ones if we have less than 5
        if len(llm_response) < 5:
            llm_response.append({"tool": "SCCM / Intune", "approach": "Endpoint management automation for Windows fleet maintenance", "expected_mttr": "0.1h"})
        if len(llm_response) < 5:
            llm_response.append({"tool": "Custom Python Script + Cron", "approach": "Lightweight scheduled automation for recurring patterns", "expected_mttr": "0.05h"})
        
        llm_response = llm_response[:5]
    
    return {
        "recommendations": llm_response,
        "source": source,
        "ticket_number": request.ticket_number,
        "hours_saveable": round(request.not_automated_count * ((request.avg_manual_mttr or 0) - (request.avg_auto_mttr or 0)), 1) if request.avg_manual_mttr else None,
    }

# ============================================================
# HUMAN-IN-THE-LOOP: Save override feedback
# ============================================================

class OverrideRequest(BaseModel):
    ticket_number: str
    override_status: str  # "Already Automated", "Can Be Automated", "Manual"


@router.post("/ticket-override/{upload_id}")
def save_ticket_override(
    upload_id: int,
    request: OverrideRequest,
    user: dict = Depends(require_upload_access)
):
    """
    Save human correction for a ticket's automation status.
    Used in next XGBoost training run as ground truth.
    """
    from models import SessionLocal, Ticket
    from datetime import datetime
    db = SessionLocal()
    
    try:
        ticket = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.ticket_number == request.ticket_number
        ).first()
        
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {request.ticket_number} not found")
        
        ticket.human_override = request.override_status
        ticket.label_source = "ticket_view"
        ticket.override_by = user.get('user_id', 'unknown')
        ticket.override_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "saved",
            "ticket_number": request.ticket_number,
            "override": request.override_status,
            "by": user.get('username', 'unknown'),
        }
    finally:
        db.close()