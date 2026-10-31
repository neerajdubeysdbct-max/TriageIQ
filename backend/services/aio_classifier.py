"""
aio_classifier.py (v3 — ML-First)
====================================
Pure ML classification engine for Ticket Intelligence.

Architecture:
  Layer 1: Qwen LLM (Primary)
    - Classify 3-5 sample tickets from each BERT cluster
    - 25 clusters × 5 samples = 125 LLM calls = ~3 minutes
    - Returns Tower, Category, SubCategory, Detail, Summary

  Layer 2: BERT Cluster Propagation
    - If Qwen classified 5 samples from Cluster 7 as "Server / Event Management / Disk Space"
    - All 487 tickets in Cluster 7 inherit that classification
    - Covers 95% of tickets instantly

  Layer 3: Heuristic Fallback (graceful degradation)
    - Only used when Ollama is DOWN and no cluster consensus exists
    - Keyword matching — same as before but LAST resort, not primary

  Layer 4: Cross-Upload Learning
    - Labels from upload 65 help classify upload 68
    - Stored in DB → next upload's clusters match against historical labels

Result: 125 LLM calls classify 99,000 tickets. Not 99K calls.

Produces 7 columns:
  1. Tower          — DYNAMIC (ML discovers, not hardcoded list)
  2. Category       — DYNAMIC
  3. SubCategory    — DYNAMIC
  4. Detail         — Sub Category 1 (deepest drill-down)
  5. Summary        — Crisp 1-liner from LLM or smart rule
  6. AutoStatus     — From existing rules engine (NEVER changed here)
  7. Action         — Meaningful text with tool name
"""

from config import LLM_MODEL, OLLAMA_URL
import re
import json
import random
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
import traceback

# ============================================================
# QWEN LLM CLASSIFICATION (Layer 1)
# ============================================================

CLASSIFICATION_PROMPT = """You are an ITSM ticket classifier for enterprise IT operations.

IMPORTANT RULES:
- This is a {record_type} dump. If it's an incident dump, NEVER use "Service Request" as category.
- Ignore ticket template names like "Self Service Incident", "<Company> Self Service", "Service Desk Template" — these are NOT the actual issue.
- Classify based on the ACTUAL problem described, not the ticket template.
- If the description is just a template name with no real issue, classify based on assignment_group and resolution_notes.
- Never use "Unknown" as subcategory — always extract something meaningful from the available fields.

Classify this ServiceNow ticket into exactly these fields:
- tower: The broad technology area (e.g. Server, Network, End User, Application, Database, Security, Cloud, Active Directory, Collaboration, Storage/Backup, SAP, Oracle, or any other appropriate tower)
- category: The issue type (e.g. Event Management, Access Management, Hardware Break-Fix, Software Issue, Network Connectivity, Batch/Job Failure, Service Request, Backup/Restore, Performance Issue, Certificate Management, Email/Messaging, or any other appropriate category)
- subcategory: The specific problem (e.g. Disk Space, CPU Utilization, Password Reset, Application Down, Host Down, Account Unlock, VPN Connectivity, etc.)
- detail: The deepest detail (e.g. Volume Capacity /opt/IBM, SAP GUI/SSO, Laptop WiFi, Router Port 443, etc.)
- summary: A crisp 1-line summary (max 80 chars) describing what happened and how it was resolved. NOT a copy of the description. Write like an analyst.

TICKET:
  Description: {description}
  Assignment Group: {assignment_group}
  Category: {sn_category}
  Subcategory: {sn_subcategory}
  Channel: {channel}
  Resolution: {resolution_notes}
  Resolved By: {resolved_by}
  MTTR: {mttr} hours
  Catalog: {catalog}
  Catalog Item: {catalog_item}
  Service: {service_name}

Respond ONLY with valid JSON, no other text:
{{"tower": "...", "category": "...", "subcategory": "...", "detail": "...", "summary": "..."}}"""


