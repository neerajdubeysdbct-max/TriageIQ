from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    team_id = Column(String, index=True)
    role = Column(String, default="user")  # user, admin, viewer
    created_at = Column(DateTime, default=datetime.utcnow)

class Upload(Base):
    __tablename__ = "uploads"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    record_type = Column(String)  # incident or request
    status = Column(String)  # saving, processing, completed, failed
    total_tickets = Column(Integer, default=0)
    team_id = Column(String, index=True)
    user_id = Column(String)
    file_hash = Column(String)
    
    # Analysis results (computed after processing)
    automation_current_pct = Column(Float)   # Already automated %
    automation_potential_pct = Column(Float) # Can be automated %
    avg_mttr_hours = Column(Float)
    sla_compliance_pct = Column(Float)
    fcr_rate_pct = Column(Float)
    total_clusters = Column(Integer)
    high_complexity = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, index=True)
    team_id = Column(String, index=True)
    record_type = Column(String)  # incident or request
    
    # Core fields
    ticket_number = Column(String, index=True)
    category = Column(String, index=True)
    subcategory = Column(String)
    assignment_group = Column(String, index=True)
    assigned_to = Column(String)
    resolved_by = Column(String)
    resolved_by_group = Column(String)
    sys_updated_by = Column(String)
    priority = Column(String)
    urgency = Column(String)
    impact = Column(String)
    state = Column(String)
    channel = Column(String)  # Email, Event Management, Phone, Self-Service
    
    # Descriptions
    short_description = Column(Text)
    description = Column(Text)
    resolution_notes = Column(Text)
    work_notes = Column(Text)
    close_notes = Column(Text)
    
    # Dates
    opened = Column(DateTime)
    resolved = Column(DateTime)
    closed = Column(DateTime)
    
    # Performance metrics
    mttr_hours = Column(Float)
    business_duration = Column(Float)
    calendar_duration = Column(Float)
    reassignment_count = Column(Integer, default=0)
    reopen_count = Column(Integer, default=0)
    
    # Contact
    caller_id = Column(String)
    requested_for = Column(String)
    contact_type = Column(String)
    
    # Context
    configuration_item = Column(String)
    catalog = Column(String)
    catalog_item = Column(String)
    service_name = Column(String)
    service_offering = Column(String)
    location = Column(String)
    company = Column(String)
    business_unit = Column(String)
    
    # ===== ML-Generated Fields (L1-L4) =====
    l1_category = Column(String, index=True)
    l2_subcategory = Column(String)
    l3_automation_feasibility = Column(String)
    l4_automation_type = Column(String)
    
    l1_confidence = Column(Float)
    l2_confidence = Column(Float)
    l3_confidence = Column(Float)
    l4_confidence = Column(Float)
    
    # Automation detection
    is_already_automated = Column(Boolean, default=False)
    can_be_automated = Column(Boolean, default=False)
    automation_potential_score = Column(Float)

    # Human-in-the-Loop feedback
    model_status = Column(String)          # the automation classifier's own prediction
    label_source = Column(String)          # random_sample | uncertainty_queue | ticket_view
    human_override = Column(String)        # analyst label: "Already Automated", "Can Be Automated", "Manual Only"
    override_by = Column(String)           # username who corrected
    override_at = Column(DateTime)         # when corrected
    automation_confidence = Column(String)  # "High", "Medium" — which layer decided
    
    # Clustering
    cluster_id = Column(Integer)
    cluster_similarity = Column(Float)
    embedding_id = Column(String)
    
    # ===== AiOps Columns (7 columns - legacy) =====
    aiops_type = Column(String)              # Technical, Functional, Process
    aiops_category = Column(String)          # Event Management, Access Management, etc.
    aiops_subcategory = Column(String)       # Password Reset, Disk Space Alert, etc.
    aiops_additional_info = Column(Text)     # Human readable automation description
    aiops_keywords = Column(String)          # Search/tagging keywords
    aiops_automation_status = Column(String) # Already Automated, Can Be Automated, Manual Only
    aiops_solution_lever = Column(String)    # RPA, Script, Self-Service, Virtual Agent, Auto-Remediation
    
    # ML prediction confidence for AiOps columns
    aiops_confidence = Column(Float)         # 0-1, how confident ML is
    aiops_predicted_by = Column(String)      # rule, ml, hybrid
    tsne_x = Column(Float, nullable=True)
    tsne_y = Column(Float, nullable=True)
    
    # ===== NEW: AIO Classification Columns (ML-generated analyst-grade) =====
    # These replace the keyword-soup cluster names with business taxonomy
    aio_tower = Column(String, index=True)       # Application, Server, Network, End User, Database, Security, Cloud, AD, Collaboration, Storage
    aio_category = Column(String, index=True)     # Event Management, Access Management, Hardware Break-Fix, etc.
    aio_subcategory = Column(String)              # "Alerts: VM disk space", "Password Reset - SAP", etc.
    aio_detail = Column(String)
    aio_summary = Column(Text)                    # LLM-cleaned one-liner from noisy descriptions
    aio_confidence = Column(Float)                # 0-1, classification confidence
    aio_classified_by = Column(String)            # "bert_cluster", "llm_qwen", "supervised", "human"
    aio_needs_review = Column(Boolean, default=False)  # Flag for low-confidence tickets
    
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingData(Base):
    """Stores labeled tickets for ML training — includes AIO columns"""
    __tablename__ = "training_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, index=True)
    upload_id = Column(Integer, index=True)
    short_description = Column(Text)
    category = Column(String)
    assignment_group = Column(String)
    channel = Column(String)
    mttr_hours = Column(Float)
    reassignment_count = Column(Integer)
    resolved_by = Column(String)
    sys_updated_by = Column(String)
    
    # Labels (what we're training ML to predict)
    aiops_type = Column(String)
    aiops_category = Column(String)
    aiops_subcategory = Column(String)
    aiops_automation_status = Column(String)
    aiops_solution_lever = Column(String)
    
    # NEW: AIO labels for training the supervised classifier
    aio_tower = Column(String)
    aio_category = Column(String)
    aio_subcategory = Column(String)
    
    # Source of label
    label_source = Column(String)  # rule, human, existing_dump, bert_cluster, llm
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class MLModel(Base):
    """Track ML model versions and performance"""
    __tablename__ = "ml_models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String)
    version = Column(String)
    framework = Column(String)
    accuracy = Column(Float)
    f1_score = Column(Float)
    status = Column(String)  # active, training, deprecated
    model_path = Column(String)
    trained_on = Column(DateTime)
    deployed_on = Column(DateTime)
    training_samples = Column(Integer)
    metrics = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Security audit trail"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    team_id = Column(String, index=True)
    action = Column(String)
    resource = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    status = Column(String)
    error_message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# Database connection
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)