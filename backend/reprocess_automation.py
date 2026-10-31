"""
reprocess_automation.py
-----------------------
Re-classify existing tickets with the new automation detection logic.
Run this after deploying automation_detector.py to fix existing datasets.

Usage:
    cd backend
    python reprocess_automation.py --upload_id 67
    python reprocess_automation.py --all
"""

import argparse
from models import SessionLocal, Ticket, Upload
from automation_detector import detect_automation_status
from sqlalchemy import func

def reprocess_upload(upload_id: int, verbose: bool = False):
    """Re-classify all tickets in an upload with new detection logic"""
    db = SessionLocal()
    
    try:
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            print(f"Upload {upload_id} not found!")
            return
        
        print(f"\n{'='*60}")
        print(f"REPROCESSING: {upload.filename}")
        print(f"Upload ID: {upload_id} | Total Tickets: {upload.total_tickets}")
        print(f"{'='*60}")
        
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        total = len(tickets)
        
        stats = {
            'Already Automated': 0,
            'Can Be Automated': 0,
            'Manual Only': 0,
            'Excluded': 0
        }
        
        solution_stats = {}
        
        for i, ticket in enumerate(tickets):
            # Build row dict from ticket
            row = {
                'ticket_number': ticket.ticket_number,
                'caller_id': ticket.caller_id,
                'affected_user': getattr(ticket, 'affected_user', ''),
                'assigned_to': ticket.assigned_to,
                'resolved_by': ticket.resolved_by,
                'sys_updated_by': ticket.sys_updated_by,
                'channel': ticket.channel,
                'category': ticket.category,
                'subcategory': ticket.subcategory,
                'assignment_group': ticket.assignment_group,
                'short_description': ticket.short_description,
                'description': ticket.description,
                'resolution_notes': ticket.resolution_notes,
                'close_notes': ticket.close_notes,
                'work_notes': ticket.work_notes,
                'resolution_code': getattr(ticket, 'resolution_code', ''),
                'mttr_hours': ticket.mttr_hours,
                'reassignment_count': ticket.reassignment_count,
                'reopen_count': getattr(ticket, 'reopen_count', 0),
                'existing_ia_category': getattr(ticket, 'existing_ia_category', None),
            }
            
            # Run new detection
            result = detect_automation_status(row)
            
            # Update ticket
            ticket.is_already_automated = result['status'] == 'Already Automated'
            ticket.can_be_automated = result['status'] == 'Can Be Automated'
            ticket.automation_potential_score = float(result['confidence'])
            ticket.aiops_automation_status = result['status']
            ticket.aiops_solution_lever = result['solution_lever']
            ticket.aiops_confidence = result['confidence'] / 100.0
            ticket.aiops_keywords = ' | '.join(result['evidence'][:5])
            ticket.aiops_additional_info = result['reasoning']
            ticket.aiops_predicted_by = 'rule_v2'
            
            # Update stats
            stats[result['status']] = stats.get(result['status'], 0) + 1
            solution_stats[result['solution_lever']] = solution_stats.get(result['solution_lever'], 0) + 1
            
            # Progress
            if (i + 1) % 5000 == 0:
                print(f"  Processed {i+1:,}/{total:,} tickets...")
                db.commit()
            
            # Verbose output for first few
            if verbose and i < 5:
                print(f"\n  [{ticket.ticket_number}]")
                print(f"    Status: {result['status']} ({result['confidence']}%)")
                print(f"    Solution: {result['solution_lever']}")
                print(f"    Evidence: {result['evidence'][:3]}")
        
        db.commit()
        
        # Update upload record
        already_auto = stats.get('Already Automated', 0)
        can_auto = stats.get('Can Be Automated', 0)
        manual = stats.get('Manual Only', 0)
        excluded = stats.get('Excluded', 0)
        valid_total = total - excluded
        
        upload.automation_current_pct = round(already_auto / max(valid_total, 1) * 100, 1)
        upload.automation_potential_pct = round(can_auto / max(valid_total, 1) * 100, 1)
        upload.high_complexity = manual
        db.commit()
        
        # Print results
        print(f"\n{'─'*60}")
        print("RESULTS:")
        print(f"{'─'*60}")
        print(f"\nAUTOMATION STATUS:")
        for status, count in sorted(stats.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1)
            bar = '█' * int(pct / 2)
            print(f"  {status:<20} {count:>8,} ({pct:>5.1f}%) {bar}")
        
        print(f"\nSOLUTION LEVERS:")
        for solution, count in sorted(solution_stats.items(), key=lambda x: -x[1])[:10]:
            pct = round(count / total * 100, 1)
            print(f"  {solution:<30} {count:>8,} ({pct:>5.1f}%)")
        
        print(f"\nUPDATE RECORD:")
        print(f"  Already Automated: {upload.automation_current_pct}%")
        print(f"  Can Be Automated:  {upload.automation_potential_pct}%")
        print(f"  High Complexity:   {upload.high_complexity:,}")
        
        return stats
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def reprocess_all():
    """Re-classify all uploads"""
    db = SessionLocal()
    try:
        uploads = db.query(Upload).filter(Upload.status == 'completed').all()
        print(f"Found {len(uploads)} completed uploads to reprocess")
        
        for upload in uploads:
            reprocess_upload(upload.id)
            
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reprocess automation classification')
    parser.add_argument('--upload_id', type=int, help='Specific upload ID to reprocess')
    parser.add_argument('--all', action='store_true', help='Reprocess all uploads')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    args = parser.parse_args()
    
    if args.all:
        reprocess_all()
    elif args.upload_id:
        reprocess_upload(args.upload_id, verbose=args.verbose)
    else:
        print("Usage:")
        print("  python reprocess_automation.py --upload_id 67")
        print("  python reprocess_automation.py --all")
        print("  python reprocess_automation.py --upload_id 67 --verbose")