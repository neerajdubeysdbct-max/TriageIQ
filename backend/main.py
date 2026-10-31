from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from models import SessionLocal, User, Ticket, Upload
from auth import get_password_hash, create_access_token, verify_password
from config import CORS_ORIGINS
from dependencies import get_current_user, require_admin, require_upload_access
from chunk_processor import save_tickets_only, run_ml_in_background

ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls"}
import os
import hashlib
import uuid
from sqlalchemy import Integer
from sqlalchemy import func
from utils import EFFORT_MINUTES_PER_TICKET, automation_savings, months_covered, priority_level_sql, sla_breach_sql
from models import Upload
from routers import copilot, ml_models, predictions


from routers.cluster_intelligence import router as cluster_intelligence_router
app = FastAPI(title="TriageIQ API")


from routers.copilot_export import router as copilot_export_router
app.include_router(copilot_export_router)

from routers.roi_calculator import router as roi_calculator_router
app.include_router(roi_calculator_router)

from routers.xgboost_xray import router as xgboost_xray_router
app.include_router(xgboost_xray_router)

from routers.ticket_intelligence import router as ticket_intelligence_router
app.include_router(ticket_intelligence_router)

from routers.system import router as system_router
app.include_router(system_router)

from routers.review import router as review_router
app.include_router(review_router)

from routers.model_admin import router as model_admin_router
app.include_router(model_admin_router)

from routers.rag import router as rag_router
app.include_router(rag_router)


@app.on_event("startup")
def _warm_embedding_model():
    """Load the sentence encoder in the background so the first copilot question is not slow."""
    import threading
    from services.rag.retrieval import _encoder
    threading.Thread(target=_encoder, daemon=True).start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# New routers
app.include_router(cluster_intelligence_router)
app.include_router(copilot.router)
app.include_router(ml_models.router)
app.include_router(predictions.router)


@app.get("/")
def read_root():
    return {"message": "TriageIQ API Running", "status": "success"}

@app.get("/health")
async def health_check():
    """Real dependency checks: Postgres round-trip, local LLM, trained classifier."""
    from sqlalchemy import text
    from routers.copilot import check_ollama
    from services.automation_scoring import MODEL_PATH

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as e:
        database = f"error: {e.__class__.__name__}"
    finally:
        db.close()

    checks = {
        "database": database,
        "llm": "ok" if await check_ollama() else "unreachable",
        "automation_model": "ok" if os.path.exists(MODEL_PATH) else "not trained",
    }
    status = "healthy" if database == "ok" else "unhealthy"
    if status == "healthy" and any(v != "ok" for v in checks.values()):
        status = "degraded"
    return {"status": status, "checks": checks}

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(401, "Invalid credentials")
        token = create_access_token(user.username, user.team_id)
        return {"access_token": token, "token_type": "bearer"}
    finally:
        db.close()

@app.post("/api/signup")
def signup(
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    team_id: str = Form(None),
    admin: dict = Depends(require_admin),
):
    """Admin-only: a self-chosen team_id would give access to that team's uploads."""
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(400, "Username exists")
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            team_id=team_id if team_id else username
        )
        db.add(user)
        db.commit()
        return {"message": "User created"}
    finally:
        db.close()

