"""
Complete ML Analysis Pipeline
Runs all ML models and generates visualizations
"""

import pandas as pd
import numpy as np
import random
from models import SessionLocal, Ticket
from services.ml_models import (
    bert_clustering,
    xgboost_scorer,
    automation_detector,
    multi_task_categorizer,
    generate_all_visualizations
)

MAX_BERT_TICKETS = 100000
TSNE_SAMPLE = 5000          # tickets placed on the 2-D cluster map


def run_complete_ml_analysis(upload_id: int) -> dict:
    """
    Run complete ML pipeline on uploaded tickets.
    Samples up to 5000 tickets for BERT clustering (statistically valid).
    """

    print("\n" + "="*70)
    print(f"STARTING COMPLETE ML ANALYSIS - Upload {upload_id}")
    print("="*70 + "\n")

    # Step 1: Load tickets from database
    print("Step 1/5: Loading tickets from database...")
    db = SessionLocal()
    all_tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()

    if len(all_tickets) == 0:
        print("ERROR: No tickets found!")
        db.close()
        return {"status": "failed", "error": "No tickets found"}

    # Above MAX_BERT_TICKETS a random sample is embedded and clustered; the other
    # tickets currently get no theme (nearest-centroid assignment is the planned fix)
    if len(all_tickets) > MAX_BERT_TICKETS:
        tickets = random.sample(all_tickets, MAX_BERT_TICKETS)
        print(f"✓ Loaded {len(all_tickets)} tickets — sampling {MAX_BERT_TICKETS} for BERT\n")
    else:
        tickets = all_tickets
        print(f"✓ Loaded {len(tickets)} tickets\n")

    # Convert to DataFrame
    tickets_df = pd.DataFrame([{
        'ticket_id': t.id,
        'short_description': t.short_description or 'No description',
        'mttr_hours': t.mttr_hours or 0,
        'reassignment_count': t.reassignment_count or 0,
        'reopen_count': t.reopen_count or 0,
        'opened': t.opened,
        'assigned_to': t.assigned_to or '',
        'resolution_notes': t.resolution_notes or '',
        'contact_type': t.contact_type or 'Unknown'
    } for t in tickets])

    # Step 2: BERT Clustering
    print("Step 2/5: Running BERT clustering...")
    descriptions = tickets_df['short_description'].tolist()

   
    embeddings = bert_clustering.load_model().encode_descriptions(descriptions)
    # Number of clusters chosen per upload by silhouette (services/cluster_selection.py)
    from services.cluster_selection import choose_k, normalize_rows
    from sklearn.metrics import silhouette_score
    embeddings = normalize_rows(embeddings)
    cluster_quality = choose_k(embeddings)
    cluster_labels, probs = bert_clustering.cluster_tickets(
        embeddings, method="kmeans", n_clusters=cluster_quality["chosen_k"])
    sample = np.random.default_rng(42).choice(len(embeddings), size=min(len(embeddings), 3000), replace=False)
    cluster_quality["final_silhouette"] = round(float(silhouette_score(embeddings[sample], cluster_labels[sample])), 4)
    import json, os
    os.makedirs(f"outputs/upload_{upload_id}", exist_ok=True)
    with open(f"outputs/upload_{upload_id}/cluster_quality.json", "w", encoding="utf-8") as f:
        json.dump(cluster_quality, f, indent=2)
    print(f"Chose k={cluster_quality['chosen_k']} (silhouette {cluster_quality['final_silhouette']})")

    tickets_df['cluster_id'] = cluster_labels
    tickets_df['cluster_probability'] = probs

    # 2-D map for the cluster view. t-SNE is for visualisation only (clustering
    # runs on the full embeddings) and scales badly, so large uploads are mapped
    # from a sample stratified by cluster; the other tickets get no map position.
    print("Computing t-SNE projection...")
    from sklearn.manifold import TSNE
    n = len(embeddings)
    if n > TSNE_SAMPLE:
        rng = np.random.default_rng(42)
        share = TSNE_SAMPLE / n
        idx = np.concatenate([
            rng.choice(members, size=max(1, int(round(len(members) * share))), replace=False)
            for members in (np.flatnonzero(cluster_labels == c) for c in np.unique(cluster_labels))
        ])
    else:
        idx = np.arange(n)
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(idx) - 1))
    coords = tsne.fit_transform(embeddings[idx])
    # Normalize to 0-100
    coords[:, 0] = (coords[:, 0] - coords[:, 0].min()) / (coords[:, 0].max() - coords[:, 0].min()) * 90 + 5
    coords[:, 1] = (coords[:, 1] - coords[:, 1].min()) / (coords[:, 1].max() - coords[:, 1].min()) * 90 + 5
    tickets_df['tsne_x'] = np.nan
    tickets_df['tsne_y'] = np.nan
    tickets_df.loc[tickets_df.index[idx], 'tsne_x'] = coords[:, 0]
    tickets_df.loc[tickets_df.index[idx], 'tsne_y'] = coords[:, 1]
    print(f"t-SNE map: {len(idx):,} of {n:,} tickets")

    n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    print(f"✓ Found {n_clusters} clusters\n")

    # Step 3: Auto-Categorization (L1/L2/L3/L4)
    print("Step 3/5: Running auto-categorization...")
    multi_task_categorizer.load_models()

    categorizations = []
    for desc in descriptions:
        cat = multi_task_categorizer.predict_categories(desc)
        categorizations.append(cat)

    tickets_df['l1_category'] = [c['l1_category'] for c in categorizations]
    tickets_df['l2_subcategory'] = [c['l2_subcategory'] for c in categorizations]
    tickets_df['l3_automation_feasibility'] = [c['l3_automation_feasibility'] for c in categorizations]
    tickets_df['l4_automation_type'] = [c['l4_automation_type'] for c in categorizations]

    print(f"✓ Categorized into {tickets_df['l1_category'].nunique()} L1 categories\n")

    # Step 4: Automation Scoring
    print("Step 4/5: Running automation scoring...")

    cluster_info = {}
    for cluster_id in set(cluster_labels):
        if cluster_id == -1:
            continue
        cluster_mask = cluster_labels == cluster_id
        cluster_tickets = tickets_df[cluster_mask]
        cluster_info[cluster_id] = {
            'size': len(cluster_tickets),
            'mttr_variance': cluster_tickets['mttr_hours'].std(),
            'repeatability': len(cluster_tickets) / len(tickets_df)
        }

    features = xgboost_scorer.extract_features(tickets_df, cluster_info)
    automation_scores = xgboost_scorer.predict_automation_score(features)
    tickets_df['automation_potential_score'] = automation_scores

    tickets_df['is_already_automated'] = tickets_df.apply(
        lambda row: automation_detector.is_already_automated(row), axis=1
    )
    tickets_df['can_be_automated'] = automation_scores >= 60

    print(f"✓ Scored automation potential")
    print(f"  - Already automated: {tickets_df['is_already_automated'].sum()} tickets")
    print(f"  - Can be automated: {tickets_df['can_be_automated'].sum()} tickets\n")

    # Step 5: Update database
    print("Step 5/5: Updating database with ML predictions...")

    for idx, row in tickets_df.iterrows():
        ticket = tickets[idx]
        ticket.cluster_id = int(row['cluster_id'])
        ticket.l1_category = row['l1_category']
        ticket.l2_subcategory = row['l2_subcategory']
        ticket.l3_automation_feasibility = row['l3_automation_feasibility']
        ticket.l4_automation_type = row['l4_automation_type']
        ticket.automation_potential_score = float(row['automation_potential_score'])
        ticket.is_already_automated = bool(row['is_already_automated'])
        ticket.can_be_automated = bool(row['can_be_automated'])
        ticket.tsne_x = None if pd.isna(row['tsne_x']) else float(row['tsne_x'])
        ticket.tsne_y = None if pd.isna(row['tsne_y']) else float(row['tsne_y'])

    db.commit()
    db.close()
    print(f"✓ Database updated\n")

    # Step 6: Generate visualizations
    print("Step 6/6: Generating visualizations...")

    # Feature importance comes from the trained automation classifier's SHAP
    # values (services.automation_scoring), never from hand-typed numbers.
    feature_importance, feature_names = None, None

    output_dir = generate_all_visualizations(
        tickets_df=tickets_df,
        embeddings=embeddings,
        cluster_labels=cluster_labels,
        automation_scores=automation_scores,
        feature_importance=feature_importance,
        feature_names=feature_names,
        upload_id=upload_id
    )

    # Save cluster summary
    try:
        cluster_summary = bert_clustering.get_cluster_summary(descriptions, cluster_labels)
        import os
        os.makedirs('outputs', exist_ok=True)
        with open(f'outputs/cluster_summary_{upload_id}.txt', 'w', encoding='utf-8') as f:
            f.write(f"Cluster Summary for Upload {upload_id}\n")
            f.write(f"Total Tickets: {len(descriptions)}\n")
            f.write("="*60 + "\n\n")
            sorted_clusters = sorted(cluster_summary.items(), key=lambda x: x[1]['count'], reverse=True)
            for cluster_id, data in sorted_clusters:
                label = f"NOISE" if cluster_id == -1 else str(cluster_id)
                f.write(f"Cluster {label} ({data['count']} tickets)\n")
                f.write(f"  Top Keywords: {', '.join(data['top_words'][:7])}\n")
                for i, desc in enumerate(data['samples'][:5], 1):
                    f.write(f"    {i}. {desc[:80]}\n")
                f.write("\n")
    except Exception as e:
        print(f"Cluster summary skipped: {e}")

    print(f"\n{'='*70}")
    print(f"✅ ML ANALYSIS COMPLETE!")
    print(f"📊 Visualizations saved to: {output_dir}")
    print(f"{'='*70}\n")

    summary = {
        'status': 'completed',
        'upload_id': upload_id,
        'total_tickets': len(tickets),
        'clusters_found': n_clusters,
        'already_automated_count': int(tickets_df['is_already_automated'].sum()),
        'can_automate_count': int(tickets_df['can_be_automated'].sum()),
        'avg_automation_score': float(automation_scores.mean()),
        'output_directory': output_dir
    }

    return summary
