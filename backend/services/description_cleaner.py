"""
description_cleaner.py (v2)
============================
Cleans ServiceNow ticket descriptions and generates crisp summaries.

Two modes:
  1. rule_clean()  — Fast regex stripping (instant, all tickets)
  2. llm_summary() — Qwen LLM generates analyst-quality 1-liner (cluster samples)

The summary should read like an analyst wrote it:
  BAD:  "RESOLUTION (DETAILS IN EMAIL) - ITS..."
  BAD:  "b3vpromgapp04 - High space used (95%) for /opt/IBM/WebSphere..."
  GOOD: "Disk space at 95% on b3vpromgapp04 /opt/IBM — Netcool auto-cleared in 12 min"
  GOOD: "Password reset for SAP GUI user x601052 — resolved via phone in 5 min"
"""

from config import LLM_MODEL, OLLAMA_URL
import re
from typing import List
from typing import Optional

# ============================================================
# COMPILED REGEX PATTERNS (loaded once at module level)
# ============================================================

# Email headers and forwarded chains
EMAIL_HEADER_RE = re.compile(
    r'(from:|to:|cc:|bcc:|sent:|date:|subject:|importance:).*',
    re.IGNORECASE
)
FORWARDED_RE = re.compile(
    r'(-{2,}\s*(forwarded|original)\s*message\s*-{2,}|'
    r'begin\s*forwarded\s*message)',
    re.IGNORECASE
)

# Email signatures and sign-offs
SIGNATURE_RE = re.compile(
    r'(regards|thanks|thank you|sincerely|best|cheers|warm regards|kind regards|'
    r'sent from my|get outlook|confidential|disclaimer|this email|'
    r'this message|privileged|intended recipient|if you are not|'
    r'please consider the environment).*',
    re.IGNORECASE | re.DOTALL
)

# Phone numbers, email addresses
PHONE_RE = re.compile(r'(\+?\d[\d\-\.\s]{7,}\d)')
EMAIL_ADDR_RE = re.compile(r'[\w\.\-]+@[\w\.\-]+\.\w+')

# URLs
URL_RE = re.compile(r'https?://\S+|www\.\S+')

# HTML tags
HTML_RE = re.compile(r'<[^>]+>')

# ServiceNow system lines
SN_SYSTEM_RE = re.compile(
    r'(work notes|additional comments|sys_id|ref:|ticket ref|'
    r'incident number|request number|task number|'
    r'created by|updated by|assigned to|resolved by|'
    r'priority:?\s*(p[1-4]|[1-4]\s*-)|'
    r'state:?\s*(new|active|resolved|closed|pending)|'
    r'category:?\s*\w)',
    re.IGNORECASE
)

# Greeting lines
GREETING_RE = re.compile(
    r'^\s*(hi|hello|dear|good morning|good afternoon|good evening|hey|greetings)\b.*$',
    re.IGNORECASE | re.MULTILINE
)

# Blank lines and excessive whitespace
MULTI_NEWLINE_RE = re.compile(r'\n\s*\n+')
MULTI_SPACE_RE = re.compile(r'  +')

# Common noise phrases that add no value
NOISE_PHRASES = [
    'please see below', 'as discussed', 'as per our conversation',
    'kindly', 'please find', 'attached herewith', 'fyi',
    'for your information', 'please note', 'note:', 'update:',
    'action required', 'urgent', 'asap', 'eod', 'cob',
    'please do the needful', 'revert back', 'please revert',
]

# Resolution boilerplate
RESOLUTION_NOISE = [
    'issue resolved', 'problem resolved', 'ticket resolved',
    'closing ticket', 'closing the ticket', 'ticket closed',
    'resolved and closing', 'issue fixed', 'problem fixed',
]


# ============================================================
# RULE-BASED CLEANING (fast, all tickets)
# ============================================================