@app.post("/api/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # Validate file type (case-insensitive; the client's file name is never used as a path)
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(400, "Only CSV and Excel files allowed")

        # Read file content
        content = await file.read()

        # Check file size
        size_mb = len(content) / 1024 / 1024
        if size_mb > 200:
            raise HTTPException(413, f"File too large ({size_mb:.1f}MB). Max 200MB")

        # ===== DUPLICATE DETECTION =====
        file_hash = hashlib.md5(content).hexdigest()
        existing = db.query(Upload).filter(
            Upload.file_hash == file_hash,
            Upload.team_id == user["team_id"]
        ).first()

        if existing and existing.status == "completed":
            return {
                "upload_id": existing.id,
                "status": "existing",
                "total_tickets": existing.total_tickets,
                "filename": existing.filename,
                "message": "This file was already analyzed. Showing existing results."
            }

        # Save under a server-generated name: a client file name like "../../x.csv"
        # must never reach the filesystem, and two uploads must never overwrite each other
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")
        with open(filepath, "wb") as f:
            f.write(content)

        # Convert Excel to CSV
        # Create upload record immediately
        upload = Upload(
            filename=file.filename,
            status="saving",
            total_tickets=0,
            team_id=user['team_id'],
            user_id=user['user_id'],
            file_hash=file_hash
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        upload_id = upload.id

        # *** RETURN IMMEDIATELY — all processing in background ***
        background_tasks.add_task(process_upload_background, filepath, upload_id, user['team_id'])

        return {
            "upload_id": upload_id,
            "status": "saving",
            "total_tickets": 0,
            "filename": file.filename,
            "message": "Upload received. Processing in background."
        }
        

    except HTTPException:
        raise                      # deliberate 4xx answers (type, size) must reach the user as they are
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Upload failed: {str(e)}")
    finally:
        db.close()
def process_upload_background(filepath: str, upload_id: int, team_id: str):
    """Handles Excel conversion + ticket saving + ML all in background"""
    try:
        # Convert Excel to CSV if needed
        if filepath.endswith(('.xlsx', '.xls')):
            import pandas as pd
            df = pd.read_excel(filepath, header=0)
            csv_path = filepath.rsplit('.', 1)[0] + '.csv'
            df.to_csv(csv_path, index=False)
            os.remove(filepath)
            filepath = csv_path

        # Phase 1: Save tickets
        total_rows = save_tickets_only(filepath, upload_id, team_id)

        # Update status
        db = SessionLocal()
        try:
            upload = db.query(Upload).filter(Upload.id == upload_id).first()
            if upload:
                upload.status = "processing"
                upload.total_tickets = total_rows
                db.commit()
        finally:
            db.close()

        # Phase 2: ML analysis
        run_ml_in_background(filepath, upload_id)

    except Exception as e:
        print(f"Background error: {e}")
        db = SessionLocal()
        try:
            upload = db.query(Upload).filter(Upload.id == upload_id).first()
            if upload:
                upload.status = "failed"
                db.commit()
        finally:
            db.close()
@app.get("/api/uploads")
def get_uploads(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        uploads = db.query(Upload).filter(
            Upload.team_id == user["team_id"]
        ).order_by(Upload.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "filename": u.filename,
                "status": u.status,
                "total_tickets": u.total_tickets,
                "created_at": str(u.created_at),
                "automation_current_pct": u.automation_current_pct,
                "automation_potential_pct": u.automation_potential_pct,
                "avg_mttr_hours": u.avg_mttr_hours,
                "sla_compliance_pct": u.sla_compliance_pct,
                "total_clusters": u.total_clusters,
            }
            for u in uploads
        ]
    finally:
        db.close()

@app.get("/api/analysis/{upload_id}")
def get_analysis(upload_id: int, user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        upload = db.query(Upload).filter(
            Upload.id == upload_id,
            Upload.team_id == user["team_id"]
        ).first()
        if not upload:
            raise HTTPException(404, "Upload not found")

        
        already_automated = round((upload.automation_current_pct or 0) * (upload.total_tickets or 0) / 100)
        can_automate = round((upload.automation_potential_pct or 0) * (upload.total_tickets or 0) / 100)
        high_complexity = upload.high_complexity or 0

        return {
            "upload": {
                "id": upload.id,
                "filename": upload.filename,
                "status": upload.status,
                "total_tickets": upload.total_tickets,
                "created_at": str(upload.created_at),
            },
            "kpis": {
                "total_tickets": upload.total_tickets,
                "avg_mttr_hours": upload.avg_mttr_hours,
                "sla_compliance_pct": upload.sla_compliance_pct,
                "total_clusters": upload.total_clusters,
                "already_automated": already_automated,
                "already_automated_pct": round(already_automated / max(upload.total_tickets, 1) * 100, 1),
                "can_automate": can_automate,
                "can_automate_pct": round(can_automate / max(upload.total_tickets, 1) * 100, 1),
                "high_complexity": high_complexity,
            }
        }
    finally:
        db.close()

@app.get("/api/upload-status/{upload_id}")
def get_upload_status(upload_id: int, user: dict = Depends(require_upload_access)):
    """Poll this endpoint to check ML analysis progress"""
    db = SessionLocal()
    try:
        upload = db.query(Upload).filter(
            Upload.id == upload_id,
            Upload.team_id == user["team_id"]
        ).first()
        if not upload:
            raise HTTPException(404, "Upload not found")

        progress = {
            "saving": 10,
            "processing": 50,
            "completed": 100,
            "failed": 0
        }.get(upload.status, 0)

        return {
            "upload_id": upload_id,
            "status": upload.status,
            "progress": progress,
            "total_tickets": upload.total_tickets,
            "total_clusters": upload.total_clusters,
            "automation_potential_pct": upload.automation_potential_pct,
        }
    finally:
        db.close()

@app.get("/api/tickets")
def get_tickets(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.team_id == user["team_id"]).all()
        return tickets
    finally:
        db.close()

@app.get("/api/tickets/{upload_id}")
def get_upload_tickets(
    upload_id: int,
    user: dict = Depends(require_upload_access),
    skip: int = 0,
    limit: int = 50
):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"]
        ).offset(skip).limit(limit).all()
        return [
            {
                "id": t.ticket_number,
                "summary": t.short_description,
                "l1": t.l1_category,
                "l2": t.l2_subcategory,
                "score": t.automation_potential_score,
                "cluster": t.cluster_id,
                "l3": t.l3_automation_feasibility,
                "l4": t.l4_automation_type,
                "status": t.state,
                "mttr": t.mttr_hours,
            }
            for t in tickets
        ]
    finally:
        db.close()
@app.get("/api/me")
def get_me(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == user["user_id"]).first()
        return {
            "username": u.username,
            "email": u.email,
            "team_id": u.team_id,
            "role": u.role
        }
    finally:
        db.close()
@app.get("/api/tsne/{upload_id}")
def get_tsne(upload_id: int, user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.cluster_id != None
        ).limit(1000).all()
        if not tickets:
            return {"points": [], "total_clusters": 0}
        from collections import defaultdict
        import random
        random.seed(42)

        COLORS = ["#2563EB","#10B981","#F59E0B","#EF4444","#7C3AED",
                  "#EC4899","#06B6D4","#84CC16","#F97316","#8B5CF6"]

        clusters = defaultdict(list)
        for t in tickets:
            clusters[t.cluster_id].append(t)

        

        points = []
        for cid, cts in clusters.items():
            color = COLORS[abs(cid) % len(COLORS)]
            for t in cts[:30]:
                if t.tsne_x is not None and t.tsne_y is not None:
                    points.append({
                    "x": round(t.tsne_x, 2),
                    "y": round(t.tsne_y, 2),
                    "cluster": cid,
                    "color": color,
                    "description": (t.short_description or "")[:50]
                })
        

        return {"points": points, "total_clusters": len(clusters)}
    finally:
        db.close()


@app.get("/api/clusters/{upload_id}")
def get_clusters(upload_id: int, user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.cluster_id != None
        ).all()

        if not tickets:
            return {"clusters": [], "total_clustered": 0}

        from collections import defaultdict
        clusters = defaultdict(list)
        for t in tickets:
            clusters[t.cluster_id].append(t)

        AUTOMATION_MAP = {
            'host status': ('Auto-Remediation', 'Restart monitoring agent', 95),
            'volume capacity': ('Auto-Remediation', 'Disk cleanup script', 90),
            'vm down': ('Auto-Remediation', 'VM auto-restart runbook', 88),
            'disk': ('Auto-Remediation', 'I/O tuning script', 85),
            'memory': ('Auto-Remediation', 'Memory cleanup script', 85),
            'windows service': ('Script/Runbook', 'Service restart automation', 80),
            'vmware': ('Auto-Remediation', 'VMware alert suppression', 75),
            'cpu': ('Auto-Remediation', 'CPU threshold auto-scaling', 85),
            'password': ('Self-Service Portal', 'Password reset portal', 95),
            'backup': ('Script/Runbook', 'Backup retry automation', 80),
            'network': ('Monitoring Rule', 'Network alert tuning', 70),
            'certificate': ('Script/Runbook', 'Auto cert renewal', 90),
        }

        def get_automation_suggestion(descriptions):
            combined = ' '.join(descriptions[:10]).lower()
            for keyword, (solution, action, score) in AUTOMATION_MAP.items():
                if keyword in combined:
                    return solution, action, score
            return 'Manual Review', 'Requires human analysis', 30

        result = []
        sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)

        for cluster_id, cluster_tickets in sorted_clusters:
            if cluster_id == -1:
                continue
            
            descs = [t.short_description or '' for t in cluster_tickets]
            already_auto = sum(1 for t in cluster_tickets if t.is_already_automated)
            can_auto = sum(1 for t in cluster_tickets if t.can_be_automated)

            # Get actual top solution from ticket data
            from collections import Counter
            solutions = [t.aiops_solution_lever for t in cluster_tickets if t.aiops_solution_lever]
            if solutions:
                solution = Counter(solutions).most_common(1)[0][0]
            else:
                solution = 'Manual Review'

            # Map solution to action
            ACTION_MAP = {
                'Auto-Remediation': ('Auto-restart/cleanup scripts', 90),
                'Self-Service Portal': ('Password reset portal', 95),
                'Automation Tuning': ('Optimize existing automation', 85),
                'Existing Automation': ('Already automated', 100),
                'Script/Runbook': ('Runbook automation', 80),
                'Manual Process': ('Requires human review', 30),
                'RPA': ('RPA bot automation', 75),
            }
            action, score = ACTION_MAP.get(solution, ('Requires analysis', 50))

            # Get top keywords from descriptions
            words = ' '.join(descs).lower().split()
            from collections import Counter
            common = [w for w, _ in Counter(words).most_common(20)
                     if len(w) > 4 and w not in ['alert','status','on','the','and','for']][:5]

            result.append({
                "cluster_id": cluster_id,
                "ticket_count": len(cluster_tickets),
                "already_automated": already_auto,
                "can_automate": can_auto,
                "automation_pct": round(min(already_auto / len(cluster_tickets) * 100, 100), 1) if len(cluster_tickets) > 0 else 0,
                "can_automate_pct": round(min(can_auto / len(cluster_tickets) * 100, 100), 1) if len(cluster_tickets) > 0 else 0,
                "manual_only": max(0, len(cluster_tickets) - already_auto - can_auto),
                "solution": solution,
                "action": action,
                "confidence": score,
                "sample_descriptions": descs[:3],
                "keywords": common,
                "hours_saved": round(can_auto * EFFORT_MINUTES_PER_TICKET / 60, 0),  # over the whole dump
            })

        return {
            "clusters": result,
            "total_clustered": len(tickets),
            "total_clusters": len(result)
        }
    finally:
        db.close()
@app.get("/api/automation-summary/{upload_id}")
def get_automation_summary(upload_id: int, user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        base = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"]
        )

        total = base.count()
        already_auto = base.filter(Ticket.is_already_automated == True).count()
        can_auto = base.filter(Ticket.is_already_automated == False, Ticket.can_be_automated == True).count()
        manual = base.filter(Ticket.is_already_automated == False, Ticket.can_be_automated == False).count()
        by_solution = db.query(
            Ticket.aiops_solution_lever,
            func.count(Ticket.id)
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.aiops_solution_lever != None,
            Ticket.can_be_automated == True,
            Ticket.is_already_automated == False
        ).group_by(Ticket.aiops_solution_lever).order_by(func.count(Ticket.id).desc()).all()

        first_opened, last_opened = db.query(func.min(Ticket.opened), func.max(Ticket.opened)).filter(
            Ticket.upload_id == upload_id, Ticket.team_id == user["team_id"]).first()
        months = months_covered(first_opened, last_opened)

        return {
            "savings": automation_savings(can_auto, months),
            "total": total,
            "already_automated": already_auto,
            "already_automated_pct": round(already_auto / max(total, 1) * 100, 1),
            "can_automate": can_auto,
            "can_automate_pct": round(can_auto / max(total, 1) * 100, 1),
            "manual_only": manual,
            "manual_only_pct": round(manual / max(total, 1) * 100, 1),
            "by_solution": [
                {"solution": s[0] or "Unknown", "count": s[1],
                 "monthly_savings_inr": automation_savings(s[1], months)["monthly_savings_inr"]}
                for s in by_solution if s[0]
            ],
        }
    finally:
        db.close()
@app.get("/api/automation-opportunities/{upload_id}")
def get_automation_opportunities(
    upload_id: int,
    user: dict = Depends(require_upload_access),
    skip: int = 0,
    limit: int = 500,
    status: str = None,
    solution: str = None,
    domain: str = None,
):
    db = SessionLocal()
    try:
        query = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"]
        )
        
        # Apply filters
        if status and status != "All":
            if status == "Already Automated":
                query = query.filter(Ticket.is_already_automated == True)
            elif status == "Can Be Automated":
                query = query.filter(Ticket.is_already_automated == False, Ticket.can_be_automated == True)
            elif status == "Manual Only":
                query = query.filter(Ticket.is_already_automated == False, Ticket.can_be_automated == False)
        if solution and solution != "All":
            query = query.filter(Ticket.aiops_solution_lever == solution)
        if domain and domain != "All":
            query = query.filter(Ticket.l1_category == domain)
        
        total_filtered = query.count()
        tickets = query.order_by(Ticket.automation_potential_score.desc()).offset(skip).limit(limit).all()
        
        # Get dynamic domains (L1 categories)
        domains = db.query(Ticket.l1_category, func.count(Ticket.id)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.l1_category != None
        ).group_by(Ticket.l1_category).order_by(func.count(Ticket.id).desc()).limit(10).all()
        
        return {
            "tickets": [
                {
                    "id": t.ticket_number or str(t.id),
                    "short_description": t.short_description,
                    "assignment_group": t.assignment_group,
                    "l1_category": t.l1_category,
                    "l2_subcategory": t.l2_subcategory,
                    "aiops_automation_status": t.aiops_automation_status,
                    "aiops_solution_lever": t.aiops_solution_lever,
                    "aiops_keywords": t.aiops_keywords,
                    "aiops_additional_info": t.aiops_additional_info,
                    "resolved_by": t.resolved_by,
                    "mttr_hours": t.mttr_hours,
                    "automation_potential_score": t.automation_potential_score,
                }
                for t in tickets
            ],
            "total": total_filtered,
            "domains": [{"name": d[0] or "Other", "count": d[1]} for d in domains],
        }
    finally:
        db.close()