def classify_with_llm(ticket_info: Dict) -> Optional[Dict]:
    """
    Classify a single ticket using Qwen LLM via Ollama.
    Returns None if Ollama is unavailable.
    """
    try:
        import requests
        prompt = CLASSIFICATION_PROMPT.format(
            record_type=ticket_info.get('record_type', 'incident'),
            description=ticket_info.get('short_description', '')[:300],
            assignment_group=ticket_info.get('assignment_group', ''),
            sn_category=ticket_info.get('category', ''),
            sn_subcategory=ticket_info.get('subcategory', ''),
            channel=ticket_info.get('channel', ''),
            resolution_notes=(ticket_info.get('resolution_notes', '') or '')[:200],
            resolved_by=ticket_info.get('resolved_by', ''),
            mttr=ticket_info.get('mttr_hours', ''),
            catalog=ticket_info.get('catalog', ''),
            catalog_item=ticket_info.get('catalog_item', ''),
            service_name=ticket_info.get('service_name', ''),
        )

        response = requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': LLM_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.1, 'num_predict': 200}
            },
            timeout=30
        )

        if response.status_code != 200:
            return None

        text = response.json().get('response', '').strip()

        # Extract JSON from response
        json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Validate required fields exist
            if all(k in result for k in ['tower', 'category', 'subcategory']):
                return {
                    'tower': str(result.get('tower', '')).strip(),
                    'category': str(result.get('category', '')).strip(),
                    'subcategory': str(result.get('subcategory', '')).strip(),
                    'detail': str(result.get('detail', '')).strip(),
                    'summary': str(result.get('summary', '')).strip()[:150],
                }
        return None
    except Exception:
        return None


def check_ollama_available() -> bool:
    """Check if Ollama is running and qwen2.5 is available."""
    try:
        import requests
        r = requests.get(f'{OLLAMA_URL}/api/tags', timeout=3)
        if r.status_code == 200:
            models = [m.get('name', '') for m in r.json().get('models', [])]
            return any('qwen' in m for m in models)
    except Exception:
        pass
    return False


def classify_cluster_samples_with_llm(
    cluster_tickets: Dict[int, List],
    samples_per_cluster: int = 5
) -> Dict[int, Dict]:
    """
    Classify representative samples from each cluster using Qwen.
    Returns: {cluster_id: {tower, category, subcategory, detail, summary}}
    
    Smart sampling: pick diverse tickets (different assignment groups,
    different descriptions) from each cluster.
    """
    if not check_ollama_available():
        print("  Ollama not available — skipping LLM classification")
        return {}

    cluster_labels = {}
    total_calls = 0
    total_clusters = len(cluster_tickets)

    print(f"  Classifying {total_clusters} clusters with Qwen LLM...")

    for cid, tickets in cluster_tickets.items():
        if cid == -1:
            continue

        # Smart sampling: pick diverse tickets
        samples = _smart_sample(tickets, samples_per_cluster)

        # Classify each sample
        results = []
        for ticket_info in samples:
            result = classify_with_llm(ticket_info)
            total_calls += 1
            if result:
                results.append(result)

        if not results:
            continue

        # Majority vote across samples
        towers = [r['tower'] for r in results if r['tower']]
        categories = [r['category'] for r in results if r['category']]
        subcategories = [r['subcategory'] for r in results if r['subcategory']]
        details = [r['detail'] for r in results if r['detail']]
        summaries = [r['summary'] for r in results if r['summary']]

        cluster_labels[cid] = {
            'tower': Counter(towers).most_common(1)[0][0] if towers else '',
            'category': Counter(categories).most_common(1)[0][0] if categories else '',
            'subcategory': Counter(subcategories).most_common(1)[0][0] if subcategories else '',
            'detail': Counter(details).most_common(1)[0][0] if details else '',
            'summary_template': summaries[0] if summaries else '',
            'confidence': len(results) / samples_per_cluster,
            'classified_by': 'llm_qwen',
        }

    print(f"  LLM classified {len(cluster_labels)}/{total_clusters} clusters ({total_calls} API calls)")
    return cluster_labels


def _smart_sample(tickets: List, n: int) -> List[Dict]:
    """Pick diverse samples from a cluster — different groups, different descriptions."""
    if len(tickets) <= n:
        return [_ticket_to_dict(t) for t in tickets]

    # Group by assignment_group for diversity
    by_group = defaultdict(list)
    for t in tickets:
        group = _get_field(t, 'assignment_group') or 'unknown'
        by_group[group].append(t)

    samples = []
    groups = list(by_group.keys())
    random.shuffle(groups)

    # Pick one from each group first
    for group in groups:
        if len(samples) >= n:
            break
        ticket = random.choice(by_group[group])
        samples.append(_ticket_to_dict(ticket))

    # Fill remaining with random picks
    remaining = [t for t in tickets if t not in samples]
    while len(samples) < n and remaining:
        ticket = random.choice(remaining)
        remaining.remove(ticket)
        samples.append(_ticket_to_dict(ticket))

    return samples