def rule_clean(text: str, max_length: int = 200) -> str:
    """
    Fast rule-based cleaning. Strips email noise, signatures,
    system lines, HTML, URLs. Returns clean 1-liner.
    
    Used for ALL tickets as baseline summary.
    """
    if not text or len(text.strip()) < 3:
        return ''

    t = str(text)

    # Strip HTML
    t = HTML_RE.sub(' ', t)

    # Strip URLs
    t = URL_RE.sub('', t)

    # Strip email headers and forwarded chains
    t = EMAIL_HEADER_RE.sub('', t)
    t = FORWARDED_RE.sub('', t)

    # Strip signatures (everything after signature line)
    t = SIGNATURE_RE.sub('', t)

    # Strip phone numbers and email addresses
    t = PHONE_RE.sub('', t)
    t = EMAIL_ADDR_RE.sub('', t)

    # Strip ServiceNow system lines
    t = SN_SYSTEM_RE.sub('', t)

    # Strip greetings
    t = GREETING_RE.sub('', t)

    # Strip noise phrases
    t_lower = t.lower()
    for phrase in NOISE_PHRASES:
        t_lower_check = t.lower()
        idx = t_lower_check.find(phrase)
        if idx != -1:
            t = t[:idx] + t[idx + len(phrase):]

    # Clean whitespace
    t = MULTI_NEWLINE_RE.sub(' ', t)
    t = MULTI_SPACE_RE.sub(' ', t)
    t = t.strip()

    # Remove leading/trailing special chars
    t = re.sub(r'^[\s\-\*\#\:\.]+', '', t)
    t = re.sub(r'[\s\-\*\#\:\.]+$', '', t)

    # Truncate to max length at word boundary
    if len(t) > max_length:
        t = t[:max_length].rsplit(' ', 1)[0] + '...'

    return t


def clean_for_embedding(text: str, max_length: int = 500) -> str:
    """
    Lighter cleaning for BERT embeddings — keeps more content
    but removes HTML, URLs, email noise.
    """
    if not text:
        return ''

    t = str(text)
    t = HTML_RE.sub(' ', t)
    t = URL_RE.sub('', t)
    t = EMAIL_HEADER_RE.sub('', t)
    t = FORWARDED_RE.sub('', t)
    t = SIGNATURE_RE.sub('', t)
    t = PHONE_RE.sub('', t)
    t = EMAIL_ADDR_RE.sub('', t)
    t = MULTI_NEWLINE_RE.sub(' ', t)
    t = MULTI_SPACE_RE.sub(' ', t)
    t = t.strip()

    if len(t) > max_length:
        t = t[:max_length]

    return t


# ============================================================
# SMART SUMMARY BUILDER (no LLM — uses ticket data)
# ============================================================

def build_smart_summary(
    short_desc: str,
    resolution_notes: str = '',
    resolved_by: str = '',
    mttr_hours: float = None,
    assignment_group: str = '',
    channel: str = '',
    aio_subcategory: str = '',
) -> str:
    """
    Build analyst-quality summary from ticket data.
    Combines key facts into a crisp 1-liner.
    
    Examples:
      "Disk space at 95% on b3vpromgapp04 — Netcool auto-cleared in 12 min"
      "Password reset for SAP GUI user x601052 — resolved via phone in 5 min"
      "UROchart application down — Citrix team investigated, 8.2h resolution"
    """
    # Clean the description first
    desc = rule_clean(short_desc, max_length=100)
    if not desc:
        desc = rule_clean(resolution_notes, max_length=80) if resolution_notes else 'No description'

    # Build resolution context
    resolution_parts = []

    # Who resolved
    resolved_l = (resolved_by or '').lower()
    resolver_names = {
        'netcool': 'Netcool', 'ignio': 'Ignio', 'sciencelogic': 'ScienceLogic',
        'verizon': 'Verizon', 'ansible': 'Ansible', 'autobot': 'AutoBot',
    }
    resolver = None
    for kw, name in resolver_names.items():
        if kw in resolved_l:
            resolver = name
            break

    if resolver:
        resolution_parts.append(f"{resolver} resolved")
    elif resolved_by and ' ' in (resolved_by or '').strip():
        # Human name
        first_name = resolved_by.strip().split()[0]
        resolution_parts.append(f"resolved by {first_name}")

    # How fast
    if mttr_hours is not None and mttr_hours > 0:
        if mttr_hours < 1:
            resolution_parts.append(f"{mttr_hours * 60:.0f} min")
        else:
            resolution_parts.append(f"{mttr_hours:.1f}h")

    # Channel context
    channel_l = (channel or '').lower()
    if 'event' in channel_l or 'monitoring' in channel_l:
        resolution_parts.append("event-triggered")
    elif 'phone' in channel_l:
        resolution_parts.append("via phone")
    elif 'portal' in channel_l or 'self-service' in channel_l:
        resolution_parts.append("via portal")

    # Combine
    if resolution_parts:
        resolution_str = " | ".join(resolution_parts)
        summary = f"{desc} — {resolution_str}"
    else:
        summary = desc

    # Cap at 150 chars
    if len(summary) > 150:
        summary = summary[:147] + '...'

    return summary