# Add this endpoint to main.py

@app.get("/api/bert-clusters/{upload_id}")
def get_bert_clusters(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get BERT cluster analysis with auto-generated names"""
    db = SessionLocal()
    try:
        from collections import Counter
        
        # Cluster name mappings based on keywords
        CLUSTER_NAMES = {
            10: "Batch Job Failures",
            2: "IMS PIN Reset",
            5: "Service Stopped Alerts",
            1: "External ITSM Tickets",
            9: "CPU High Alerts",
            4: "Host Unreachable",
            13: "VPN/Domain Password",
            8: "Tablespace Alerts",
            14: "GUI Password Reset",
            11: "IMS/RACF Password Reset",
            0: "General Alerts",
            3: "Memory Alerts",
            6: "Disk Space Alerts",
            7: "Application Errors",
            12: "Network Issues",
            15: "Backup Failures",
            16: "Database Issues",
            17: "Email/Exchange",
            18: "Security Alerts",
        }
        
        # Get clusters (excluding -1 which is noise)
        cluster_counts = db.query(
            Ticket.cluster_id,
            func.count(Ticket.id)
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
            Ticket.cluster_id != -1
        ).group_by(Ticket.cluster_id).order_by(func.count(Ticket.id).desc()).all()
        
        clusters = []
        total_clustered = 0
        
        for cluster_id, count in cluster_counts:
            total_clustered += count
            
            # Get sample tickets for keywords
            samples = db.query(Ticket.short_description).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == cluster_id
            ).limit(30).all()
            
            # Extract keywords
            all_text = ' '.join([s[0] or '' for s in samples]).lower()
            words = [w for w in all_text.split() if len(w) > 3 and w not in [
                'with', 'from', 'that', 'this', 'have', 'been', 'were', 'will',
                'service', 'the', 'and', 'for', 'are', 'was', 'not', 'has'
            ]]
            common_words = Counter(words).most_common(8)
            keywords = [w[0] for w in common_words]
            
            # Auto-generate name if not in mapping
            if cluster_id in CLUSTER_NAMES:
                name = CLUSTER_NAMES[cluster_id]
            else:
                # Generate from top keywords
                name = ' '.join(keywords[:2]).title() if keywords else f"Pattern {cluster_id}"
            
            # Get automation stats
            can_auto = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == cluster_id,
                Ticket.is_already_automated == False,
                Ticket.can_be_automated == True
            ).count()

            already_auto = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == cluster_id,
                Ticket.is_already_automated == True
            ).count()
            
            can_automate_pct = round((can_auto + already_auto) / count * 100) if count > 0 else 0
            
            # Get top solution
            top_solution = db.query(
                Ticket.aiops_solution_lever,
                func.count(Ticket.id)
            ).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == cluster_id,
                Ticket.aiops_solution_lever != None
            ).group_by(Ticket.aiops_solution_lever).order_by(func.count(Ticket.id).desc()).first()
            
            # Get sample descriptions
            sample_descs = [s[0][:80] if s[0] else '' for s in samples[:5]]
            
            clusters.append({
                "cluster_id": cluster_id,
                "name": name,
                "count": count,
                "keywords": keywords,
                "can_automate_pct": can_automate_pct,
                "top_solution": top_solution[0] if top_solution else "Manual Process",
                "samples": sample_descs,
            })
        
        return {
            "clusters": clusters,
            "total_clustered": total_clustered,
            "total_clusters": len(clusters),
        }
        
    finally:
        db.close()

# Add this endpoint to main.py


@app.get("/api/cxo-clusters/{upload_id}")
def get_cxo_clusters(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get CXO-friendly cluster analysis with business names and stories"""
    from cluster_classifier import classify_cluster, generate_cluster_story
    from collections import Counter, defaultdict
    
    db = SessionLocal()
    try:
        # Get upload info for dataset name
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        dataset_name = upload.filename.replace('.xlsx', '').replace('.csv', '').replace('_', ' ') if upload else f"Dataset {upload_id}"
        
        # Get all clustered tickets
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
            Ticket.cluster_id != -1
        ).all()
        
        if not tickets:
            return {"clusters": [], "summary": {}}
        
        opened = [t.opened for t in tickets if t.opened]
        months = months_covered(min(opened, default=None), max(opened, default=None))
        
        # Group by cluster
        clusters_data = {}
        for t in tickets:
            if t.cluster_id not in clusters_data:
                clusters_data[t.cluster_id] = []
            clusters_data[t.cluster_id].append(t)
        
        # Process each cluster (first pass - get base categories)
        cxo_clusters = []
        total_can_automate = 0
        total_hours_saved = 0
        
        # Keywords to ignore when finding unique identifiers
        IGNORE_WORDS = {
            'with', 'from', 'that', 'this', 'have', 'been', 'were', 'will', 'service',
            'the', 'and', 'for', 'are', 'was', 'not', 'has', 'alert', 'status',
            'password', 'reset', 'access', 'request', 'user', 'issue', 'error',
            'failed', 'failure', 'please', 'need', 'help', 'unable', 'cannot',
            'ticket', 'incident', 'problem', 'resolved', 'closed', 'open'
        }
        
        # System/Platform identifiers (WHAT system)
        SYSTEM_KEYWORDS = [
            'vmware', 'citrix', 'oracle', 'sql', 'mysql', 'postgres', 'linux', 'windows',
            'exchange', 'outlook', 'sharepoint', 'sap', 'salesforce', 'aws', 'azure',
            'ims', 'racf', 'vpn', 'gui', 'mainframe', 'mvs', 'unix', 'aix',
            'netbackup', 'veeam', 'commvault', 'cisco', 'juniper', 'f5',
            'tomcat', 'apache', 'nginx', 'iis', 'websphere', 'jboss'
        ]
        
        # Action/Problem context keywords (WHY/WHAT happened)
        ACTION_KEYWORDS = {
            # Problem states
            'unreachable': 'Unreachable',
            'timeout': 'Timeout',
            'down': 'Down',
            'stopped': 'Stopped',
            'hung': 'Hung',
            'slow': 'Slow',
            'degraded': 'Degraded',
            'offline': 'Offline',
            'disconnected': 'Disconnected',
            
            # Resource issues
            'cpu': 'CPU',
            'memory': 'Memory',
            'ram': 'Memory',
            'disk': 'Disk',
            'storage': 'Storage',
            'space': 'Space',
            'capacity': 'Capacity',
            'threshold': 'Threshold',
            'quota': 'Quota',
            
            # Actions/Events
            'snapshot': 'Snapshot',
            'backup': 'Backup',
            'restore': 'Restore',
            'replication': 'Replication',
            'sync': 'Sync',
            'migration': 'Migration',
            'failover': 'Failover',
            'restart': 'Restart',
            'reboot': 'Reboot',
            
            # Specific issues
            'certificate': 'Certificate',
            'ssl': 'SSL',
            'authentication': 'Auth',
            'permission': 'Permission',
            'locked': 'Locked',
            'expired': 'Expired',
            'tablespace': 'Tablespace',
            'listener': 'Listener',
            'connection': 'Connection',
            'latency': 'Latency',
            'packet': 'Packet Loss',
            'dns': 'DNS',
            'dhcp': 'DHCP',
            
            # Alert types
            'critical': 'Critical',
            'warning': 'Warning',
            'high': 'High',
            'alert': 'Alert',
        }
        
        for cluster_id, cluster_tickets in sorted(clusters_data.items(), key=lambda x: len(x[1]), reverse=True):
            # Get keywords from descriptions
            descs = [t.short_description or '' for t in cluster_tickets]
            all_text = ' '.join(descs[:50]).lower()
            all_words = all_text.split()
            word_counts = Counter(w for w in all_words if len(w) > 2 and w.lower() not in IGNORE_WORDS)
            keywords = [w for w, _ in word_counts.most_common(15)]
            
            # Extract system identifier
            system_identifier = None
            for sys_kw in SYSTEM_KEYWORDS:
                if sys_kw in all_text:
                    system_identifier = sys_kw.upper() if len(sys_kw) <= 4 else sys_kw.title()
                    break
            
            # Extract action/context identifier
            action_identifier = None
            for action_kw, action_label in ACTION_KEYWORDS.items():
                if action_kw in all_text:
                    action_identifier = action_label
                    break
            
            # Build unique identifier: System + Action
            if system_identifier and action_identifier:
                unique_identifier = f"{system_identifier} {action_identifier}"
            elif system_identifier:
                unique_identifier = system_identifier
            elif action_identifier:
                unique_identifier = action_identifier
            else:
                # Fallback: use top distinctive keyword
                for kw in keywords[:5]:
                    if len(kw) > 3 and kw not in IGNORE_WORDS:
                        unique_identifier = kw.title()
                        break
                else:
                    unique_identifier = None
            
            # Classify cluster
            category = classify_cluster(keywords, descs[:10])
            
            # Calculate stats
            ticket_count = len(cluster_tickets)
            can_automate = sum(1 for t in cluster_tickets if t.can_be_automated)
            already_automated = sum(1 for t in cluster_tickets if t.is_already_automated)
            hours_saved = can_automate * EFFORT_MINUTES_PER_TICKET / 60  # over the whole dump
            
            total_can_automate += can_automate
            total_hours_saved += hours_saved
            
            # Generate story
            story = generate_cluster_story(
                category=category,
                ticket_count=ticket_count,
                can_automate=can_automate,
                already_automated=already_automated,
                hours_saved=hours_saved,
                months=months
            )
            
            # Get sample tickets
            samples = [d[:100] for d in descs[:5]]
            
            cxo_clusters.append({
                "cluster_id": cluster_id,
                "base_name": category["name"],
                "unique_identifier": unique_identifier,
                "keywords": keywords[:8],
                "sample_tickets": samples,
                **story
            })
        
        # Second pass: Resolve duplicate names with smart context
        name_counts = Counter(c["base_name"] for c in cxo_clusters)
        
        # Track used full names to avoid duplicates
        used_names = defaultdict(int)
        
        for cluster in cxo_clusters:
            base_name = cluster["base_name"]
            identifier = cluster.get("unique_identifier")
            
            if name_counts[base_name] > 1 and identifier:
                # Build proposed name with identifier
                proposed_name = f"{base_name} - {identifier}"
            elif name_counts[base_name] > 1:
                # No identifier, use base name (will add number later)
                proposed_name = base_name
            else:
                # Unique base name
                proposed_name = base_name
            
            # Check if this exact name is already used
            used_names[proposed_name] += 1
            
            if used_names[proposed_name] > 1:
                # Add number suffix for true duplicates
                cluster["name"] = f"{proposed_name} #{used_names[proposed_name]}"
            else:
                cluster["name"] = proposed_name
            
            # Clean up temp fields
            if "base_name" in cluster:
                del cluster["base_name"]
            if "unique_identifier" in cluster:
                del cluster["unique_identifier"]
        
        # Summary stats
        total_tickets = len(tickets)
        cxo_savings = automation_savings(total_can_automate, months)
        summary = {
            "dataset_name": dataset_name,
            "total_tickets": total_tickets,
            "total_clusters": len(cxo_clusters),
            "total_can_automate": total_can_automate,
            "total_already_automated": sum(1 for t in tickets if t.is_already_automated),
            "total_hours_saved": round(total_hours_saved, 0),
            "total_monthly_savings_lakhs": round(cxo_savings["monthly_savings_inr"] / 100000, 1),
            "total_annual_savings_cr": round(cxo_savings["annual_savings_inr"] / 10000000, 2),
            "savings_assumptions": cxo_savings["assumptions"],
        }
        
        return {
            "clusters": cxo_clusters,
            "summary": summary,
        }
        
    finally:
        db.close()