def _ticket_to_dict(ticket) -> Dict:
    """Convert ticket (SQLAlchemy or dict) to dict for LLM prompt."""
    fields = ['short_description', 'assignment_group', 'category', 'subcategory',
              'channel', 'resolution_notes', 'resolved_by', 'mttr_hours',
              'aiops_automation_status', 'aiops_solution_lever', 'record_type',
              'catalog', 'catalog_item', 'service_name', 'service_offering']
    result = {}
    for f in fields:
        result[f] = _get_field(ticket, f)
    result['mttr_hours'] = _get_float(ticket, 'mttr_hours')
    return result


# ============================================================
# APPLICATION / SERVER EXTRACTION (used by heuristic fallback)
# ============================================================

KNOWN_APPS = {
    'sap': 'SAP', 'oracle': 'Oracle', 'salesforce': 'Salesforce',
    'servicenow': 'ServiceNow', 'jira': 'JIRA', 'confluence': 'Confluence',
    'sharepoint': 'SharePoint', 'teams': 'Teams', 'outlook': 'Outlook',
    'exchange': 'Exchange', 'citrix': 'Citrix', 'vmware': 'VMware',
    'tableau': 'Tableau', 'power bi': 'Power BI', 'powerbi': 'Power BI',
    'peoplesoft': 'PeopleSoft', 'siebel': 'Siebel', 'hyperion': 'Hyperion',
    'cognos': 'Cognos', 'informatica': 'Informatica', 'urochart': 'UROchart',
    'sql server': 'SQL Server', 'mssql': 'SQL Server', 'mysql': 'MySQL',
    'postgres': 'PostgreSQL', 'mongodb': 'MongoDB', 'db2': 'DB2',
    'hana': 'SAP HANA', 'apache': 'Apache', 'nginx': 'Nginx', 'iis': 'IIS',
    'tomcat': 'Tomcat', 'websphere': 'WebSphere', 'weblogic': 'WebLogic',
    'netcool': 'Netcool', 'sciencelogic': 'ScienceLogic', 'ignio': 'Ignio',
    'solarwinds': 'SolarWinds', 'splunk': 'Splunk', 'ansible': 'Ansible',
    'zoom': 'Zoom', 'webex': 'WebEx', 'slack': 'Slack',
    'o365': 'Office 365', 'office 365': 'Office 365',
    'windows': 'Windows', 'linux': 'Linux', 'unix': 'Unix', 'aix': 'AIX',
}

SERVER_PATTERN = re.compile(r'\b([a-zA-Z]{2,8}[\-_]?[a-zA-Z]*\d{1,4}[a-zA-Z]*\d*)\b')

def extract_app_name(text: str, group: str = '') -> Optional[str]:
    combined = f"{text} {group}".lower()
    for kw, name in KNOWN_APPS.items():
        if kw in combined:
            return name
    return None

def extract_server_name(text: str) -> Optional[str]:
    match = SERVER_PATTERN.search(text or '')
    if match:
        name = match.group(1)
        skip = {'error', 'issue', 'alert', 'event', 'admin', 'medium', 'minor', 'major', 'normal'}
        if len(name) >= 5 and name.lower() not in skip:
            return name
    return None


# ============================================================
# NOISE DETECTION
# ============================================================

NOISE_PATTERNS = [
    (r'closure.*duplicate|duplicate.*closure|duplicate.*ticket', 'Duplicate Ticket Closure'),
    (r'resolution.*email|details.*email|resolution.*in.*email', 'Resolution via Email'),
    (r'no action.*required|no.*action.*needed', 'No Action Required'),
    (r'false.*alert|false.*alarm|false.*positive', 'False Alert'),
    (r'test.*ticket|testing.*only|please.*ignore', 'Test Ticket'),
    (r'auto.*close|auto.*closed|auto.*resolved', 'Auto-Closed'),
]

