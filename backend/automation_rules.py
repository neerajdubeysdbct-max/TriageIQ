"""
automation_rules.py
-------------------
Rule-based automation classification with full explainability.
Returns status, confidence, evidence for every ticket.
"""

from typing import Dict, List, Tuple, Optional
from automation_config import (
    MTTR_THRESHOLDS, COMPLEXITY_THRESHOLDS,
    MONITORING_TOOLS, AUTOMATION_RESOLVERS,
    SELF_HEAL_PATTERNS, AUTOMATION_WORK_PATTERNS,
    HUMAN_INVESTIGATION_PATTERNS, SIMPLE_RESOLUTION_PATTERNS,
    COMPLEX_RESOLUTION_PATTERNS, EXCLUSION_RESOLUTION_CODES,
    AUTO_CHANNELS, MANUAL_CHANNELS, AUTO_CATEGORIES,
    SELF_SERVICE_CATEGORIES, SHORT_DESC_PATTERNS,
    TOOL_RECOMMENDATIONS,
)


def safe_lower(value) -> str:
    """Safely convert to lowercase string"""
    if value is None:
        return ''
    return str(value).lower().strip()


def contains_any(text: str, patterns: List[str]) -> Tuple[bool, List[str]]:
    """Check if text contains any pattern, return matches"""
    text = safe_lower(text)
    matched = [p for p in patterns if p in text]
    return len(matched) > 0, matched


