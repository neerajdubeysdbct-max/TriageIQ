"""
chunk_processor.py
------------------
Universal ITSM ticket processor supporting:
- ServiceNow incident export (opened_at, resolved_at, sys_updated_by)
- Service request / task export (SCTASK, Created, Closed, Business duration)
- Incident export with resolve time in seconds (Created, Resolve time, Channel)
- Monitoring-driven export (ScienceLogic, Ignio, work notes)

Generates 7 AiOps columns for every ticket with FULL EXPLAINABILITY.
Saves training data automatically for continuous ML learning.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from models import SessionLocal, Ticket, Upload, TrainingData

CHUNK_SIZE = 5000

# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL COLUMN MAP (all dump formats)
# ═══════════════════════════════════════════════════════════════════════════════

COLUMN_MAP = {
    # Ticket number
    'number': 'ticket_number', 'Number': 'ticket_number',
    'incident_number': 'ticket_number', 'Incident number': 'ticket_number',
    'request_number': 'ticket_number',

    # Created / Opened
    'opened_at': 'created_at', 'Opened': 'created_at',
    'opened': 'created_at', 'Created': 'created_at',

    # Resolved / Closed
    'resolved_at': 'resolved_at', 'Resolved': 'resolved_at',
    'resolved': 'resolved_at', 'Closed': 'closed_at', 'closed_at': 'closed_at',

    # Duration (seconds)
    'calendar_duration': 'calendar_duration_sec',
    'business_duration': 'business_duration_sec',
    'Business duration': 'business_duration_sec',
    'Resolve time': 'resolve_time_sec',

    # Descriptions
    'short_description': 'short_description', 'Short description': 'short_description',
    'Short Description': 'short_description', 'description': 'description',
    'Description': 'description', 'close_notes': 'close_notes',
    'Close notes': 'close_notes', 'work_notes': 'work_notes',
    'Work notes': 'work_notes', 'Comments and Work notes': 'work_notes',
    'resolution_notes': 'resolution_notes', 'Resolution code': 'resolution_code',
    'Resolution notes': 'resolution_notes',

    # Category
    'category': 'category', 'Category': 'category',
    'subcategory': 'subcategory', 'Subcategory': 'subcategory',

    # Priority / State
    'priority': 'priority', 'Priority': 'priority',
    'state': 'state', 'State': 'state',

    # Assignment
    'assignment_group': 'assignment_group', 'Assignment group': 'assignment_group',
    'Assignment Group': 'assignment_group', 'assigned_to': 'assigned_to',
    'Assigned to': 'assigned_to', 'Assigned To': 'assigned_to',

    # Resolved by
    'resolved_by': 'resolved_by', 'Resolved by': 'resolved_by',
    'Resolved By': 'resolved_by', 'resolved_by_group': 'resolved_by_group',
    'Resolved by group': 'resolved_by_group',

    # System fields
    'sys_updated_by': 'sys_updated_by', 'sys_updated_on': 'sys_updated_on',

    # Channel
    'channel': 'channel', 'Channel': 'channel',
    'Origin': 'channel', 'contact_type': 'channel',

    # Caller / User
    'caller_id': 'caller_id', 'Caller': 'caller_id',
    'Affected user': 'affected_user', 'Requested for': 'requested_for',
    'User ID': 'user_id',

    # Reassignment / Reopen
    'reassignment_count': 'reassignment_count',
    'Reassignment count': 'reassignment_count',
    'reopen_count': 'reopen_count', 'Reopen count': 'reopen_count',

    # Config / Location
    'cmdb_ci': 'configuration_item', 'Configuration item': 'configuration_item',
    'location': 'location', 'Location': 'location',

    # Catalog / Service (Service Request dumps)
    'Catalog': 'catalog', 'catalog': 'catalog',
    'Item': 'catalog_item', 'item': 'catalog_item',
    'Service': 'service_name', 'service': 'service_name',
    'Service offering': 'service_offering', 'service_offering': 'service_offering',

    # Company / BU
    'business_service.company': 'company',
    'business_service.business_unit': 'business_unit',

    # Existing IA columns from labeled dumps
    'IA_type': 'existing_ia_type', 'IA_Category': 'existing_ia_category',
    'IA_SubCategory': 'existing_ia_subcategory', 'IA_Addnl Info': 'existing_ia_info',
    'IA_Keywords': 'existing_ia_keywords',

    # GSK / Custom ServiceNow fields
    'u_assignment_group': 'assignment_group',
    'u_configuration_item': 'configuration_item',
    'type': 'channel',
    'opened_at': 'created_at',
    'opened_for.u_country': 'location',
    'opened_for.location': 'location',
    'opened_for.u_business_unit': 'business_unit',
    'u_service': 'company',
    'u_service_offering': 'subcategory',
    'u_service.u_portfolio_service_group': 'category',
}


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION DETECTION SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

# Monitoring/Automation tools that CREATE tickets
MONITORING_TOOLS = [
    'sciencelogic', 'netcool', 'solarwinds', 'nagios', 'zabbix', 'datadog',
    'dynatrace', 'appdynamics', 'splunk', 'prometheus', 'grafana', 'pagerduty',
    'event management', 'monitoring', 'automated alert', 'system alert'
]

# Automation tools that RESOLVE tickets
AUTOMATION_RESOLVERS = [
    'automated id', 'ignio', 'autobot', 'automation', 'system', 'script',
    'integration', 'external tool', 'runbook', 'ansible', 'puppet', 'chef',
    'terraform', 'jenkins', 'scheduled task', 'cron', 'orchestration',
    'service account', 'svc-', 'bot', 'netcool', 'verizon proactive'
]

# Keywords in work_notes indicating automation attempted
AUTOMATION_WORK_PATTERNS = [
    'ignio is working', 'ignio integration user', 'automation executed',
    'script executed', 'runbook executed', 'auto-remediation', 'bot resolved',
    'automated action', 'self-healing', 'auto-scaling'
]

# Self-healing patterns in resolution notes
SELF_HEAL_PATTERNS = [
    'below threshold', 'under threshold', 'currently normal', 'back to normal',
    'resolved itself', 'no action required', 'auto-resolved', 'self-healed',
    'recovered', 'stabilized', 'normalized', 'cleared automatically',
    'alert cleared', 'no longer occurring', 'issue no longer exists'
]

# Patterns indicating human investigation was needed
HUMAN_INVESTIGATION_PATTERNS = [
    'investigated', 'analysis', 'root cause', 'troubleshoot', 'diagnosed',
    'found that', 'identified', 'checked with', 'confirmed with', 'spoke to',
    'called', 'escalated to', 'vendor involved', 'manual intervention',
    'restarted manually', 'applied fix', 'patched', 'reconfigured'
]

# Resolution codes indicating NOT real automation (exclude from analysis)
INVALID_RESOLUTION_CODES = [
    'cancelled', 'duplicate', 'not reproducible', 'user error', 'no fault found',
    'withdrawn', 'rejected', 'invalid'
]

# Channels indicating automation source
AUTO_CHANNELS = ['event management', 'monitoring', 'api', 'integration', 'automated']
MANUAL_CHANNELS = ['phone', 'walk-in', 'chat']

# Categories pre-labeled as automated
AUTO_CATEGORIES = ['automated alerts', 'monitoring event', 'event management']

# Automation levers for "Can Be Automated" detection
AUTOMATION_LEVERS = {
    'Password Reset': (
        ['password', 'reset password', 'forgot password', 'change password', 'pwd reset'],
        'Access Management', 'Self-Service Portal', 'Functional', 95
    ),
    'Account Unlock': (
        ['account locked', 'unlock account', 'locked out', 'account unlock'],
        'Access Management', 'Self-Service Portal', 'Functional', 95
    ),
    'User Provisioning': (
        ['create user', 'new user', 'onboard', 'provision user', 'new joiner'],
        'Access Management', 'RPA', 'Functional', 85
    ),
    'Access Request': (
        ['access request', 'request access', 'permission', 'role assignment', 'vpn access'],
        'Access Management', 'RPA', 'Functional', 80
    ),
    'VPN Issue': (
        ['vpn', 'virtual private network', 'remote access'],
        'Network', 'Script/Runbook', 'Technical', 75
    ),
    'Disk Space Alert': (
        ['disk space', 'disk full', 'low disk', 'storage full', 'high space', 'out of disk'],
        'Event Management', 'Auto-Remediation', 'Technical', 90
    ),
    'Memory Utilization': (
        ['memory', 'ram', 'high memory', 'memory utilization', 'out of memory'],
        'Event Management', 'Auto-Remediation', 'Technical', 85
    ),
    'CPU Alert': (
        ['cpu', 'processor', 'high cpu', 'cpu usage', 'cpu utilization', 'cpu exceeded'],
        'Event Management', 'Auto-Remediation', 'Technical', 85
    ),
    'Server Reboot': (
        ['reboot', 'restart server', 'server restart', 'bounce server'],
        'Infrastructure', 'Script/Runbook', 'Technical', 80
    ),
    'Service Restart': (
        ['service restart', 'restart service', 'service down', 'service not running'],
        'Infrastructure', 'Script/Runbook', 'Technical', 80
    ),
    'Backup/Restore': (
        ['backup', 'restore', 'recovery', 'data restore'],
        'Infrastructure', 'Script/Runbook', 'Technical', 70
    ),
    'Certificate Renewal': (
        ['certificate', 'ssl', 'cert expiry', 'certificate renewal', 'expired cert'],
        'Infrastructure', 'Auto-Remediation', 'Technical', 85
    ),
    'Log Cleanup': (
        ['log full', 'log cleanup', 'clear logs', 'log space'],
        'Event Management', 'Auto-Remediation', 'Technical', 85
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def safe_lower(value) -> str:
    """Safely convert to lowercase string"""
    if value is None:
        return ''
    return str(value).lower().strip()


def contains_any(text: str, patterns: List[str]) -> Tuple[bool, List[str]]:
    """Check if text contains any of the patterns, return matched patterns"""
    text = safe_lower(text)
    matched = [p for p in patterns if p in text]
    return len(matched) > 0, matched


def calculate_work_notes_complexity(work_notes: str) -> Tuple[str, int]:
    """Analyze work notes length and complexity"""
    length = len(work_notes or '')
    if length == 0:
        return 'empty', 0
    elif length < 50:
        return 'minimal', length
    elif length < 200:
        return 'short', length
    elif length < 500:
        return 'medium', length
    elif length < 1000:
        return 'detailed', length
    else:
        return 'extensive', length


# ═══════════════════════════════════════════════════════════════════════════════
# DUMP TYPE AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_dump_type(df: pd.DataFrame) -> dict:
    """Auto-detect dump format and record type from column names and ticket prefixes"""
    cols_lower = [c.lower().strip() for c in df.columns]

    # Record type from content (ticket-number prefixes + type-specific columns)
    from utils import detect_dump_content
    content = detect_dump_content(df)
    record_type = content.get("primary", "incident") if content["type"] != "unknown" else "incident"

    # Detect dump format
    if 'opened_at' in cols_lower and 'sys_updated_by' in cols_lower:
        dump_format = 'servicenow_incident'
        mttr_strategy = 'opened_resolved_timestamps'
    elif 'business duration' in cols_lower or 'business_duration' in cols_lower:
        dump_format = 'request_task'
        mttr_strategy = 'closed_created_timestamps'
    elif 'resolve time' in cols_lower:
        dump_format = 'resolve_seconds'
        mttr_strategy = 'resolve_time_seconds'
    else:
        dump_format = 'generic'
        mttr_strategy = 'opened_resolved_timestamps'

    return {'record_type': record_type, 'dump_format': dump_format, 'mttr_strategy': mttr_strategy,
            'content': content}


# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN MAPPING & CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_ticket_dates(values: pd.Series) -> pd.Series:
    """
    ISO timestamps (2025-08-12 10:00) are read as written; dayfirst would turn
    them into 8 December or NaT. Slash/dot formats from Indian exports
    (12/08/2025) are read day-first.
    """
    text = values.astype(str).str.strip()
    iso = text.str.match(r'^\d{4}-\d{2}-\d{2}')
    parsed = pd.to_datetime(text.where(iso), errors='coerce', format='ISO8601')
    if (~iso).any():
        parsed = parsed.fillna(pd.to_datetime(values.where(~iso), errors='coerce', dayfirst=True, format='mixed'))
    return parsed


def map_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    for col in ['created_at', 'resolved_at', 'closed_at']:
        if col in df.columns:
            df[col] = parse_ticket_dates(df[col])

    for col in ['short_description', 'description', 'resolution_notes', 'close_notes',
                'work_notes', 'assignment_group', 'assigned_to', 'resolved_by',
                'sys_updated_by', 'channel', 'resolution_code', 'affected_user']:
        if col not in df.columns:
            df[col] = ''
        else:
            df[col] = df[col].fillna('').astype(str).str.strip()

    for col in ['category', 'subcategory', 'priority', 'state']:
        if col not in df.columns:
            df[col] = 'Unknown'
        else:
            df[col] = df[col].fillna('Unknown').astype(str).str.strip()

    if 'reassignment_count' in df.columns:
        df['reassignment_count'] = pd.to_numeric(df['reassignment_count'], errors='coerce').fillna(0).astype(int)
    else:
        df['reassignment_count'] = 0

    if 'reopen_count' in df.columns:
        df['reopen_count'] = pd.to_numeric(df['reopen_count'], errors='coerce').fillna(0).astype(int)
    else:
        df['reopen_count'] = 0

    if 'ticket_number' not in df.columns:
        df['ticket_number'] = [f'TKT-{i}' for i in df.index]

    df = df.drop_duplicates(subset=['ticket_number'], keep='first')
    return df


def calculate_mttr(row: dict, mttr_strategy: str):
    try:
        if mttr_strategy == 'opened_resolved_timestamps':
            c, r = row.get('created_at'), row.get('resolved_at')
            if pd.notna(c) and pd.notna(r):
                diff = (pd.to_datetime(r) - pd.to_datetime(c)).total_seconds() / 3600
                return diff if 0 < diff < 8760 else None

        elif mttr_strategy == 'closed_created_timestamps':
            c, cl = row.get('created_at'), row.get('closed_at')
            if pd.notna(c) and pd.notna(cl):
                diff = (pd.to_datetime(cl) - pd.to_datetime(c)).total_seconds() / 3600
                return diff if 0 < diff < 8760 else None
            bd = row.get('business_duration_sec')
            if bd and float(str(bd).replace(',', '')) > 0:
                return float(str(bd).replace(',', '')) / 3600

        elif mttr_strategy == 'resolve_time_seconds':
            rt = row.get('resolve_time_sec')
            if rt:
                val = float(str(rt).replace(',', ''))
                return val / 3600 if val > 0 else None
    except:
        pass
    return None

def detect_automation_combined(row: dict) -> dict:
    """Wrapper that calls the new hybrid classifier"""
    try:
        from automation_classifier import classify_ticket
        return classify_ticket(row)
    except ImportError as e:
        print(f"Warning: Could not import automation_classifier: {e}")
        return {
            'is_already_automated': False,
            'can_be_automated': False,
            'automation_potential_score': 0.0,
            'aiops_automation_status': 'Manual Only',
            'aiops_solution_lever': 'Manual Process',
            'aiops_keywords': 'Classification error',
            'aiops_additional_info': str(e),
            'aiops_confidence': 0.0,
            'aiops_predicted_by': 'fallback',
            'aiops_type': 'Unknown',
            'aiops_category': row.get('category', 'Other'),
            'aiops_subcategory': row.get('subcategory', ''),
            'l1_category': row.get('category', 'Other'),
            'l2_subcategory': row.get('subcategory', ''),
            'l3_automation_feasibility': 'Unknown',
            'l4_automation_type': 'Manual',
        }
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: SAVE TICKETS (FAST PHASE)
# ═══════════════════════════════════════════════════════════════════════════════

def save_tickets_only(filepath: str, upload_id: int, team_id: str) -> int:
    total_rows = 0
    try:
        if filepath.endswith('.csv'):
            df_full = pd.read_csv(filepath, low_memory=False)
        else:
            df_full = pd.read_excel(filepath, header=0)

        dump_info = detect_dump_type(df_full)
        record_type = dump_info['record_type']
        mttr_strategy = dump_info['mttr_strategy']
        print(f"Detected: {dump_info['dump_format']} | {record_type} | MTTR: {mttr_strategy}")

        # Keep the detection evidence for the dashboard
        import json
        os.makedirs(f"outputs/upload_{upload_id}", exist_ok=True)
        with open(f"outputs/upload_{upload_id}/dump_type.json", "w", encoding="utf-8") as f:
            json.dump(dump_info["content"], f, indent=2)

        # Update record type on upload
        db = SessionLocal()
        try:
            upload = db.query(Upload).filter(Upload.id == upload_id).first()
            if upload:
                upload.record_type = record_type
                db.commit()
        finally:
            db.close()

        df_full = map_and_clean(df_full)
        chunks = [df_full[i:i+CHUNK_SIZE] for i in range(0, len(df_full), CHUNK_SIZE)]

        for i, chunk in enumerate(chunks):
            rows = _save_chunk(chunk, upload_id, team_id, record_type, mttr_strategy, i)
            total_rows += rows
            print(f"Chunk {i+1}/{len(chunks)}: {rows} rows (total: {total_rows})")

        _update_upload_metrics(upload_id)
        return total_rows

    except Exception as e:
        print(f"Error in save_tickets_only: {e}")
        import traceback; traceback.print_exc()
        return total_rows


def _save_chunk(df_chunk, upload_id, team_id, record_type, mttr_strategy, chunk_number):
    db = SessionLocal()
    try:
        tickets = []
        training_records = []

        for idx, row in df_chunk.iterrows():
            row_dict = row.to_dict()
            mttr_hours = calculate_mttr(row_dict, mttr_strategy)
            row_dict['mttr_hours'] = mttr_hours
            auto = detect_automation_combined(row_dict)

            ticket = Ticket(
                upload_id=upload_id, team_id=team_id, record_type=record_type,
                ticket_number=str(row_dict.get('ticket_number', f'TKT-{idx}'))[:50],
                category=str(row_dict.get('category', 'Unknown'))[:100],
                subcategory=str(row_dict.get('subcategory', ''))[:100],
                assignment_group=str(row_dict.get('assignment_group', 'Unknown'))[:200],
                assigned_to=str(row_dict.get('assigned_to', ''))[:200],
                resolved_by=str(row_dict.get('resolved_by', ''))[:200],
                resolved_by_group=str(row_dict.get('resolved_by_group', ''))[:200],
                sys_updated_by=str(row_dict.get('sys_updated_by', ''))[:200],
                priority=str(row_dict.get('priority', 'Unknown'))[:50],
                state=str(row_dict.get('state', ''))[:50],
                channel=str(row_dict.get('channel', ''))[:100],
                reassignment_count=int(row_dict.get('reassignment_count', 0) or 0),
                short_description=str(row_dict.get('short_description', ''))[:500],
                description=str(row_dict.get('description', ''))[:2000],
                resolution_notes=str(row_dict.get('resolution_notes', ''))[:500],
                close_notes=str(row_dict.get('close_notes', ''))[:500],
                work_notes=str(row_dict.get('work_notes', ''))[:1000],
                opened=row_dict.get('created_at') if pd.notna(row_dict.get('created_at')) else None,
                resolved=row_dict.get('resolved_at') if pd.notna(row_dict.get('resolved_at')) else None,
                closed=row_dict.get('closed_at') if pd.notna(row_dict.get('closed_at')) else None,
                mttr_hours=mttr_hours,
                business_duration=float(row_dict.get('business_duration_sec', 0) or 0) / 3600,
                calendar_duration=float(row_dict.get('calendar_duration_sec', 0) or 0) / 3600,
                configuration_item=str(row_dict.get('configuration_item', ''))[:200],
                catalog=str(row_dict.get('catalog', ''))[:200],
                catalog_item=str(row_dict.get('catalog_item', ''))[:200],
                service_name=str(row_dict.get('service_name', ''))[:200],
                service_offering=str(row_dict.get('service_offering', ''))[:200],
                location=str(row_dict.get('location', ''))[:200],
                company=str(row_dict.get('company', ''))[:200],
                business_unit=str(row_dict.get('business_unit', ''))[:200],
                caller_id=str(row_dict.get('caller_id', ''))[:200],
                requested_for=str(row_dict.get('requested_for', ''))[:200],
                # L1-L4
                l1_category=auto.get('l1_category', 'Other'),
                l2_subcategory=auto.get('l2_subcategory', ''),
                l3_automation_feasibility=auto.get('l3_automation_feasibility', 'Not Feasible'),
                l4_automation_type=auto.get('l4_automation_type', 'Manual'),
                # Automation flags
                is_already_automated=auto.get('is_already_automated', False),
                can_be_automated=auto.get('can_be_automated', False),
                automation_potential_score=auto.get('automation_potential_score', 0.0),
                # AiOps 7 columns
                aiops_type=auto.get('aiops_type'),
                aiops_category=auto.get('aiops_category'),
                aiops_subcategory=auto.get('aiops_subcategory'),
                aiops_additional_info=auto.get('aiops_additional_info'),
                aiops_keywords=auto.get('aiops_keywords'),
                aiops_automation_status=auto.get('aiops_automation_status', 'Manual Only'),
                aiops_solution_lever=auto.get('aiops_solution_lever', 'Manual'),
                aiops_confidence=auto.get('aiops_confidence', 0.0),
                aiops_predicted_by=auto.get('aiops_predicted_by', 'rule'),
            )
            tickets.append(ticket)

            # Save training data for future ML
            if auto.get('aiops_automation_status'):
                training_records.append(TrainingData(
                    upload_id=upload_id,
                    short_description=str(row_dict.get('short_description', ''))[:500],
                    category=str(row_dict.get('category', ''))[:100],
                    assignment_group=str(row_dict.get('assignment_group', ''))[:200],
                    channel=str(row_dict.get('channel', ''))[:100],
                    mttr_hours=mttr_hours,
                    reassignment_count=int(row_dict.get('reassignment_count', 0) or 0),
                    resolved_by=str(row_dict.get('resolved_by', ''))[:200],
                    sys_updated_by=str(row_dict.get('sys_updated_by', ''))[:200],
                    aiops_type=auto.get('aiops_type'),
                    aiops_category=auto.get('aiops_category'),
                    aiops_subcategory=auto.get('aiops_subcategory'),
                    aiops_automation_status=auto.get('aiops_automation_status'),
                    aiops_solution_lever=auto.get('aiops_solution_lever'),
                    label_source=auto.get('aiops_predicted_by', 'rule'),
                    is_verified=auto.get('aiops_predicted_by') == 'existing_label',
                ))

        db.bulk_save_objects(tickets)
        if training_records:
            db.bulk_save_objects(training_records)
        db.commit()
        return len(tickets)

    except Exception as e:
        db.rollback()
        print(f"Chunk {chunk_number} error: {e}")
        import traceback; traceback.print_exc()
        return 0
    finally:
        db.close()


def _update_upload_metrics(upload_id: int):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        total = len(tickets)
        if total == 0:
            return

        already_auto = sum(1 for t in tickets if t.is_already_automated)
        can_auto = sum(1 for t in tickets if t.can_be_automated)
        high_complex = sum(1 for t in tickets if t.aiops_automation_status == 'Manual Only')
        excluded = sum(1 for t in tickets if t.aiops_automation_status == 'Excluded')
        mttr_vals = [t.mttr_hours for t in tickets if t.mttr_hours and 0 < t.mttr_hours < 720]
        avg_mttr = float(np.mean(mttr_vals)) if mttr_vals else 0.0

        valid_total = total - excluded
        
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if upload:
            upload.automation_current_pct = round(already_auto / max(valid_total, 1) * 100, 1)
            upload.automation_potential_pct = round(can_auto / max(valid_total, 1) * 100, 1)
            upload.avg_mttr_hours = round(avg_mttr, 2)
            upload.high_complexity = high_complex
            upload.total_tickets = total
            db.commit()
            print(f"Metrics: {already_auto} automated ({upload.automation_current_pct}%), "
                  f"{can_auto} can automate ({upload.automation_potential_pct}%), "
                  f"{excluded} excluded, avg MTTR: {avg_mttr:.1f}h")
    except Exception as e:
        print(f"Metrics error: {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND ML PHASE
# ═══════════════════════════════════════════════════════════════════════════════

def run_ml_in_background(filepath: str, upload_id: int):
    db = SessionLocal()
    try:
        print(f"Starting ML analysis for upload {upload_id}...")
        from services.ml_analysis import run_complete_ml_analysis
        run_complete_ml_analysis(upload_id)

         # AIO Classification (Qwen LLM + BERT cluster propagation)
        try:
            from reprocess_aio import reprocess_upload
            reprocess_upload(upload_id)
            print(f"AIO classification done for upload {upload_id}")
        except Exception as e:
            print(f"AIO classification skipped: {e}")
       
        # Supervised L1/L2 category classifier (train_category_model.py); runs
        # first so the automation step can use its subcategories
        try:
            from services.category_scoring import apply_category_model
            apply_category_model(upload_id)
        except Exception as e:
            print(f"Category model skipped: {e}")

        # Supervised automation classifier (train_automation_model.py). When a
        # trained model exists it owns the automation flags.
        model_applied = False
        try:
            from services.automation_scoring import apply_automation_model
            model_applied = apply_automation_model(upload_id) is not None
        except Exception as e:
            print(f"Automation model skipped: {e}")

        # Fallback without a trained classifier: heuristic automation labels
        if not model_applied:
            try:
                from services.xgboost_trainer import generate_automation_labels
                import pandas as pd
                from models import Ticket
                tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
                if tickets:
                    tickets_df = pd.DataFrame([{
                        'short_description': t.short_description or '',
                        'mttr_hours': t.mttr_hours or 0,
                        'reassignment_count': t.reassignment_count or 0,
                        'reopen_count': t.reopen_count or 0,
                        'contact_type': t.contact_type or '',
                        'aiops_automation_status': t.aiops_automation_status or '',
                        'aiops_solution_lever': t.aiops_solution_lever or '',
                    } for t in tickets])
                    labels = generate_automation_labels(tickets_df)
                    for i, t in enumerate(tickets):
                        if not t.is_already_automated:
                            t.can_be_automated = bool(labels[i] == 1)
                    db.commit()
                    print("No trained automation model: heuristic labels applied")
            except Exception as e:
                print(f"Heuristic automation labels skipped: {e}")

        # Search index for the copilot (embeddings of description + closure notes)
        try:
            from services.rag.retrieval import index_upload
            index_upload(upload_id)
        except Exception as e:
            print(f"Copilot search index skipped: {e}")

        # X-Ray: surrogate XGBoost on operational features that explains the
        # automation decisions above (labels = the classifier's output)
        try:
            from services.xgboost_trainer import run_xgboost_xray
            db.expire_all()
            run_xgboost_xray(upload_id)
        except Exception as e:
            print(f"X-Ray surrogate skipped (non-critical): {e}")

        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if upload:
            upload.status = "completed"
            upload.completed_at = datetime.utcnow()
            db.commit()
        print(f"ML analysis completed for upload {upload_id}")

    except Exception as e:
        # Mark the failure honestly: a "completed" status here used to hide
        # crashed runs, and also blocked re-uploading the same file.
        import traceback
        traceback.print_exc()
        print(f"ML analysis failed: {e}")
        db.rollback()
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if upload:
            upload.status = "failed"
            upload.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

def process_csv_in_chunks(filepath, upload_id, team_id):
    total_rows = save_tickets_only(filepath, upload_id, team_id)
    run_ml_in_background(filepath, upload_id)
    return {"total_rows": total_rows, "status": "completed"}


def update_cluster_assignments(upload_id, cluster_labels):
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        for idx, ticket in enumerate(tickets):
            if idx < len(cluster_labels):
                ticket.cluster_id = int(cluster_labels[idx])
        db.commit()
    finally:
        db.close()