def detect_noise(desc: str, resolution: str = '') -> Optional[str]:
    combined = f"{desc} {resolution}".lower()
    for pattern, label in NOISE_PATTERNS:
        if re.search(pattern, combined):
            return label
    return None


# ============================================================
# HEURISTIC FALLBACK (Layer 3 — only when LLM + cluster both fail)
# ============================================================

def heuristic_classify(ticket) -> Dict:
    """
    Keyword-based classification. ONLY used when:
    - Ollama is not running (LLM unavailable)
    - Ticket has no cluster (cluster_id = -1)
    - No historical labels exist

    Returns same structure as LLM classification.
    """
    desc = _get_field(ticket, 'short_description').lower()
    group = _get_field(ticket, 'assignment_group').lower()
    sn_cat = _get_field(ticket, 'category').lower()
    sn_subcat = _get_field(ticket, 'subcategory').lower()
    channel = _get_field(ticket, 'channel').lower()
    resolution = _get_field(ticket, 'resolution_notes').lower()
    combined = f"{desc} {sn_cat} {sn_subcat} {resolution}"

    # --- Noise check ---
    noise = detect_noise(desc, resolution)
    if noise:
        return {'tower': 'Other', 'category': 'Duplicate/Cancelled', 'subcategory': noise,
                'detail': '', 'summary': noise, 'confidence': 0.9}

    # --- Tower from assignment group ---
    tower = _tower_from_group(group)
    if not tower:
        tower = _tower_from_keywords(desc, sn_cat, channel)

    # --- Category ---
    category = _category_from_keywords(combined, channel, sn_cat)

    # --- SubCategory ---
    subcategory, detail = _subcategory_from_keywords(combined, category, group, desc)

    return {
        'tower': tower, 'category': category, 'subcategory': subcategory,
        'detail': detail, 'summary': '', 'confidence': 0.4,
    }


def _tower_from_group(group: str) -> Optional[str]:
    """Extract tower from assignment group name."""
    tower_map = {
        'server': 'Server', 'compute': 'Server', 'wintel': 'Server', 'unix': 'Server',
        'linux': 'Server', 'vmware': 'Server', 'infra': 'Server', 'hosting': 'Server',
        'nw': 'Network', 'network': 'Network', 'cisco': 'Network', 'telecom': 'Network',
        'wan': 'Network', 'verizon': 'Network', 'firewall': 'Network',
        'desktop': 'End User', 'deskside': 'End User', 'workplace': 'End User',
        'helpdesk': 'End User', 'service desk': 'End User',
        'app': 'Application', 'application': 'Application', 'middleware': 'Application',
        'dba': 'Database', 'database': 'Database',
        'security': 'Security', 'soc': 'Security',
        'cloud': 'Cloud', 'aws': 'Cloud', 'azure': 'Cloud',
        'ad': 'Active Directory', 'identity': 'Active Directory',
        'exchange': 'Collaboration', 'o365': 'Collaboration', 'messaging': 'Collaboration',
        'storage': 'Storage/Backup', 'backup': 'Storage/Backup', 'san': 'Storage/Backup',
        'sap': 'SAP', 'oracle': 'Oracle', 'netcool': 'Server', 'monitoring': 'Server',
    }
    for keyword, t in tower_map.items():
        if keyword in group:
            return t
    return None


def _tower_from_keywords(desc: str, sn_cat: str, channel: str) -> str:
    """Extract tower from description keywords."""
    combined = f"{desc} {sn_cat}"
    checks = [
        (['server', 'vm ', 'host', 'linux', 'windows server', 'unix', 'esxi'], 'Server'),
        (['network', 'router', 'switch', 'vpn', 'dns', 'firewall', 'connectivity', 'internet', 'wifi'], 'Network'),
        (['laptop', 'desktop', 'printer', 'workstation', 'machine not', 'machine is not'], 'End User'),
        (['database', 'db ', 'sql', 'tablespace', 'oracle db'], 'Database'),
        (['email', 'exchange', 'outlook', 'teams', 'sharepoint', 'o365'], 'Collaboration'),
        (['storage', 'san', 'nas', 'backup', 'restore', 'tape'], 'Storage/Backup'),
        (['security', 'antivirus', 'malware', 'vulnerability'], 'Security'),
        (['cloud', 'aws', 'azure', 'gcp', 'kubernetes'], 'Cloud'),
        (['active directory', 'ldap', 'domain controller', 'ad account'], 'Active Directory'),
        (['application', 'app ', 'software', 'citrix', 'sap', 'erp'], 'Application'),
    ]
    for keywords, tower in checks:
        if any(k in combined for k in keywords):
            return tower

    if any(k in channel for k in ['event', 'monitoring']):
        return 'Server'
    return 'Other'