# Add this endpoint to main.py

# REPLACE the existing get_dashboard_kpis function in main.py with this:

@app.get("/api/dashboard-kpis/{upload_id}")
def get_dashboard_kpis(upload_id: int, user: dict = Depends(require_upload_access)):
    """Get all dashboard KPIs for landing page"""
    from sqlalchemy import func, case, and_, or_
    from collections import Counter
    
    db = SessionLocal()
    try:
        # Base query
        base = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"]
        )
        
        total = base.count()
        if total == 0:
            return {"error": "No tickets found", "total": 0}
        
        # Get upload info
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        dataset_name = upload.filename.replace('.xlsx', '').replace('.csv', '').replace('_', ' ').replace('(1)', '').strip() if upload else f"Dataset {upload_id}"
        
        # ========== RECORD TYPE DETECTION ==========
        
        # Sample first 100 tickets to detect record type
        sample_tickets = base.limit(100).all()
        
        def detect_record_type(tickets):
            """Content-based detection saved at upload; else re-derived from ticket numbers (never the file name)."""
            import json
            path = f"outputs/upload_{upload_id}/dump_type.json"
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            from utils import detect_dump_content
            import pandas as pd
            numbers = [r[0] for r in db.query(Ticket.ticket_number).filter(
                Ticket.upload_id == upload_id, Ticket.team_id == user["team_id"]).all()]
            return detect_dump_content(pd.DataFrame({"number": numbers}))

        record_type = detect_record_type(sample_tickets)
        
        # ========== SECTION 1: AUTOMATION VALUE ==========
        
        already_automated = base.filter(Ticket.is_already_automated == True).count()
        can_automate = base.filter(Ticket.can_be_automated == True).count()
        
        # Fix: ensure no overlap
        manual_only = total - already_automated - can_automate
        if manual_only < 0:
            manual_only = 0
        
        first_opened, last_opened = db.query(func.min(Ticket.opened), func.max(Ticket.opened)).filter(
            Ticket.upload_id == upload_id, Ticket.team_id == user["team_id"]).first()
        savings = automation_savings(can_automate, months_covered(first_opened, last_opened))
        annual_savings = savings["annual_savings_inr"]
        
        automation_value = {
            "total_tickets": total,
            "already_automated": already_automated,
            "already_automated_pct": round(already_automated / total * 100, 1) if total > 0 else 0,
            "can_automate": can_automate,
            "can_automate_pct": round(can_automate / total * 100, 1) if total > 0 else 0,
            "manual_only": manual_only,
            "manual_only_pct": round(manual_only / total * 100, 1) if total > 0 else 0,
            "hours_saved_monthly": savings["hours_saved_monthly"],
            "monthly_savings_inr": savings["monthly_savings_inr"],
            "annual_savings_inr": round(annual_savings, 0),
            "savings_assumptions": savings["assumptions"],
            "annual_savings_lakhs": round(annual_savings / 100000, 1),
            "annual_savings_cr": round(annual_savings / 10000000, 2),
        }
        
        # ========== SECTION 2: OPERATIONAL EFFICIENCY ==========
        
        # Resolution time by automation status: one definition for every page (services/metrics.py)
        from services.metrics import mttr_by_status
        mttr = mttr_by_status(db, upload_id, user["team_id"])
        avg_mttr = mttr["overall"]["avg_hours"] or 0
        mttr_automated = mttr["automated"]["avg_hours"] or 0
        mttr_manual = mttr["human_handled"]["avg_hours"] or 0

        # Priority distribution, normalised to P1..P4 whatever the source format
        priority_level = priority_level_sql(Ticket.priority)
        priority_data = db.query(
            priority_level,
            func.count(Ticket.id)
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.priority != None
        ).group_by(priority_level).order_by(priority_level).all()

        high_priority_count = sum(c for lvl, c in priority_data if lvl in ("P1", "P2"))

        # SLA breaches among P1/P2 (P1 > 4h, P2 > 8h)
        sla_risk = db.query(func.count(Ticket.id)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            priority_level.in_(["P1", "P2"]),
            sla_breach_sql(Ticket.priority, Ticket.mttr_hours)
        ).scalar() or 0
        
        operational_efficiency = {
            "avg_mttr_hours": round(avg_mttr, 2),
            "mttr_automated_hours": round(mttr_automated, 2),
            "mttr_manual_hours": round(mttr_manual, 2),
            "mttr_by_status": mttr,
            "priority_distribution": [
                {"priority": p[0], "count": p[1]}
                for p in priority_data
            ],
            "high_priority_count": high_priority_count,
            "high_priority_pct": round(high_priority_count / total * 100, 1) if total > 0 else 0,
            "sla_breach_risk_count": sla_risk,
            # share of P1/P2 tickets that breached their SLA
            "sla_breach_risk_pct": round(sla_risk / high_priority_count * 100, 1) if high_priority_count > 0 else 0,
        }
        
        # ========== SECTION 3: TEAM PERFORMANCE ==========
        
        # Top 10 teams by volume
        team_volume = db.query(
            Ticket.assignment_group,
            func.count(Ticket.id).label('count'),
            func.avg(Ticket.mttr_hours).label('avg_mttr')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.assignment_group != None
        ).group_by(Ticket.assignment_group).order_by(func.count(Ticket.id).desc()).limit(10).all()
        
        # Team automation rates
        team_automation = db.query(
            Ticket.assignment_group,
            func.count(Ticket.id).label('total'),
            func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('automated')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.assignment_group != None
        ).group_by(Ticket.assignment_group).order_by(func.count(Ticket.id).desc()).limit(10).all()
        
        # Find best/worst teams
        best_mttr_team = None
        worst_mttr_team = None
        most_automated_team = None
        
        if team_volume:
            sorted_by_mttr = sorted([t for t in team_volume if t[2] and t[2] > 0], key=lambda x: x[2])
            if sorted_by_mttr:
                best_mttr_team = {"team": sorted_by_mttr[0][0][:30], "mttr": round(sorted_by_mttr[0][2], 1)}
                worst_mttr_team = {"team": sorted_by_mttr[-1][0][:30], "mttr": round(sorted_by_mttr[-1][2], 1)}
        
        if team_automation:
            sorted_by_auto = sorted(
                [{"team": t[0], "pct": round((t[2] or 0) / t[1] * 100, 1) if t[1] > 0 else 0} for t in team_automation],
                key=lambda x: x["pct"],
                reverse=True
            )
            if sorted_by_auto:
                most_automated_team = {"team": sorted_by_auto[0]["team"][:30], "pct": sorted_by_auto[0]["pct"]}
        
        team_performance = {
            "top_teams_by_volume": [
                {
                    "team": t[0][:40] if t[0] else "Unknown",
                    "count": t[1],
                    "avg_mttr": round(t[2], 2) if t[2] else 0
                }
                for t in team_volume
            ],
            "team_automation_rates": [
                {
                    "team": t[0][:40] if t[0] else "Unknown",
                    "total": t[1],
                    "automated": t[2] or 0,
                    "automation_pct": round((t[2] or 0) / t[1] * 100, 1) if t[1] > 0 else 0
                }
                for t in team_automation
            ],
            "best_mttr_team": best_mttr_team,
            "worst_mttr_team": worst_mttr_team,
            "most_automated_team": most_automated_team,
        }
        
        # ========== SECTION 4: CHANNEL ANALYSIS ==========
        
        # Tickets by channel
        channel_data = db.query(
            Ticket.channel,
            func.count(Ticket.id).label('count'),
            func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('automated')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.channel != None
        ).group_by(Ticket.channel).order_by(func.count(Ticket.id).desc()).all()
        
        # Top callers (repeat issues)
        caller_data = db.query(
            Ticket.caller_id,
            func.count(Ticket.id).label('count')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.caller_id != None
        ).group_by(Ticket.caller_id).order_by(func.count(Ticket.id).desc()).limit(10).all()
        
        # Find best automation channel
        best_auto_channel = None
        if channel_data:
            channels_with_auto = [
                {"channel": c[0], "pct": round((c[2] or 0) / c[1] * 100, 1) if c[1] > 0 else 0, "count": c[1]}
                for c in channel_data if c[1] > 100  # Only channels with >100 tickets
            ]
            if channels_with_auto:
                sorted_channels = sorted(channels_with_auto, key=lambda x: x["pct"], reverse=True)
                best_auto_channel = sorted_channels[0]
        
        channel_analysis = {
            "by_channel": [
                {
                    "channel": c[0] or "Unknown",
                    "count": c[1],
                    "automated": c[2] or 0,
                    "automation_pct": round((c[2] or 0) / c[1] * 100, 1) if c[1] > 0 else 0
                }
                for c in channel_data
            ],
            "top_callers": [
                {"caller": c[0][:30] if c[0] else "Unknown", "count": c[1]}
                for c in caller_data if c[1] > 1
            ],
            "best_auto_channel": best_auto_channel,
            "top_channel": {"channel": channel_data[0][0], "count": channel_data[0][1]} if channel_data else None,
        }
        
        # ========== SECTION 5: ML PATTERNS ==========
        
        # Cluster count
        cluster_count = db.query(func.count(func.distinct(Ticket.cluster_id))).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
            Ticket.cluster_id != -1
        ).scalar() or 0
        
        # Top cluster (most tickets)
        top_cluster = db.query(
            Ticket.cluster_id,
            func.count(Ticket.id).label('count')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
            Ticket.cluster_id != -1
        ).group_by(Ticket.cluster_id).order_by(func.count(Ticket.id).desc()).first()
        
        # Get sample description for top cluster
        top_cluster_info = None
        if top_cluster:
            sample_ticket = db.query(Ticket.short_description).filter(
                Ticket.upload_id == upload_id,
                Ticket.cluster_id == top_cluster[0]
            ).first()
            top_cluster_info = {
                "cluster_id": top_cluster[0],
                "count": top_cluster[1],
                "sample": sample_ticket[0][:50] if sample_ticket and sample_ticket[0] else "Unknown"
            }
        
        # Solution distribution
        solution_data = db.query(
            Ticket.aiops_solution_lever,
            func.count(Ticket.id).label('count')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.aiops_solution_lever != None,
            Ticket.can_be_automated == True,
            Ticket.is_already_automated == False
        ).group_by(Ticket.aiops_solution_lever).order_by(func.count(Ticket.id).desc()).all()
        
        # Average confidence score
        avg_confidence = db.query(func.avg(Ticket.automation_potential_score)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.automation_potential_score != None
        ).scalar() or 0
        
        ml_patterns = {
            "cluster_count": cluster_count,
            "top_cluster": top_cluster_info,
            "avg_confidence": round(avg_confidence, 1),
            "solution_distribution": [
                {
                    "solution": s[0] or "Unknown",
                    "count": s[1],
                    "pct": round(s[1] / total * 100, 1) if total > 0 else 0
                }
                for s in solution_data
            ],
        }
        
        # ========== SECTION 6: INFRASTRUCTURE ==========
        
        # Top configuration items
        ci_data = db.query(
            Ticket.configuration_item,
            func.count(Ticket.id).label('count')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.configuration_item != None
        ).group_by(Ticket.configuration_item).order_by(func.count(Ticket.id).desc()).limit(10).all()
        
        # Category distribution
        category_data = db.query(
            Ticket.l1_category,
            func.count(Ticket.id).label('count')
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.l1_category != None
        ).group_by(Ticket.l1_category).order_by(func.count(Ticket.id).desc()).all()
        
        infrastructure = {
            "top_configuration_items": [
                {"ci": c[0][:40] if c[0] else "Unknown", "count": c[1]}
                for c in ci_data
            ],
            "category_distribution": [
                {
                    "category": c[0] or "Unknown",
                    "count": c[1],
                    "pct": round(c[1] / total * 100, 1) if total > 0 else 0
                }
                for c in category_data
            ],
        }
        
        # ========== FINAL RESPONSE ==========
        
        return {
            "dataset_name": dataset_name,
            "upload_id": upload_id,
            "total_tickets": total,
            "last_analyzed": upload.created_at.isoformat() if upload and upload.created_at else None,
            "record_type": record_type,
            
            "automation_value": automation_value,
            "operational_efficiency": operational_efficiency,
            "team_performance": team_performance,
            "channel_analysis": channel_analysis,
            "ml_patterns": ml_patterns,
            "infrastructure": infrastructure,
        }
        
    finally:
        db.close()