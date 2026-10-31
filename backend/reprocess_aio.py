"""
reprocess_aio.py (v2)
======================
Reprocess existing uploads with AIO classification.
Uses ML-first approach: Qwen LLM + BERT cluster propagation + heuristic fallback.

Usage:
    python reprocess_aio.py                        # Latest upload
    python reprocess_aio.py --upload-id 65         # Specific upload
    python reprocess_aio.py --all                  # All uploads
    python reprocess_aio.py --upload-id 65 --llm   # Force LLM summaries
"""

import argparse
import time
from collections import Counter
from models import SessionLocal, Ticket, Upload


def reprocess_upload(upload_id: int, use_llm: bool = False, batch_size: int = 1000):
    """Reprocess a single upload with AIO classification."""
    
    print(f"\n{'='*70}")
    print(f"  REPROCESSING UPLOAD {upload_id}")
    print(f"{'='*70}")
    
    start = time.time()
    db = SessionLocal()
    
    try:
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            print(f"  Upload {upload_id} not found")
            return
        
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        total = len(tickets)
        
        if total == 0:
            print(f"  No tickets found")
            return
        
        print(f"  File: {upload.filename}")
        print(f"  Tickets: {total}")
        
        # --- Get existing cluster labels ---
        cluster_labels = []
        has_clusters = False
        for t in tickets:
            cid = t.cluster_id if t.cluster_id is not None else -1
            cluster_labels.append(cid)
            if cid != -1:
                has_clusters = True
        
        if has_clusters:
            unique_clusters = len(set(c for c in cluster_labels if c != -1))
            print(f"  Clusters: {unique_clusters} (using existing)")
        else:
            print(f"  Clusters: None (heuristic only)")
            cluster_labels = None
        
        # --- Run AIO classifier ---
        from services.aio_classifier import classify_batch
        
        print(f"\n  Running ML-first classification...")
        results = classify_batch(
            tickets=tickets,
            cluster_labels=cluster_labels,
        )
        
        # --- Generate summaries ---
        from services.description_cleaner import build_smart_summary
        
        print(f"\n  Generating summaries...")
        
        # --- Update database ---
        print(f"\n  Updating database...")
        
        for i in range(0, total, batch_size):
            batch_end = min(i + batch_size, total)
            
            for j in range(i, batch_end):
                ticket = tickets[j]
                result = results[j]
                
                # Update AIO columns
                ticket.aio_tower = result.get('aio_tower', '')
                ticket.aio_category = result.get('aio_category', '')
                ticket.aio_subcategory = result.get('aio_subcategory', '')
                ticket.aio_detail = result.get('aio_detail', '')
                ticket.aio_confidence = result.get('aio_confidence', 0.5)
                ticket.aio_classified_by = result.get('aio_classified_by', 'heuristic')
                ticket.aio_needs_review = result.get('aio_needs_review', False)
                
                # Generate summary
                ticket.aio_summary = build_smart_summary(
                    short_desc=ticket.short_description or '',
                    resolution_notes=ticket.resolution_notes or '',
                    resolved_by=ticket.resolved_by or '',
                    mttr_hours=ticket.mttr_hours,
                    assignment_group=ticket.assignment_group or '',
                    channel=ticket.channel or '',
                    aio_subcategory=ticket.aio_subcategory or '',
                )
                
                # Sync legacy columns (for backward compatibility)
                if ticket.aio_tower and not ticket.aiops_type:
                    ticket.aiops_type = 'Technical' if ticket.aio_tower in ['Server', 'Network', 'Database', 'Storage/Backup', 'Cloud', 'Security'] else 'Functional'
                if ticket.aio_category and not ticket.aiops_category:
                    ticket.aiops_category = ticket.aio_category
                if ticket.aio_subcategory and not ticket.aiops_subcategory:
                    ticket.aiops_subcategory = ticket.aio_subcategory
            
            db.commit()
            print(f"    {batch_end}/{total}")
        
        # --- Print statistics ---
        elapsed = time.time() - start
        
        print(f"\n{'='*70}")
        print(f"  AIO CLASSIFICATION STATISTICS")
        print(f"{'='*70}")
        
        # Tower distribution
        tower_counts = Counter(t.aio_tower for t in tickets if t.aio_tower)
        print(f"\n  Tower Distribution:")
        max_bar = 50
        max_count = max(tower_counts.values()) if tower_counts else 1
        for tower, count in tower_counts.most_common(15):
            pct = count / total * 100
            bar = '█' * int(count / max_count * max_bar)
            print(f"    {tower:25s} {count:>6,} ({pct:5.1f}%) {bar}")
        
        # Category distribution
        cat_counts = Counter(t.aio_category for t in tickets if t.aio_category)
        print(f"\n  Top 10 Categories:")
        for cat, count in cat_counts.most_common(10):
            pct = count / total * 100
            print(f"    {cat:30s} {count:>6,} ({pct:5.1f}%)")
        
        # SubCategory distribution
        subcat_counts = Counter(t.aio_subcategory for t in tickets if t.aio_subcategory)
        print(f"\n  Top 10 Sub Categories:")
        for subcat, count in subcat_counts.most_common(10):
            pct = count / total * 100
            print(f"    {subcat:30s} {count:>6,} ({pct:5.1f}%)")
        
        # Classification method
        method_counts = Counter(t.aio_classified_by for t in tickets if t.aio_classified_by)
        print(f"\n  Classification Method:")
        for method, count in method_counts.most_common():
            print(f"    {method:20s} {count:>6,} ({count/total*100:.1f}%)")
        
        # Confidence stats
        confidences = [t.aio_confidence for t in tickets if t.aio_confidence]
        if confidences:
            avg_conf = sum(confidences) / len(confidences) * 100
            print(f"\n  Confidence: avg={avg_conf:.1f}%")
        
        # Needs review
        needs_review = sum(1 for t in tickets if t.aio_needs_review)
        print(f"  Needs Review: {needs_review} tickets ({needs_review/total*100:.1f}%)")
        
        print(f"\n{'='*70}")
        print(f"  Completed in {elapsed:.1f}s ({total} tickets)")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Reprocess uploads with AIO classification")
    parser.add_argument("--upload-id", type=int, help="Specific upload ID")
    parser.add_argument("--all", action="store_true", help="Reprocess all uploads")
    parser.add_argument("--llm", action="store_true", help="Use LLM for summaries")
    args = parser.parse_args()
    
    if args.all:
        db = SessionLocal()
        uploads = db.query(Upload).filter(Upload.status == "completed").order_by(Upload.id).all()
        db.close()
        
        print(f"\nFound {len(uploads)} uploads to reprocess")
        for u in uploads:
            reprocess_upload(u.id, use_llm=args.llm)
    
    elif args.upload_id:
        reprocess_upload(args.upload_id, use_llm=args.llm)
    
    else:
        # Default: latest upload
        db = SessionLocal()
        latest = db.query(Upload).filter(Upload.status == "completed").order_by(Upload.id.desc()).first()
        db.close()
        
        if latest:
            print(f"Reprocessing latest upload: {latest.id} ({latest.filename})")
            reprocess_upload(latest.id, use_llm=args.llm)
        else:
            print("No completed uploads found")
            print("Usage: python reprocess_aio.py --upload-id 65")


if __name__ == "__main__":
    main()