def _category_from_keywords(combined: str, channel: str, sn_cat: str) -> str:
    """Extract category from keywords."""
    checks = [
        (['alert', 'threshold', 'monitoring', 'high space', 'high cpu', 'high memory',
          'disk space', 'host down', 'service down', 'ping', 'unreachable'], 'Event Management'),
        (['password', 'reset', 'unlock', 'locked out', 'access request', 'login fail',
          'gui/sso', 'account lock', 'id creation'], 'Access Management'),
        (['hardware', 'physical', 'replace', 'faulty', 'power supply', 'fan', 'loud noise'], 'Hardware Break-Fix'),
        (['network', 'connectivity', 'internet', 'wifi', 'unable to connect'], 'Network Connectivity'),
        (['batch', 'job fail', 'etl', 'cron', 'scheduled job'], 'Batch/Job Failure'),
        (['backup fail', 'restore', 'recovery'], 'Backup/Restore'),
        (['certificate', 'ssl', 'cert expir'], 'Certificate Management'),
        (['email', 'mailbox', 'exchange', 'outlook', 'mail flow'], 'Email/Messaging'),
        (['patch', 'update', 'hotfix'], 'Patch/Update'),
    ]
    for keywords, cat in checks:
        if any(k in combined for k in keywords):
            return cat

    if any(k in channel for k in ['event', 'monitoring']):
        return 'Event Management'

    # Use ServiceNow category if meaningful
    if sn_cat and sn_cat.strip() not in ['unknown', '', 'none', 'other']:
        return sn_cat.strip().title()

    if any(k in combined for k in ['error', 'crash', 'not working', 'slow', 'down']):
        return 'Software Issue'

    return 'Unclassified'


def _subcategory_from_keywords(combined: str, category: str, group: str, desc: str) -> Tuple[str, str]:
    """Extract subcategory and detail from keywords."""
    desc_l = desc.lower() if desc else ''

    # Event Management subcategories
    if category == 'Event Management':
        if any(k in combined for k in ['disk space', 'high space', 'space used', 'volume']):
            return 'Disk Space', extract_server_name(desc) or extract_app_name(desc, group) or ''
        if any(k in combined for k in ['cpu', 'processor']):
            return 'CPU Utilization', extract_server_name(desc) or ''
        if any(k in combined for k in ['memory', 'ram', 'swap']):
            return 'Memory Utilization', extract_server_name(desc) or ''
        if any(k in combined for k in ['host down', 'server down', 'unreachable', 'ping']):
            return 'Host Down', extract_server_name(desc) or ''
        if any(k in combined for k in ['interface', 'port down', 'link down']):
            return 'Network Device Alert', ''
        return 'General Monitoring', extract_server_name(desc) or ''

    # Access Management subcategories
    if category == 'Access Management':
        if any(k in combined for k in ['password', 'pwd', 'gui/sso']):
            app = extract_app_name(desc, group)
            return 'Password Reset', app or 'General'
        if any(k in combined for k in ['unlock', 'locked']):
            return 'Account Unlock', extract_app_name(desc, group) or ''
        if any(k in combined for k in ['access', 'permission', 'role']):
            return 'Access Request', extract_app_name(desc, group) or ''
        if any(k in combined for k in ['create', 'new user', 'onboard', 'provision']):
            return 'Account Creation', ''
        return 'General Access', ''

    # Software Issue subcategories
    if category == 'Software Issue':
        app = extract_app_name(desc, group)
        if any(k in desc_l for k in ['down', 'not working', 'not responding', 'unavailable']):
            return 'Application Down', app or ''
        if any(k in desc_l for k in ['error', 'fail', 'crash', 'exception']):
            return 'Application Error', app or ''
        if any(k in desc_l for k in ['slow', 'performance', 'timeout']):
            return 'Application Slow', app or ''
        if any(k in desc_l for k in ['export', 'import', 'report']):
            return 'Export/Import Issue', app or ''
        if app:
            return f'{app} Issue', ''
        return 'General Software', ''

    # Network
    if category == 'Network Connectivity':
        if any(k in combined for k in ['vpn', 'remote access']):
            return 'VPN Connectivity', ''
        if any(k in combined for k in ['internet', 'wifi', 'browse']):
            return 'Internet Access', ''
        if any(k in combined for k in ['dns', 'resolve']):
            return 'DNS Issue', ''
        return 'General Connectivity', ''

    # Hardware
    if category == 'Hardware Break-Fix':
        if any(k in combined for k in ['disk fail', 'hard drive', 'raid']):
            return 'Disk Failure', ''
        if any(k in combined for k in ['fan', 'loud noise', 'temperature']):
            return 'Fan/Cooling', ''
        if any(k in combined for k in ['machine', 'not working', 'laptop', 'desktop']):
            return 'Machine Not Working', 'Laptop/Desktop' if 'laptop' in combined else ''
        return 'General Hardware', ''

    # Fallback: extract app name or use SN subcategory
    app = extract_app_name(desc, group)
    if app:
        return f'{app} Issue', ''
    return 'Unclassified', 'Needs Review'


