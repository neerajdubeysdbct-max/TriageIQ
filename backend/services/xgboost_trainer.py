"""
XGBoost X-Ray Trainer Service
Real XGBoost training with SHAP explainability, feature engineering,
calibration metrics, and What-If simulation.

This replaces the rule-based scoring with genuine ML training.
"""

import numpy as np
import pandas as pd
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ML imports
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    precision_recall_curve, roc_curve
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def engineer_features(tickets_df: pd.DataFrame, cluster_info: dict = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Extract rich features from ticket data for XGBoost training.
    
    Returns:
        features_df: DataFrame with engineered features
        feature_names: List of feature column names
    """
    features = pd.DataFrame(index=tickets_df.index)
    
    # --- 1. Resolution Time Features ---
    mttr = pd.to_numeric(tickets_df['mttr_hours'], errors='coerce').fillna(0)
    features['mttr_hours'] = mttr
    mttr = pd.to_numeric(mttr, errors='coerce').fillna(0)
    features['mttr_log'] = np.log1p(mttr)
    features['mttr_is_fast'] = (mttr < 1).astype(int)          # < 1 hour
    features['mttr_is_very_fast'] = (mttr < 0.17).astype(int)  # < 10 min
    
    # --- 2. Reassignment & Reopen ---
    features['reassignment_count'] = tickets_df['reassignment_count'].fillna(0).clip(0, 20)
    features['reopen_count'] = tickets_df['reopen_count'].fillna(0).clip(0, 10)
    features['zero_reassignment'] = (features['reassignment_count'] == 0).astype(int)
    features['high_reassignment'] = (features['reassignment_count'] >= 3).astype(int)
    
    # --- 3. Text-based Features ---
    desc = tickets_df['short_description'].fillna('')
    features['desc_length'] = desc.str.len()
    features['desc_word_count'] = desc.str.split().str.len().fillna(0)
    
    # Description entropy (diversity of characters — low entropy = templated/repetitive)
    def char_entropy(text):
        if not text or len(text) < 2:
            return 0
        from collections import Counter
        counts = Counter(text.lower())
        total = len(text)
        probs = [c / total for c in counts.values()]
        return -sum(p * np.log2(p) for p in probs if p > 0)
    
    features['desc_entropy'] = desc.apply(char_entropy)
    
    # Resolution notes features
    if 'resolution_notes' in tickets_df.columns:
        res = tickets_df['resolution_notes'].fillna('')
        features['resolution_length'] = res.str.len()
        features['has_resolution'] = (res.str.len() > 5).astype(int)
    else:
        features['resolution_length'] = 0
        features['has_resolution'] = 0
    
    # --- 4. Channel Features ---
    if 'contact_type' in tickets_df.columns:
        contact = tickets_df['contact_type'].fillna('Unknown').str.lower()
        features['is_portal'] = contact.str.contains('portal|self-service|self_service', regex=True).astype(int)
        features['is_email'] = contact.str.contains('email', regex=True).astype(int)
        features['is_event'] = contact.str.contains('event|monitoring|alert', regex=True).astype(int)
        features['is_phone'] = contact.str.contains('phone|call', regex=True).astype(int)
    else:
        features['is_portal'] = 0
        features['is_email'] = 0
        features['is_event'] = 0
        features['is_phone'] = 0
    
    # --- 5. Time Features ---
    if 'opened' in tickets_df.columns:
        opened = pd.to_datetime(tickets_df['opened'], errors='coerce')
        features['hour_of_day'] = opened.dt.hour.fillna(12)
        features['day_of_week'] = opened.dt.dayofweek.fillna(3)
        features['is_weekend'] = (features['day_of_week'] >= 5).astype(int)
        features['is_business_hours'] = ((features['hour_of_day'] >= 8) & (features['hour_of_day'] <= 18)).astype(int)
    else:
        features['hour_of_day'] = 12
        features['day_of_week'] = 3
        features['is_weekend'] = 0
        features['is_business_hours'] = 1
    
    # --- 6. Cluster Features ---
    if cluster_info and 'cluster_id' in tickets_df.columns:
        cluster_ids = tickets_df['cluster_id'].fillna(-1)
        features['cluster_size'] = cluster_ids.map(
            lambda cid: cluster_info.get(int(cid), {}).get('size', 0)
        ).fillna(0)
        features['cluster_mttr_var'] = cluster_ids.map(
            lambda cid: cluster_info.get(int(cid), {}).get('mttr_variance', 0)
        ).fillna(0)
        features['repeatability'] = cluster_ids.map(
            lambda cid: cluster_info.get(int(cid), {}).get('repeatability', 0)
        ).fillna(0)
    else:
        features['cluster_size'] = 0
        features['cluster_mttr_var'] = 0
        features['repeatability'] = 0
    
    # --- 7. Keyword Indicator Features ---
    desc_lower = desc.str.lower()
    features['kw_password'] = desc_lower.str.contains('password|pwd|reset|unlock', regex=True).astype(int)
    features['kw_server'] = desc_lower.str.contains('server|host|vm|virtual', regex=True).astype(int)
    features['kw_alert'] = desc_lower.str.contains('alert|threshold|monitoring|event', regex=True).astype(int)
    features['kw_disk'] = desc_lower.str.contains('disk|volume|space|capacity|storage', regex=True).astype(int)
    features['kw_network'] = desc_lower.str.contains('network|vpn|connectivity|port|switch', regex=True).astype(int)
    
    # Clean up any infinities or NaN
    features = features.replace([np.inf, -np.inf], 0).fillna(0)
    
    feature_names = features.columns.tolist()
    return features, feature_names


# ============================================================
# LABEL GENERATION (semi-supervised from existing data)
# ============================================================

def generate_automation_labels(tickets_df: pd.DataFrame) -> np.ndarray:
    """
    Generate binary automation labels from ticket data.
    Uses multiple signals to create pseudo-labels for training.
    
    Returns:
        labels: numpy array of 0 (not automatable) or 1 (automatable)
    """
    labels = np.zeros(len(tickets_df), dtype=int)
    scores = np.zeros(len(tickets_df), dtype=float)
    
    # Signal 1: Already automated status
    if 'aiops_automation_status' in tickets_df.columns:
        auto_status = tickets_df['aiops_automation_status'].fillna('')
        scores += (auto_status == 'Already Automated').astype(float) * 3.0
        scores += (auto_status == 'Can Be Automated').astype(float) * 2.0
    
    # Signal 2: Solution lever suggests automation
    if 'aiops_solution_lever' in tickets_df.columns:
        lever = tickets_df['aiops_solution_lever'].fillna('')
        auto_levers = ['Auto-Remediation', 'Script/Runbook', 'Self-Service Portal',
                       'RPA', 'Automation Tuning', 'Existing Automation']
        for al in auto_levers:
            scores += (lever == al).astype(float) * 1.5
    
    # Signal 3: Fast resolution
    mttr = tickets_df['mttr_hours'].fillna(999)
    scores += (mttr < 0.5).astype(float) * 1.0   # < 30 min
    scores += (mttr < 0.17).astype(float) * 1.0   # < 10 min (bonus)
    
    # Signal 4: Zero reassignments (clean routing = scriptable)
    reassign = tickets_df['reassignment_count'].fillna(5)
    scores += (reassign == 0).astype(float) * 0.8
    
    # Signal 5: Pattern keywords
    desc = tickets_df['short_description'].fillna('').str.lower()
    auto_keywords = ['password', 'reset', 'unlock', 'backup', 'alert', 'threshold',
                     'monitoring', 'disk space', 'memory', 'cpu', 'restart', 'service stopped']
    for kw in auto_keywords:
        scores += desc.str.contains(kw, regex=False).astype(float) * 0.5
    
    # Signal 6: Event management channel (monitoring alerts are automatable)
    if 'contact_type' in tickets_df.columns:
        contact = tickets_df['contact_type'].fillna('').str.lower()
        scores += contact.str.contains('event|monitoring', regex=True).astype(float) * 1.0
    
    # Negative signals (penalize)
    scores -= (mttr > 24).astype(float) * 1.5     # Very long resolution
    scores -= (reassign >= 3).astype(float) * 1.0  # Many reassignments
    
    manual_keywords = ['investigate', 'troubleshoot', 'complex', 'escalat', 'custom',
                       'vendor', 'hardware replacement', 'physical']
    for kw in manual_keywords:
        scores -= desc.str.contains(kw, regex=False).astype(float) * 0.8
    
    # Threshold: positive score = automatable
    labels = (scores >= 2.0).astype(int)
    
    return labels


# ============================================================
# XGBOOST TRAINING
# ============================================================

def train_xgboost_model(
    features_df: pd.DataFrame,
    labels: np.ndarray,
    feature_names: List[str],
    upload_id: int
) -> Dict:
    """
    Train XGBoost classifier with cross-validation.
    
    Returns:
        dict with model, metrics, feature importance, SHAP values, etc.
    """
    if not HAS_XGBOOST:
        return {"error": "XGBoost not installed. Run: pip install xgboost"}
    
    X = features_df.values.astype(np.float32)
    y = labels
    
    # Handle class imbalance
    pos_count = y.sum()
    neg_count = len(y) - pos_count
    scale_pos_weight = neg_count / max(pos_count, 1)
    
    print(f"\n{'='*60}")
    print(f"TRAINING XGBOOST MODEL")
    print(f"{'='*60}")
    print(f"Total samples: {len(y)}")
    print(f"Positive (automatable): {pos_count} ({pos_count/len(y)*100:.1f}%)")
    print(f"Negative (manual): {neg_count} ({neg_count/len(y)*100:.1f}%)")
    print(f"Scale pos weight: {scale_pos_weight:.2f}")
    
    # XGBoost parameters
    params = {
        'max_depth': 6,
        'learning_rate': 0.1,
        'n_estimators': 200,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'min_child_weight': 5,
        'scale_pos_weight': scale_pos_weight,
        'eval_metric': 'logloss',
        'random_state': 42,
        'use_label_encoder': False,
    }
    
    # Cross-validation (5-fold stratified)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    model = xgb.XGBClassifier(**params)
    
    # Get cross-validated predictions for metrics
    y_pred_cv = cross_val_predict(model, X, y, cv=skf, method='predict')
    y_prob_cv = cross_val_predict(model, X, y, cv=skf, method='predict_proba')[:, 1]
    
    # Train final model on all data
    model.fit(X, y)
    
    # ---- Metrics ----
    accuracy = accuracy_score(y, y_pred_cv)
    precision = precision_score(y, y_pred_cv, zero_division=0)
    recall = recall_score(y, y_pred_cv, zero_division=0)
    f1 = f1_score(y, y_pred_cv, zero_division=0)
    
    try:
        roc_auc = roc_auc_score(y, y_prob_cv)
    except ValueError:
        roc_auc = 0.5
    
    cm = confusion_matrix(y, y_pred_cv)
    
    print(f"\n--- Cross-Validated Metrics ---")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"ROC AUC:   {roc_auc:.4f}")
    
    # ---- Feature Importance ----
    importance_gain = model.feature_importances_  # gain-based
    
    # Also get importance by other metrics
    importance_dict = {
        'gain': importance_gain.tolist(),
        'features': feature_names,
    }
    
    # Sort by importance
    sorted_idx = np.argsort(importance_gain)[::-1]
    top_features = [(feature_names[i], float(importance_gain[i])) for i in sorted_idx[:15]]
    
    print(f"\n--- Top 10 Features ---")
    for name, imp in top_features[:10]:
        print(f"  {name:30s} {imp:.4f}")
    
    # ---- SHAP Values ----
    shap_data = None
    if HAS_SHAP:
        print(f"\nComputing SHAP values...")
        try:
            # Use a sample for large datasets
            sample_size = min(2000, len(X))
            sample_idx = np.random.RandomState(42).choice(len(X), sample_size, replace=False)
            X_sample = X[sample_idx]
            
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
            
            # Mean absolute SHAP per feature
            mean_shap = np.abs(shap_values).mean(axis=0)
            shap_sorted_idx = np.argsort(mean_shap)[::-1]
            
            shap_data = {
                'mean_abs_shap': mean_shap.tolist(),
                'features': feature_names,
                'top_shap': [
                    {'feature': feature_names[i], 'importance': float(mean_shap[i])}
                    for i in shap_sorted_idx[:15]
                ],
                'sample_size': sample_size,
                # Store per-sample SHAP for waterfall/force plots (just first 100)
                'sample_shap_values': shap_values[:100].tolist(),
                'sample_features': X_sample[:100].tolist(),
                'expected_value': float(explainer.expected_value) if isinstance(explainer.expected_value, (int, float, np.floating)) else float(explainer.expected_value[0]) if hasattr(explainer.expected_value, '__len__') else 0.0,
            }
            
            print(f"✓ SHAP computed on {sample_size} samples")
        except Exception as e:
            print(f"⚠ SHAP computation failed: {e}")
            shap_data = None
    
    # ---- ROC Curve Data ----
    fpr, tpr, roc_thresholds = roc_curve(y, y_prob_cv)
    roc_data = {
        'fpr': fpr[::max(1, len(fpr)//100)].tolist(),  # Sample to ~100 points
        'tpr': tpr[::max(1, len(tpr)//100)].tolist(),
        'auc': roc_auc,
    }
    
    # ---- Precision-Recall Curve ----
    pr_precision, pr_recall, pr_thresholds = precision_recall_curve(y, y_prob_cv)
    pr_data = {
        'precision': pr_precision[::max(1, len(pr_precision)//100)].tolist(),
        'recall': pr_recall[::max(1, len(pr_recall)//100)].tolist(),
    }
    
    # ---- Calibration Curve ----
    try:
        cal_fraction, cal_mean = calibration_curve(y, y_prob_cv, n_bins=10, strategy='uniform')
        calibration_data = {
            'fraction_of_positives': cal_fraction.tolist(),
            'mean_predicted_value': cal_mean.tolist(),
        }
    except Exception:
        calibration_data = None
    
    # ---- Confidence Distribution ----
    prob_bins = np.histogram(y_prob_cv, bins=20, range=(0, 1))
    confidence_dist = {
        'counts': prob_bins[0].tolist(),
        'bin_edges': prob_bins[1].tolist(),
    }
    
    # ---- Save Model ----
    os.makedirs('models', exist_ok=True)
    model_path = f'models/xgboost_xray_{upload_id}.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'feature_names': feature_names,
            'params': params,
            'trained_at': datetime.utcnow().isoformat(),
            'sample_count': len(y),
        }, f)
    print(f"\n✓ Model saved to {model_path}")
    
    # ---- Automation Frontier ----
    # Score distribution by predicted class
    auto_scores = y_prob_cv[y_pred_cv == 1]
    manual_scores = y_prob_cv[y_pred_cv == 0]
    
    frontier_data = {
        'automatable': {
            'count': int(y_pred_cv.sum()),
            'avg_confidence': float(auto_scores.mean()) if len(auto_scores) > 0 else 0,
            'score_distribution': np.histogram(auto_scores, bins=10, range=(0, 1))[0].tolist() if len(auto_scores) > 0 else [],
        },
        'manual': {
            'count': int((y_pred_cv == 0).sum()),
            'avg_confidence': float(manual_scores.mean()) if len(manual_scores) > 0 else 0,
            'score_distribution': np.histogram(manual_scores, bins=10, range=(0, 1))[0].tolist() if len(manual_scores) > 0 else [],
        },
        'threshold': 0.5,
        'total': len(y),
    }
    
    # ---- Package Results ----
    results = {
        'status': 'success',
        'upload_id': upload_id,
        'model_path': model_path,
        'training': {
            'total_samples': len(y),
            'positive_samples': int(pos_count),
            'negative_samples': int(neg_count),
            'class_ratio': f"{pos_count}:{neg_count}",
            'cv_folds': 5,
            'params': {k: v for k, v in params.items() if k != 'use_label_encoder'},
        },
        'metrics': {
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
            'roc_auc': round(roc_auc, 4),
            'confusion_matrix': cm.tolist(),
        },
        'feature_importance': {
            'top_features': top_features,
            'all_features': importance_dict,
        },
        'shap': shap_data,
        'roc_curve': roc_data,
        'pr_curve': pr_data,
        'calibration': calibration_data,
        'confidence_distribution': confidence_dist,
        'frontier': frontier_data,
        'trained_at': datetime.utcnow().isoformat(),
    }
    
    # Save results as JSON too
    results_path = f'models/xgboost_xray_results_{upload_id}.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"✓ Results saved to {results_path}\n")
    
    return results


# ============================================================
# WHAT-IF SIMULATOR
# ============================================================

def what_if_simulate(
    model_path: str,
    base_features: Dict[str, float],
    modifications: Dict[str, float],
    feature_names: List[str]
) -> Dict:
    """
    What-If simulator: modify feature values and see prediction change.
    
    Args:
        model_path: Path to saved XGBoost model
        base_features: Current feature values
        modifications: Features to change {feature_name: new_value}
        feature_names: List of feature names
    
    Returns:
        dict with original and modified predictions
    """
    with open(model_path, 'rb') as f:
        saved = pickle.load(f)
    
    model = saved['model']
    
    # Build feature vector
    base_vector = np.array([base_features.get(f, 0) for f in feature_names]).reshape(1, -1).astype(np.float32)
    modified_vector = base_vector.copy()
    
    for feat_name, new_val in modifications.items():
        if feat_name in feature_names:
            idx = feature_names.index(feat_name)
            modified_vector[0, idx] = new_val
    
    # Get predictions
    base_prob = model.predict_proba(base_vector)[0][1]
    modified_prob = model.predict_proba(modified_vector)[0][1]
    
    # Get SHAP if available
    shap_diff = None
    if HAS_SHAP:
        try:
            explainer = shap.TreeExplainer(model)
            base_shap = explainer.shap_values(base_vector)[0]
            mod_shap = explainer.shap_values(modified_vector)[0]
            shap_diff = {
                feature_names[i]: {
                    'base_shap': float(base_shap[i]),
                    'modified_shap': float(mod_shap[i]),
                    'delta': float(mod_shap[i] - base_shap[i])
                }
                for i in range(len(feature_names))
                if abs(mod_shap[i] - base_shap[i]) > 0.001
            }
        except Exception:
            pass
    
    return {
        'base_prediction': {
            'probability': round(float(base_prob), 4),
            'label': 'Automatable' if base_prob >= 0.5 else 'Manual',
            'confidence': round(float(max(base_prob, 1 - base_prob)) * 100, 1),
        },
        'modified_prediction': {
            'probability': round(float(modified_prob), 4),
            'label': 'Automatable' if modified_prob >= 0.5 else 'Manual',
            'confidence': round(float(max(modified_prob, 1 - modified_prob)) * 100, 1),
        },
        'delta': round(float(modified_prob - base_prob), 4),
        'modifications': modifications,
        'shap_diff': shap_diff,
    }


# ============================================================
# MAIN PIPELINE FUNCTION
# ============================================================

def run_xgboost_xray(upload_id: int) -> Dict:
    """
    Full XGBoost X-Ray pipeline:
    1. Load tickets from DB
    2. Engineer features
    3. Labels: the supervised automation classifier's decisions when it has
       scored this upload (the X-Ray is then a surrogate model that explains
       that classifier in operational terms; its metrics are fidelity, i.e.
       agreement with the classifier, not accuracy); otherwise heuristic
       pseudo-labels
    4. Train XGBoost with CV
    5. Compute SHAP
    6. Return comprehensive results
    """
    from models import SessionLocal, Ticket
    
    print(f"\n{'='*60}")
    print(f"XGBOOST X-RAY PIPELINE — Upload {upload_id}")
    print(f"{'='*60}\n")
    
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        if not tickets:
            return {"error": f"No tickets found for upload {upload_id}"}
        
        print(f"Loaded {len(tickets)} tickets")
        
        # Build DataFrame
        tickets_df = pd.DataFrame([{
            'short_description': t.short_description or '',
            'mttr_hours': t.mttr_hours or 0,
            'reassignment_count': t.reassignment_count or 0,
            'reopen_count': t.reopen_count or 0,
            'opened': t.opened,
            'resolution_notes': t.resolution_notes or '',
            'contact_type': t.contact_type or '',
            'cluster_id': t.cluster_id or -1,
            'cluster_similarity': t.cluster_similarity or 0,
            'aiops_automation_status': t.aiops_automation_status or '',
            'aiops_solution_lever': t.aiops_solution_lever or '',
            'assigned_to': t.assigned_to or '',
            'l4_automation_type': t.l4_automation_type or '',
            'model_automatable': bool(t.is_already_automated or t.can_be_automated),
            'model_scored': t.automation_confidence is not None,
        } for t in tickets])
        
        # Build cluster info
        cluster_info = {}
        if 'cluster_id' in tickets_df.columns:
            for cid in tickets_df['cluster_id'].unique():
                if cid == -1:
                    continue
                mask = tickets_df['cluster_id'] == cid
                cluster_tickets = tickets_df[mask]
                cluster_info[int(cid)] = {
                    'size': len(cluster_tickets),
                    'mttr_variance': cluster_tickets['mttr_hours'].std() if len(cluster_tickets) > 1 else 0,
                    'repeatability': len(cluster_tickets) / len(tickets_df),
                }
        
        # Step 1: Feature Engineering
        print("\nStep 1: Engineering features...")
        features_df, feature_names = engineer_features(tickets_df, cluster_info)
        print(f"✓ {len(feature_names)} features engineered")
        
        # Step 2: Generate Labels
        print("\nStep 2: Generating automation labels...")
        if tickets_df['model_scored'].all():
            labels = tickets_df['model_automatable'].astype(int).to_numpy()
            label_source = "automation_classifier"
        else:
            labels = generate_automation_labels(tickets_df)
            label_source = "heuristic_rules"
        print(f"Label source: {label_source}")
        print(f"✓ Labels: {labels.sum()} automatable, {len(labels) - labels.sum()} manual")
        
        # Step 3: Train Model
        print("\nStep 3: Training XGBoost...")
        results = train_xgboost_model(features_df, labels, feature_names, upload_id)
        results['label_source'] = label_source
        results['metric_meaning'] = (
            "fidelity: agreement with the supervised automation classifier"
            if label_source == "automation_classifier"
            else "agreement with heuristic pseudo-labels, not accuracy against ground truth")
        results_path = f'models/xgboost_xray_results_{upload_id}.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Add feature stats for What-If defaults
        results['feature_stats'] = {
            name: {
                'mean': round(float(features_df[name].mean()), 4),
                'std': round(float(features_df[name].std()), 4),
                'min': round(float(features_df[name].min()), 4),
                'max': round(float(features_df[name].max()), 4),
                'median': round(float(features_df[name].median()), 4),
            }
            for name in feature_names
        }
        
        return results
        
    finally:
        db.close()

# Alias for external imports
generate_labels = generate_automation_labels