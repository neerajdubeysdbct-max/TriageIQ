"""
automation_detector.py
----------------------
Universal automation detection with FULL EXPLAINABILITY.
Works across ServiceNow incident, request/task and monitoring-driven exports.

Every classification includes evidence chain showing WHY.
"""

from typing import Dict, List, Tuple, Optional
import re

# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL DEFINITIONS
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

# Resolution codes indicating NOT real automation
INVALID_RESOLUTION_CODES = [
    'cancelled', 'duplicate', 'not reproducible', 'user error', 'no fault found',
    'withdrawn', 'rejected', 'invalid'
]

# Channels indicating automation source
AUTO_CHANNELS = ['event management', 'monitoring', 'api', 'integration', 'automated']
MANUAL_CHANNELS = ['phone', 'walk-in', 'chat']

# Categories pre-labeled as automated
AUTO_CATEGORIES = ['automated alerts', 'monitoring event', 'event management']

# Assignment groups indicating automation team
AUTO_ASSIGNMENT_GROUPS = ['automation', 'netcool', 'integration', 'orchestration']


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
# MAIN DETECTION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_automation_status(row: Dict) -> Dict:
    """
    Detect automation status with FULL EXPLAINABILITY.
    
    Returns:
    {
        'status': 'Already Automated' | 'Can Be Automated' | 'Manual Only' | 'Excluded',
        'confidence': 0-100,
        'evidence': [list of evidence strings],
        'signals': {detailed signal breakdown},
        'solution_lever': recommended solution,
        'reasoning': human-readable explanation
    }
    """
    
    # Initialize
    evidence = []
    signals = {}
    score = 0  # Positive = automated, Negative = manual
    
    # ─────────────────────────────────────────────────────────────────────────
    # EXTRACT ALL FIELDS
    # ─────────────────────────────────────────────────────────────────────────
    
    # Identifiers
    ticket_number = safe_lower(row.get('ticket_number', ''))
    
    # People/Systems
    caller = safe_lower(row.get('caller_id', '') or row.get('caller', ''))
    affected_user = safe_lower(row.get('affected_user', ''))
    assigned_to = safe_lower(row.get('assigned_to', ''))
    resolved_by = safe_lower(row.get('resolved_by', ''))
    sys_updated_by = safe_lower(row.get('sys_updated_by', ''))
    
    # Categorization
    channel = safe_lower(row.get('channel', '') or row.get('origin', ''))
    category = safe_lower(row.get('category', ''))
    subcategory = safe_lower(row.get('subcategory', ''))
    assignment_group = safe_lower(row.get('assignment_group', ''))
    
    # Descriptions
    short_desc = safe_lower(row.get('short_description', ''))
    description = safe_lower(row.get('description', ''))
    resolution_notes = safe_lower(row.get('resolution_notes', '') or row.get('close_notes', ''))
    work_notes = safe_lower(row.get('work_notes', ''))
    resolution_code = safe_lower(row.get('resolution_code', ''))
    
    # Metrics
    mttr_hours = row.get('mttr_hours')
    reassignment_count = int(row.get('reassignment_count', 0) or 0)
    reopen_count = int(row.get('reopen_count', 0) or 0)
    
    # Existing labels
    existing_ia_category = row.get('existing_ia_category')
    
    # ─────────────────────────────────────────────────────────────────────────
    # EXCLUSION CHECK (Cancelled, Duplicate, etc.)
    # ─────────────────────────────────────────────────────────────────────────
    
    is_invalid, invalid_matches = contains_any(resolution_code, INVALID_RESOLUTION_CODES)
    if is_invalid:
        return {
            'status': 'Excluded',
            'confidence': 100,
            'evidence': [f"Resolution code indicates invalid ticket: {', '.join(invalid_matches)}"],
            'signals': {'resolution_code': resolution_code, 'invalid_matches': invalid_matches},
            'solution_lever': 'N/A',
            'reasoning': f"Ticket was {invalid_matches[0]} - excluded from automation analysis"
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: EXISTING IA LABEL (Gold standard)
    # ─────────────────────────────────────────────────────────────────────────
    
    if existing_ia_category:
        evidence.append(f"✓ Has existing IA label: {existing_ia_category}")
        signals['existing_ia_label'] = True
        score += 10  # Definitive
        
        return {
            'status': 'Already Automated',
            'confidence': 100,
            'evidence': evidence,
            'signals': signals,
            'solution_lever': 'Existing Automation',
            'reasoning': f"Pre-labeled as automated: {existing_ia_category}"
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: CALLER/SOURCE ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    is_monitoring_caller, monitoring_matches = contains_any(caller, MONITORING_TOOLS)
    is_monitoring_affected, affected_matches = contains_any(affected_user, MONITORING_TOOLS + AUTOMATION_RESOLVERS)
    
    if is_monitoring_caller:
        evidence.append(f"✓ Ticket created by monitoring tool: {caller}")
        signals['monitoring_caller'] = caller
        score += 2
    
    if is_monitoring_affected:
        evidence.append(f"✓ Affected user is automation system: {affected_user}")
        signals['automation_affected_user'] = affected_user
        score += 2
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: CHANNEL ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    is_auto_channel, channel_matches = contains_any(channel, AUTO_CHANNELS)
    is_manual_channel, manual_channel_matches = contains_any(channel, MANUAL_CHANNELS)
    
    if is_auto_channel:
        evidence.append(f"✓ Automated channel: {channel}")
        signals['auto_channel'] = channel
        score += 2
    elif is_manual_channel:
        evidence.append(f"✗ Manual channel: {channel}")
        signals['manual_channel'] = channel
        score -= 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: CATEGORY ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    is_auto_category, cat_matches = contains_any(category + ' ' + subcategory, AUTO_CATEGORIES)
    
    if is_auto_category:
        evidence.append(f"✓ Auto category: {category}/{subcategory}")
        signals['auto_category'] = f"{category}/{subcategory}"
        score += 3
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: RESOLVER ANALYSIS (Critical)
    # ─────────────────────────────────────────────────────────────────────────
    
    is_auto_resolver, resolver_matches = contains_any(resolved_by, AUTOMATION_RESOLVERS)
    is_auto_assigned, assigned_matches = contains_any(assigned_to, AUTOMATION_RESOLVERS)
    is_auto_updater, updater_matches = contains_any(sys_updated_by, AUTOMATION_RESOLVERS)
    
    has_automation_tool = is_auto_resolver or is_auto_assigned or is_auto_updater
    
    if is_auto_resolver:
        evidence.append(f"✓ Resolved by automation tool: {resolved_by}")
        signals['auto_resolver'] = resolved_by
        score += 3
    
    if is_auto_assigned and not is_auto_resolver:
        evidence.append(f"⚠ Assigned to automation but resolved differently: {assigned_to}")
        signals['auto_assigned_diff_resolver'] = {'assigned': assigned_to, 'resolved': resolved_by}
        score += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: WORK NOTES ANALYSIS (Ignio, etc.)
    # ─────────────────────────────────────────────────────────────────────────
    
    has_auto_work, auto_work_matches = contains_any(work_notes, AUTOMATION_WORK_PATTERNS)
    has_human_work, human_work_matches = contains_any(work_notes, HUMAN_INVESTIGATION_PATTERNS)
    work_complexity, work_length = calculate_work_notes_complexity(work_notes)
    
    signals['work_notes_complexity'] = work_complexity
    signals['work_notes_length'] = work_length
    
    if has_auto_work:
        evidence.append(f"✓ Automation tool activity in work notes: {', '.join(auto_work_matches[:2])}")
        signals['automation_in_work_notes'] = auto_work_matches
        score += 2
    
    if has_human_work:
        evidence.append(f"✗ Human investigation noted: {', '.join(human_work_matches[:2])}")
        signals['human_investigation'] = human_work_matches
        score -= 2
    
    if work_complexity == 'extensive':
        evidence.append(f"✗ Extensive work notes ({work_length} chars) indicate complex manual work")
        score -= 1
    elif work_complexity in ['empty', 'minimal']:
        evidence.append(f"✓ Minimal work notes suggest automated/simple resolution")
        score += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: SELF-HEALING DETECTION
    # ─────────────────────────────────────────────────────────────────────────
    
    is_self_healed, heal_matches = contains_any(resolution_notes, SELF_HEAL_PATTERNS)
    
    if is_self_healed:
        evidence.append(f"✓ Self-healing detected: {', '.join(heal_matches[:2])}")
        signals['self_healed'] = True
        signals['heal_patterns'] = heal_matches
        score += 3
        
        # If monitoring created and self-healed, this is definitely automated
        if is_monitoring_caller or is_auto_channel:
            evidence.append(f"✓ Monitoring alert + self-healing = infrastructure automation")
            score += 2
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: MTTR ANALYSIS (Critical)
    # ─────────────────────────────────────────────────────────────────────────
    
    if mttr_hours is not None:
        mttr_minutes = mttr_hours * 60
        signals['mttr_minutes'] = round(mttr_minutes, 1)
        
        if mttr_minutes < 15:
            evidence.append(f"✓ Very fast resolution: {mttr_minutes:.0f} min")
            score += 3
        elif mttr_minutes < 30:
            evidence.append(f"✓ Fast resolution: {mttr_minutes:.0f} min")
            score += 2
        elif mttr_minutes < 60:
            evidence.append(f"○ Moderate resolution time: {mttr_minutes:.0f} min")
            score += 1
        elif mttr_minutes < 240:  # 4 hours
            evidence.append(f"✗ Slow resolution: {mttr_minutes:.0f} min")
            score -= 1
        else:
            evidence.append(f"✗ Very slow resolution: {mttr_minutes:.0f} min ({mttr_hours:.1f} hours)")
            score -= 2
        
        # Critical: If has automation tool but slow, automation didn't fully work
        if has_automation_tool and mttr_minutes > 60:
            evidence.append(f"⚠ Automation tool assigned but slow MTTR - tool needs tuning")
            signals['automation_tool_slow'] = True
            score -= 1  # Reduce confidence
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 9: REASSIGNMENT ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    signals['reassignment_count'] = reassignment_count
    signals['reopen_count'] = reopen_count
    
    if reassignment_count == 0:
        evidence.append(f"✓ No reassignment - direct resolution")
        score += 1
    elif reassignment_count == 1:
        evidence.append(f"○ Single reassignment")
        # Neutral
    elif reassignment_count >= 2:
        evidence.append(f"✗ Multiple reassignments ({reassignment_count}) - complex issue")
        score -= 2
    
    if reopen_count > 0:
        evidence.append(f"✗ Ticket reopened {reopen_count} times - resolution quality issue")
        score -= 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 10: ASSIGNMENT GROUP ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    is_auto_group, group_matches = contains_any(assignment_group, AUTO_ASSIGNMENT_GROUPS)
    
    if is_auto_group:
        evidence.append(f"✓ Assigned to automation team: {assignment_group}")
        signals['automation_team'] = assignment_group
        score += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 11: SHORT DESCRIPTION PATTERNS
    # ─────────────────────────────────────────────────────────────────────────
    
    # Event policy pattern (monitoring rules)
    if 'event policy:' in short_desc or 'issue type :' in short_desc:
        evidence.append(f"✓ Monitoring rule triggered (Event policy in description)")
        signals['monitoring_rule'] = True
        score += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # FINAL CLASSIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    
    signals['final_score'] = score
    
    # Calculate confidence (0-100)
    # Score range roughly -10 to +15, map to 0-100
    confidence = min(max(int(50 + score * 5), 10), 100)
    
    # Determine status
    if score >= 6:
        status = 'Already Automated'
        solution_lever = 'Existing Automation'
        
        # Refine solution lever
        if is_self_healed:
            solution_lever = 'Self-Healing Infrastructure'
        elif is_auto_resolver:
            # Extract tool name
            if 'ignio' in resolved_by:
                solution_lever = 'Ignio Auto-Remediation'
            elif 'netcool' in resolved_by:
                solution_lever = 'Netcool Automation'
            elif 'verizon' in resolved_by:
                solution_lever = 'Verizon Proactive'
            else:
                solution_lever = 'Existing Automation'
        
        reasoning = f"Strong automation evidence (score: {score}). " + "; ".join([e for e in evidence if e.startswith('✓')][:3])
        
    elif score >= 2:
        status = 'Can Be Automated'
        
        # Determine best solution lever
        if has_automation_tool and mttr_hours and mttr_hours > 1:
            solution_lever = 'Automation Tuning'
            reasoning = f"Automation tool exists but needs tuning (MTTR: {mttr_hours:.1f}h)"
        elif is_monitoring_caller or is_auto_channel:
            solution_lever = 'Auto-Remediation Script'
            reasoning = "Monitoring alert - can be extended with auto-remediation"
        elif 'password' in short_desc or 'reset' in short_desc or 'access' in short_desc:
            solution_lever = 'Self-Service Portal'
            reasoning = "Access/password request - suitable for self-service"
        elif mttr_hours and mttr_hours < 0.5:
            solution_lever = 'Script/Runbook'
            reasoning = f"Fast resolution ({mttr_hours*60:.0f} min) suggests scriptable"
        else:
            solution_lever = 'RPA/Script'
            reasoning = "Automation potential based on patterns"
        
    else:
        status = 'Manual Only'
        solution_lever = 'Manual Process'
        
        # Explain why manual
        manual_reasons = [e for e in evidence if e.startswith('✗')]
        if manual_reasons:
            reasoning = f"Manual intervention required. " + "; ".join(manual_reasons[:2])
        else:
            reasoning = "Insufficient automation evidence"
    
    return {
        'status': status,
        'confidence': confidence,
        'evidence': evidence,
        'signals': signals,
        'solution_lever': solution_lever,
        'reasoning': reasoning
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WRAPPER FOR CHUNK PROCESSOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_automation_for_ticket(row: Dict) -> Dict:
    """
    Wrapper function to integrate with chunk_processor.py
    Returns fields compatible with Ticket model.
    """
    result = detect_automation_status(row)
    
    # Map status to boolean flags
    is_already_automated = result['status'] == 'Already Automated'
    can_be_automated = result['status'] == 'Can Be Automated'
    
    # Build evidence string for display
    evidence_str = ' | '.join(result['evidence'][:5])  # Top 5 evidence items
    
    return {
        # Boolean flags
        'is_already_automated': is_already_automated,
        'can_be_automated': can_be_automated,
        
        # Scores
        'automation_potential_score': float(result['confidence']),
        
        # AiOps columns
        'aiops_automation_status': result['status'],
        'aiops_solution_lever': result['solution_lever'],
        'aiops_confidence': result['confidence'] / 100.0,
        'aiops_keywords': evidence_str,
        'aiops_additional_info': result['reasoning'],
        'aiops_predicted_by': 'rule_v2',
        
        # L1-L4 (can be enhanced based on category/subcategory)
        'l3_automation_feasibility': 'High' if is_already_automated else ('Medium' if can_be_automated else 'Low'),
        'l4_automation_type': result['solution_lever'],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_detection():
    """Test with sample tickets"""
    
    test_cases = [
        {
            'name': 'Full automation (bot created and resolved)',
            'ticket_number': 'INC0429086',
            'channel': 'Event Management',
            'caller_id': 'Automated ID for Netcool [IBM]',
            'resolved_by': 'Automated ID for Netcool [IBM]',
            'resolution_code': 'Solved (Permanently)',
            'mttr_hours': 0.2,
            'reassignment_count': 0,
            'short_description': 'High space used (95%) for /logs',
            'category': 'Automated Alerts',
            'subcategory': 'Monitoring Event',
        },
        {
            'name': 'Ignio diagnosed, human resolved',
            'ticket_number': 'INC1129619',
            'caller_id': 'sciencelogic',
            'resolved_by': 'Abhishek Karippal Bharath',
            'work_notes': 'Ignio is working on your request... CPU utilization is below threshold now.',
            'resolution_notes': 'CPU utilization is below threshold now. Alert resolved from SL.',
            'mttr_hours': 2.8,
            'reassignment_count': 1,
            'short_description': 'Issue type : CPU Utilization, Event policy: Host Resource',
        },
        {
            'name': 'Phone password reset',
            'ticket_number': 'INC0429083',
            'channel': 'Phone',
            'caller_id': 'A03530',
            'resolved_by': 'Ankur Gupta',
            'mttr_hours': 0.08,  # ~5 min
            'reassignment_count': 0,
            'short_description': 'GUI/SSO Password Reset / [x601052]',
            'category': 'User Administration',
            'subcategory': 'Password Reset - GUI / SSO',
        },
        {
            'name': 'Cancelled duplicate',
            'ticket_number': 'INC0429089',
            'channel': 'Email',
            'resolved_by': 'Ankur Gupta',
            'resolution_code': 'Cancelled',
            'short_description': 'CLOSURE OF DUPLICATE TICKET',
        },
        {
            'name': 'Complex manual - multiple reassignments',
            'ticket_number': 'INC9999999',
            'channel': 'Phone',
            'caller_id': 'John Smith',
            'resolved_by': 'Senior Engineer',
            'mttr_hours': 8.5,
            'reassignment_count': 4,
            'work_notes': 'Investigated the issue. Found that the root cause was... Escalated to vendor.',
            'resolution_notes': 'Applied patch after vendor consultation.',
        },
    ]
    
    print("=" * 80)
    print("AUTOMATION DETECTION TEST RESULTS")
    print("=" * 80)
    
    for tc in test_cases:
        name = tc.pop('name')
        result = detect_automation_status(tc)
        
        print(f"\n{'─' * 80}")
        print(f"TEST: {name}")
        print(f"{'─' * 80}")
        print(f"STATUS: {result['status']} ({result['confidence']}% confidence)")
        print(f"SOLUTION: {result['solution_lever']}")
        print(f"REASONING: {result['reasoning']}")
        print(f"\nEVIDENCE:")
        for e in result['evidence']:
            print(f"  {e}")
        print(f"\nSIGNALS: {result['signals']}")


if __name__ == '__main__':
    test_detection()