# ============================================================
# MEANINGFUL ACTION TEXT
# ============================================================

RESOLVER_TOOLS = {
    'netcool': 'Netcool', 'ignio': 'Ignio', 'sciencelogic': 'ScienceLogic',
    'verizon proactive': 'Verizon Proactive', 'ansible': 'Ansible',
    'puppet': 'Puppet', 'jenkins': 'Jenkins', 'autobot': 'AutoBot',
    'solarwinds': 'SolarWinds',
}

def build_meaningful_action(status: str, lever: str, resolved_by: str,
                            group: str, subcat: str, desc: str) -> str:
    """Build meaningful action text with tool/context name."""
    resolved_l = (resolved_by or '').lower()
    group_l = (group or '').lower()
    desc_l = (desc or '').lower()

    if status == 'Already Automated':
        for kw, tool in RESOLVER_TOOLS.items():
            if kw in resolved_l or kw in group_l:
                return f"Existing Automation — {tool}"
        if 'auto' in resolved_l or 'system' in resolved_l:
            return "Existing Automation — System Auto-Resolve"
        return "Existing Automation"

    if status == 'Excluded':
        return "N/A — Excluded"

    if status in ['Manual Only', 'Manual']:
        if any(k in desc_l for k in ['vendor', 'external']):
            return "Manual — Vendor Investigation Required"
        if any(k in desc_l for k in ['hardware', 'physical', 'replace']):
            return "Manual — Physical Intervention Required"
        if any(k in desc_l for k in ['complex', 'escalat', 'troubleshoot']):
            return "Manual — Complex Investigation"
        return "Manual Process"

    # Can Be Automated
    if lever == 'Self-Service Portal':
        if 'password' in desc_l: return "Self-Service Portal — Password Reset"
        if 'unlock' in desc_l: return "Self-Service Portal — Account Unlock"
        if 'access' in desc_l: return "Self-Service Portal — Access Request"
        return "Self-Service Portal"
    if lever == 'Auto-Remediation':
        if 'disk' in desc_l or 'space' in desc_l: return "Auto-Remediation — Disk Cleanup Script"
        if 'cpu' in desc_l: return "Auto-Remediation — Process Management"
        if 'memory' in desc_l: return "Auto-Remediation — Memory Management"
        if 'service' in desc_l or 'restart' in desc_l: return "Auto-Remediation — Service Restart"
        return "Auto-Remediation — Monitoring Script"
    if lever == 'Script/Runbook':
        if 'restart' in desc_l or 'reboot' in desc_l: return "Script/Runbook — Service Restart"
        if 'backup' in desc_l: return "Script/Runbook — Backup Recovery"
        if 'certificate' in desc_l: return "Script/Runbook — Certificate Renewal"
        return "Script/Runbook"
    if lever == 'RPA': return "RPA — UI Automation"
    if lever == 'Automation Tuning':
        for kw, tool in RESOLVER_TOOLS.items():
            if kw in group_l: return f"Automation Tuning — {tool}"
        return "Automation Tuning"
    return lever or "Script/Runbook"


# ============================================================
# EVIDENCE BUILDER
# ============================================================