def classify_by_rules(ticket: Dict) -> Dict:
    """
    Rule-based classification with full explainability.
    
    Args:
        ticket: Dict with ticket fields
        
    Returns:
        {
            'status': 'Already Automated' | 'Can Be Automated' | 'Manual Only' | 'Excluded',
            'confidence': 0-100,
            'evidence': [list of evidence strings],
            'solution_lever': recommended solution,
            'tools': [list of recommended tools],
            'reasoning': human-readable explanation,
        }
    """
    
    evidence = []
    
    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACT FIELDS
    # ═══════════════════════════════════════════════════════════════════════
    
    caller = safe_lower(ticket.get('caller_id', '') or ticket.get('caller', ''))
    affected_user = safe_lower(ticket.get('affected_user', ''))
    resolved_by = safe_lower(ticket.get('resolved_by', ''))
    assigned_to = safe_lower(ticket.get('assigned_to', ''))
    
    channel = safe_lower(ticket.get('channel', ''))
    category = safe_lower(ticket.get('category', ''))
    subcategory = safe_lower(ticket.get('subcategory', ''))
    assignment_group = safe_lower(ticket.get('assignment_group', ''))
    
    short_desc = safe_lower(ticket.get('short_description', ''))
    resolution_notes = safe_lower(ticket.get('resolution_notes', '') or ticket.get('close_notes', ''))
    work_notes = safe_lower(ticket.get('work_notes', ''))
    resolution_code = safe_lower(ticket.get('resolution_code', ''))
    
    mttr_hours = ticket.get('mttr_hours')
    mttr_minutes = mttr_hours * 60 if mttr_hours else None
    reassignment_count = int(ticket.get('reassignment_count', 0) or 0)
    reopen_count = int(ticket.get('reopen_count', 0) or 0)
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: CHECK EXCLUSIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    is_excluded, excluded_matches = contains_any(resolution_code, EXCLUSION_RESOLUTION_CODES)
    if is_excluded:
        return {
            'status': 'Excluded',
            'confidence': 100,
            'evidence': [f"Ticket excluded: {excluded_matches[0]}"],
            'solution_lever': 'N/A',
            'tools': [],
            'reasoning': f"Ticket was {excluded_matches[0]} - not real work",
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: CHECK SELF-HEALING (Regardless of resolver/MTTR)
    # ═══════════════════════════════════════════════════════════════════════
    is_self_healed, heal_matches = contains_any(resolution_notes, SELF_HEAL_PATTERNS)
    is_monitoring_caller, _ = contains_any(caller, MONITORING_TOOLS)
    is_auto_channel, _ = contains_any(channel, AUTO_CHANNELS)
    is_auto_resolver, _ = contains_any(resolved_by, AUTOMATION_RESOLVERS)
    is_human_resolver = resolved_by and ' ' in resolved_by.strip() and not is_auto_resolver
    
    if is_self_healed and (is_monitoring_caller or is_auto_channel):
        if is_auto_resolver or not resolved_by:
            evidence.append(f"✓ Self-healed: '{heal_matches[0]}'")
            evidence.append(f"✓ Resolved by automation")
            
            return {
                'status': 'Already Automated',
                'confidence': 95,
                'evidence': evidence,
                'solution_lever': 'Self-Healing',
                'tools': TOOL_RECOMMENDATIONS['Self-Healing']['tools'],
                'reasoning': "Infrastructure self-healed without human intervention",
            }
        else:
            evidence.append(f"✓ Self-healed: '{heal_matches[0]}'")
            evidence.append(f"✗ But human closed: {resolved_by[:25]}")
            
            return {
                'status': 'Can Be Automated',
                'confidence': 85,
                'evidence': evidence,
                'solution_lever': 'Auto-Close Script',
                'tools': ['ServiceNow Flow', 'Auto-Close Rule'],
                'reasoning': "Self-healed but human had to close - add auto-close",
            }
    
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: DETECT SIGNALS
    # ═══════════════════════════════════════════════════════════════════════
    
    # 3a. Resolver analysis
    is_auto_resolver, resolver_matches = contains_any(resolved_by, AUTOMATION_RESOLVERS)
    is_human_resolver = resolved_by and ' ' in resolved_by and not is_auto_resolver
    
    # 3b. Work notes analysis
    has_auto_work, auto_work_matches = contains_any(work_notes, AUTOMATION_WORK_PATTERNS)
    has_human_work, human_work_matches = contains_any(work_notes, HUMAN_INVESTIGATION_PATTERNS)
    
    # 3c. Resolution analysis
    has_simple_resolution, simple_matches = contains_any(resolution_notes, SIMPLE_RESOLUTION_PATTERNS)
    has_complex_resolution, complex_matches = contains_any(resolution_notes, COMPLEX_RESOLUTION_PATTERNS)
    
    # 3d. Category analysis
    is_auto_category, _ = contains_any(category + ' ' + subcategory, AUTO_CATEGORIES)
    is_self_service_category, _ = contains_any(category + ' ' + subcategory, SELF_SERVICE_CATEGORIES)
    
    # 3e. Complexity signals
    is_complex = (
        reassignment_count >= COMPLEXITY_THRESHOLDS['reassignment_complex'] or
        reopen_count >= COMPLEXITY_THRESHOLDS['reopen_complex'] or
        len(work_notes) > COMPLEXITY_THRESHOLDS['work_notes_very_long'] or
        has_complex_resolution
    )
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: CHECK COMPLEXITY (Manual Only)
    # ═══════════════════════════════════════════════════════════════════════
    
    if is_complex:
        if reassignment_count >= COMPLEXITY_THRESHOLDS['reassignment_complex']:
            evidence.append(f"✗ Multiple reassignments: {reassignment_count}")
        if reopen_count >= COMPLEXITY_THRESHOLDS['reopen_complex']:
            evidence.append(f"✗ Reopened: {reopen_count} times")
        if len(work_notes) > COMPLEXITY_THRESHOLDS['work_notes_very_long']:
            evidence.append(f"✗ Extensive investigation: {len(work_notes)} chars")
        if has_complex_resolution:
            evidence.append(f"✗ Complex resolution: '{complex_matches[0]}'")
        
        return {
            'status': 'Manual Only',
            'confidence': 85,
            'evidence': evidence,
            'solution_lever': 'Manual Process',
            'tools': [],
            'reasoning': "Complex issue requiring human judgment",
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: CHECK AUTOMATION RESOLVER
    # ═══════════════════════════════════════════════════════════════════════
    
    if is_auto_resolver:
        evidence.append(f"✓ Resolved by automation: {resolved_by[:30]}")
        
        if mttr_minutes and mttr_minutes < MTTR_THRESHOLDS['auto_fast']:
            evidence.append(f"✓ Fast resolution: {mttr_minutes:.0f} min")
            return {
                'status': 'Already Automated',
                'confidence': 95,
                'evidence': evidence,
                'solution_lever': 'Existing Automation',
                'tools': TOOL_RECOMMENDATIONS['Self-Healing']['tools'],
                'reasoning': "Automation tool resolved quickly",
            }
        else:
            mttr_str = f"{mttr_minutes:.0f} min" if mttr_minutes else "unknown"
            evidence.append(f"⚠ Slow resolution: {mttr_str}")
            return {
                'status': 'Can Be Automated',
                'confidence': 80,
                'evidence': evidence,
                'solution_lever': 'Automation Tuning',
                'tools': TOOL_RECOMMENDATIONS['Automation Tuning']['tools'],
                'reasoning': "Automation exists but needs tuning/optimization",
            }
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6: HUMAN RESOLVED - DETERMINE SOLUTION LEVER
    # ═══════════════════════════════════════════════════════════════════════
    
    if is_human_resolver:
        evidence.append(f"✓ Resolved by human: {resolved_by[:25]}")
    
    # 6a. Check for self-service candidates
    for lever, patterns in SHORT_DESC_PATTERNS.items():
        if lever == 'Self-Service Portal':
            has_pattern, matches = contains_any(short_desc, patterns)
            if has_pattern or is_self_service_category:
                evidence.append(f"✓ Self-service pattern: '{matches[0] if matches else category}'")
                if mttr_minutes:
                    evidence.append(f"✓ Resolution time: {mttr_minutes:.0f} min")
                return {
                    'status': 'Can Be Automated',
                    'confidence': 90,
                    'evidence': evidence,
                    'solution_lever': 'Self-Service Portal',
                    'tools': TOOL_RECOMMENDATIONS['Self-Service Portal']['tools'],
                    'reasoning': "User can perform this action via self-service",
                }
    
    # 6b. Check for auto-remediation candidates (monitoring alerts)
    if is_monitoring_caller or is_auto_channel or is_auto_category:
        evidence.append(f"✓ Monitoring alert: {channel or category}")
        if has_auto_work:
            evidence.append(f"✓ Automation attempted: {auto_work_matches[0]}")
        if mttr_minutes:
            evidence.append(f"✓ Resolution time: {mttr_minutes:.0f} min")
        
        return {
            'status': 'Can Be Automated',
            'confidence': 85,
            'evidence': evidence,
            'solution_lever': 'Auto-Remediation',
            'tools': TOOL_RECOMMENDATIONS['Auto-Remediation']['tools'],
            'reasoning': "Monitoring alert - add auto-remediation script",
        }
    
    # 6c. Check for script/runbook candidates
    for lever, patterns in SHORT_DESC_PATTERNS.items():
        if lever == 'Script/Runbook':
            has_pattern, matches = contains_any(short_desc + ' ' + resolution_notes, patterns)
            if has_pattern:
                evidence.append(f"✓ Scriptable pattern: '{matches[0]}'")
                if mttr_minutes:
                    evidence.append(f"✓ Resolution time: {mttr_minutes:.0f} min")
                return {
                    'status': 'Can Be Automated',
                    'confidence': 80,
                    'evidence': evidence,
                    'solution_lever': 'Script/Runbook',
                    'tools': TOOL_RECOMMENDATIONS['Script/Runbook']['tools'],
                    'reasoning': "Repetitive task that can be scripted",
                }
    
    # 6d. Check for RPA candidates
    for lever, patterns in SHORT_DESC_PATTERNS.items():
        if lever == 'RPA':
            has_pattern, matches = contains_any(short_desc, patterns)
            if has_pattern:
                evidence.append(f"✓ RPA pattern: '{matches[0]}'")
                return {
                    'status': 'Can Be Automated',
                    'confidence': 75,
                    'evidence': evidence,
                    'solution_lever': 'RPA',
                    'tools': TOOL_RECOMMENDATIONS['RPA']['tools'],
                    'reasoning': "UI-based repetitive task suitable for RPA",
                }
    
    # 6e. Fast resolution without patterns = scriptable
    if mttr_minutes and mttr_minutes < MTTR_THRESHOLDS['auto_fast'] and reassignment_count <= 1:
        evidence.append(f"✓ Very fast resolution: {mttr_minutes:.0f} min")
        evidence.append(f"✓ No reassignments")
        if has_simple_resolution:
            evidence.append(f"✓ Simple resolution: '{simple_matches[0]}'")
        
        return {
            'status': 'Can Be Automated',
            'confidence': 80,
            'evidence': evidence,
            'solution_lever': 'Script/Runbook',
            'tools': TOOL_RECOMMENDATIONS['Script/Runbook']['tools'],
            'reasoning': "Fast, simple resolution - can be scripted",
        }
    
    # 6f. Medium speed routine work
    if mttr_minutes and mttr_minutes < MTTR_THRESHOLDS['routine'] and reassignment_count == 0:
        evidence.append(f"✓ Routine resolution time: {mttr_minutes:.0f} min")
        evidence.append(f"✓ No reassignments")
        
        return {
            'status': 'Can Be Automated',
            'confidence': 70,
            'evidence': evidence,
            'solution_lever': 'Script/Runbook',
            'tools': TOOL_RECOMMENDATIONS['Script/Runbook']['tools'],
            'reasoning': "Routine work - can be automated",
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 7: DEFAULT - NEEDS MORE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    
    # Check if there are any positive signals
    if has_simple_resolution:
        evidence.append(f"✓ Simple resolution: '{simple_matches[0]}'")
        return {
            'status': 'Can Be Automated',
            'confidence': 65,
            'evidence': evidence,
            'solution_lever': 'Script/Runbook',
            'tools': TOOL_RECOMMENDATIONS['Script/Runbook']['tools'],
            'reasoning': "Simple resolution pattern detected",
        }
    
    if has_human_work:
        evidence.append(f"✗ Human investigation: '{human_work_matches[0]}'")
    
    if mttr_minutes and mttr_minutes > MTTR_THRESHOLDS['complex']:
        evidence.append(f"✗ Long resolution: {mttr_hours:.1f} hours")
    
    # Default to Manual Only if no automation signals
    return {
        'status': 'Manual Only',
        'confidence': 60,
        'evidence': evidence if evidence else ["No clear automation pattern detected"],
        'solution_lever': 'Manual Process',
        'tools': [],
        'reasoning': "No clear automation opportunity identified",
    }


def get_rule_confidence(ticket: Dict) -> int:
    """Quick confidence check without full classification"""
    result = classify_by_rules(ticket)
    return result['confidence']