# ============================================================
# LLM SUMMARY (for cluster samples — Qwen via Ollama)
# ============================================================

SUMMARY_PROMPT = """Summarize this IT support ticket in exactly ONE line (max 80 characters).
Write like an IT analyst — factual, concise, no fluff.

Description: {description}
Resolution: {resolution}
Assignment Group: {group}

Examples of good summaries:
- "Disk space 95% on server xyz01 /opt — auto-cleared by Netcool"
- "SAP password reset for user x601052 — completed in 5 min"
- "Exchange mailbox full for John Smith — increased quota"

Your 1-line summary:"""


def llm_summary(
    short_desc: str,
    resolution_notes: str = '',
    assignment_group: str = '',
) -> Optional[str]:
    """
    Generate analyst-quality summary using Qwen LLM.
    Returns None if Ollama unavailable.
    """
    try:
        import requests

        prompt = SUMMARY_PROMPT.format(
            description=(short_desc or '')[:200],
            resolution=(resolution_notes or '')[:200],
            group=assignment_group or '',
        )

        response = requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': LLM_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.1, 'num_predict': 100}
            },
            timeout=15
        )

        if response.status_code == 200:
            text = response.json().get('response', '').strip()
            # Clean up common LLM artifacts
            text = re.sub(r'^[\"\'\-\*\s]+', '', text)
            text = re.sub(r'[\"\'\s]+$', '', text)
            # Remove "Summary:" prefix if LLM adds it
            text = re.sub(r'^(summary|answer|response|here)[\s:]+', '', text, flags=re.IGNORECASE)
            if len(text) > 5 and len(text) < 200:
                return text[:150]

    except Exception:
        pass

    return None


def batch_llm_summaries(tickets_info: list, batch_size: int = 5) -> dict:
    """
    Generate LLM summaries for a batch of tickets.
    Returns: {index: summary_text}
    """
    results = {}
    for i, info in enumerate(tickets_info):
        if i >= batch_size * 20:  # Cap at 100 LLM calls for summaries
            break
        summary = llm_summary(
            info.get('short_description', ''),
            info.get('resolution_notes', ''),
            info.get('assignment_group', ''),
        )
        if summary:
            results[i] = summary
    return results


# ============================================================
# MAIN: GENERATE SUMMARIES FOR BATCH
# ============================================================

def generate_summaries(tickets, use_llm: bool = False) -> List:
    """
    Generate summaries for a list of tickets.
    
    Args:
        tickets: List of SQLAlchemy Ticket objects or dicts
        use_llm: If True, use Qwen for cluster sample summaries
        
    Returns:
        List of summary strings (same order as input)
    """
    summaries = []
    for ticket in tickets:
        summary = build_smart_summary(
            short_desc=_get_field(ticket, 'short_description'),
            resolution_notes=_get_field(ticket, 'resolution_notes'),
            resolved_by=_get_field(ticket, 'resolved_by'),
            mttr_hours=_get_float(ticket, 'mttr_hours'),
            assignment_group=_get_field(ticket, 'assignment_group'),
            channel=_get_field(ticket, 'channel'),
            aio_subcategory=_get_field(ticket, 'aio_subcategory'),
        )
        summaries.append(summary)
    return summaries


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


# Make List available for type hints