def build_evidence_line(ticket) -> str:
    """Build 1-line evidence string for table display."""
    parts = []
    resolved_l = _get_field(ticket, 'resolved_by').lower()
    channel_l = _get_field(ticket, 'channel').lower()
    mttr = _get_float(ticket, 'mttr_hours')
    reassign = int(_get_float(ticket, 'reassignment_count'))

    for kw, tool in RESOLVER_TOOLS.items():
        if kw in resolved_l:
            parts.append(f"Resolved by {tool}")
            break
    else:
        rb = _get_field(ticket, 'resolved_by')
        if rb and ' ' in rb.strip():
            parts.append(f"Resolved by {rb.strip().split()[0]}")

    if mttr and mttr > 0:
        parts.append(f"{mttr*60:.0f}min" if mttr < 1 else f"{mttr:.1f}h")

    if 'event' in channel_l or 'monitoring' in channel_l: parts.append("Event channel")
    elif 'phone' in channel_l: parts.append("Phone")
    elif 'email' in channel_l: parts.append("Email")
    elif 'portal' in channel_l or 'self-service' in channel_l: parts.append("Portal")

    if reassign == 0: parts.append("0 reassign")
    elif reassign >= 3: parts.append(f"{reassign} reassign")

    return " | ".join(parts) if parts else "—"


# ============================================================
# NEEDS REVIEW LOGIC
# ============================================================

def should_flag_for_review(subcategory: str, tower_conf: float, cat_conf: float) -> bool:
    """Only flag genuinely uncertain tickets. Target: 5-10%, not 46%."""
    if subcategory == 'Unclassified':
        return True
    if tower_conf < 0.3 and cat_conf < 0.3:
        return True
    return False


# ============================================================
# MAIN: CLASSIFY BATCH (orchestrator)
# ============================================================

def classify_batch(
    tickets,
    embeddings=None,
    cluster_labels=None,
    cluster_label_map=None
) -> List[Dict]:
    """
    Classify a batch of tickets using ML-first approach.

    Flow:
      1. Group tickets by cluster
      2. Classify cluster samples with Qwen LLM
      3. Propagate LLM labels to all cluster members
      4. Heuristic fallback for unclustered/unclassified tickets
    """
    total = len(tickets)
    print(f"\n  AIO Classification: {total} tickets")

    # --- Step 1: Group tickets by cluster ---
    cluster_tickets = defaultdict(list)
    ticket_cluster_map = {}

    for i, ticket in enumerate(tickets):
        cid = -1
        if cluster_labels is not None and i < len(cluster_labels):
            cid = int(cluster_labels[i])
        cluster_tickets[cid].append(ticket)
        ticket_cluster_map[id(ticket)] = cid

    clustered = sum(len(v) for k, v in cluster_tickets.items() if k != -1)
    unclustered = len(cluster_tickets.get(-1, []))
    print(f"  Clustered: {clustered} ({len(cluster_tickets)-1} clusters) | Unclustered: {unclustered}")

    # --- Step 2: LLM classification of cluster samples ---
    llm_labels = classify_cluster_samples_with_llm(cluster_tickets, samples_per_cluster=5)
    llm_classified = len(llm_labels)

    # --- Step 3: Build consensus (LLM + heuristic for non-LLM clusters) ---
    # For clusters LLM couldn't classify, build heuristic consensus
    heuristic_consensus = {}
    for cid, tickets_in_cluster in cluster_tickets.items():
        if cid == -1 or cid in llm_labels:
            continue
        # Heuristic consensus for this cluster
        tower_votes = Counter()
        cat_votes = Counter()
        subcat_votes = Counter()
        for t in tickets_in_cluster[:20]:  # Sample max 20 for speed
            h = heuristic_classify(t)
            tower_votes[h['tower']] += 1
            cat_votes[h['category']] += 1
            subcat_votes[h['subcategory']] += 1

        if tower_votes:
            best_tower = tower_votes.most_common(1)[0]
            best_cat = cat_votes.most_common(1)[0]
            best_subcat = subcat_votes.most_common(1)[0]
            total_votes = sum(tower_votes.values())
            if best_tower[1] / total_votes >= 0.5:
                heuristic_consensus[cid] = {
                    'tower': best_tower[0],
                    'category': best_cat[0],
                    'subcategory': best_subcat[0],
                    'detail': '',
                    'summary_template': '',
                    'confidence': best_tower[1] / total_votes * 0.7,
                    'classified_by': 'bert_cluster',
                }

    # Merge: LLM labels take priority
    all_cluster_labels = {**heuristic_consensus, **llm_labels}

    llm_count = 0
    cluster_count = 0
    heuristic_count = 0

    # --- Step 4: Classify each ticket ---
    results = []
    for i, ticket in enumerate(tickets):
        cid = ticket_cluster_map.get(id(ticket), -1)

        # Get classification source
        if cid in llm_labels:
            # LLM classified this cluster
            cl = llm_labels[cid]
            classified_by = 'llm_qwen'
            confidence = cl.get('confidence', 0.8)
            llm_count += 1
        elif cid in all_cluster_labels:
            # Heuristic consensus for this cluster
            cl = all_cluster_labels[cid]
            classified_by = 'bert_cluster'
            confidence = cl.get('confidence', 0.5)
            cluster_count += 1
        else:
            # No cluster or no consensus — individual heuristic
            cl = heuristic_classify(ticket)
            classified_by = 'heuristic'
            confidence = cl.get('confidence', 0.4)
            heuristic_count += 1

        desc = _get_field(ticket, 'short_description')
        group = _get_field(ticket, 'assignment_group')
        resolved_by = _get_field(ticket, 'resolved_by')
        aiops_status = _get_field(ticket, 'aiops_automation_status') or 'Manual'
        solution_lever = _get_field(ticket, 'aiops_solution_lever') or ''

        # Use rules engine confidence (better than our heuristic confidence)
        existing_conf = _get_float(ticket, 'automation_potential_score')
        if existing_conf > 0:
            confidence = existing_conf / 100.0

        # Enrich detail with per-ticket specifics (server name, app name)
        detail = cl.get('detail', '')
        if not detail:
            app = extract_app_name(desc, group)
            if app:
                detail = app
            else:
                server = extract_server_name(desc)
                if server:
                    detail = server

        # Automation status mapping (from rules engine — NEVER changed)
        if aiops_status == 'Already Automated':
            auto_potential = 'Already Automated'
        elif aiops_status in ['Can Be Automated', 'can_be_automated']:
            auto_potential = 'Can Be Automated'
        elif aiops_status == 'Excluded':
            auto_potential = 'Excluded'
        else:
            auto_potential = 'Manual'

        tower = cl.get('tower', 'Other')
        category = cl.get('category', 'Unclassified')
        subcategory = cl.get('subcategory', 'Unclassified')

        # Noise check (per ticket — duplicates, test tickets)
        noise = detect_noise(desc, _get_field(ticket, 'resolution_notes'))
        if noise:
            category = 'Duplicate/Cancelled'
            subcategory = noise
            detail = ''

        tower_conf = confidence if classified_by == 'llm_qwen' else 0.5
        cat_conf = confidence if classified_by == 'llm_qwen' else 0.5

        results.append({
            'aio_tower': tower,
            'aio_category': category,
            'aio_subcategory': subcategory,
            'aio_detail': detail,
            'aio_confidence': confidence,
            'aio_classified_by': classified_by,
            'aio_needs_review': should_flag_for_review(subcategory, tower_conf, cat_conf),
            'auto_potential': auto_potential,
            'action': build_meaningful_action(aiops_status, solution_lever, resolved_by, group, subcategory, desc),
            'evidence': build_evidence_line(ticket),
        })

    print(f"\n  Classification results:")
    print(f"    LLM (Qwen):        {llm_count} tickets ({llm_count/total*100:.1f}%)")
    print(f"    BERT Cluster:      {cluster_count} tickets ({cluster_count/total*100:.1f}%)")
    print(f"    Heuristic fallback: {heuristic_count} tickets ({heuristic_count/total*100:.1f}%)")

    return results


# ============================================================
# HELPERS
# ============================================================

def _get_field(ticket, field_name) -> str:
    if isinstance(ticket, dict):
        return str(ticket.get(field_name, '') or '')
    return str(getattr(ticket, field_name, '') or '')

def _get_float(ticket, field_name) -> float:
    if isinstance(ticket, dict):
        val = ticket.get(field_name, 0)
    else:
        val = getattr(ticket, field_name, 0)
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0