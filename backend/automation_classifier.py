"""
automation_classifier.py
------------------------
Hybrid automation classifier combining rules + ML.
Uses rules for explainability, ML for edge cases.
"""

from typing import Dict, List, Optional
from automation_rules import classify_by_rules
from automation_ml import predict_with_ml, is_ml_available
from automation_config import TOOL_RECOMMENDATIONS


def classify_ticket(ticket: Dict) -> Dict:
    """
    Hybrid classification: Rules + ML combined.
    
    Priority:
    1. If rule confidence >= 80% → Use rules (explainable)
    2. If ML confidence >= 80% and rules < 80% → Use ML
    3. If both agree → High confidence
    4. If disagree → Use higher confidence, flag for review
    
    Args:
        ticket: Dict with ticket fields
        
    Returns:
        {
            'status': 'Already Automated' | 'Can Be Automated' | 'Manual Only' | 'Excluded',
            'confidence': 0-100,
            'evidence': [list of evidence strings],
            'solution_lever': recommended solution,
            'tools': [list of recommended tools],
            'effort': implementation effort,
            'reasoning': human-readable explanation,
            'predicted_by': 'rule' | 'ml' | 'hybrid',
            'needs_review': bool,
            
            # For DB storage
            'is_already_automated': bool,
            'can_be_automated': bool,
            'automation_potential_score': float,
            'aiops_automation_status': str,
            'aiops_solution_lever': str,
            'aiops_keywords': str,
            'aiops_additional_info': str,
            'aiops_confidence': float,
            'aiops_predicted_by': str,
        }
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Get rule-based prediction
    # ═══════════════════════════════════════════════════════════════════════
    
    rule_result = classify_by_rules(ticket)
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Get ML prediction (if available)
    # ═══════════════════════════════════════════════════════════════════════
    
    ml_result = None
    if is_ml_available():
        ml_result = predict_with_ml(ticket)
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Combine results
    # ═══════════════════════════════════════════════════════════════════════
    
    needs_review = False
    predicted_by = 'rule'
    
    if rule_result['confidence'] >= 80:
        # Strong rule match - use rules
        final_status = rule_result['status']
        final_confidence = rule_result['confidence']
        predicted_by = 'rule'
        
    elif ml_result and ml_result['confidence'] >= 80:
        # ML is confident - use ML but keep rule evidence
        final_status = ml_result['status']
        final_confidence = ml_result['confidence']
        predicted_by = 'ml'
        
    elif ml_result and rule_result['status'] == ml_result['status']:
        # Both agree - boost confidence
        final_status = rule_result['status']
        final_confidence = min(95, max(rule_result['confidence'], ml_result['confidence']) + 10)
        predicted_by = 'hybrid'
        
    elif ml_result and rule_result['status'] != ml_result['status']:
        # Disagreement - use higher confidence, flag for review
        if rule_result['confidence'] >= ml_result['confidence']:
            final_status = rule_result['status']
            final_confidence = rule_result['confidence']
            predicted_by = 'rule'
        else:
            final_status = ml_result['status']
            final_confidence = ml_result['confidence']
            predicted_by = 'ml'
        needs_review = True
        
    else:
        # No ML - use rules
        final_status = rule_result['status']
        final_confidence = rule_result['confidence']
        predicted_by = 'rule'
    
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Build final result
    # ═══════════════════════════════════════════════════════════════════════
    
    solution_lever = rule_result['solution_lever']
    tools = rule_result.get('tools', [])
    tool_info = TOOL_RECOMMENDATIONS.get(solution_lever, {})
    
    # Build evidence string for DB
    evidence_str = ' | '.join(rule_result['evidence'][:5])
    
    # Determine boolean flags
    is_already_automated = final_status == 'Already Automated'
    can_be_automated = final_status == 'Can Be Automated'
    
    # Build L1-L4 categories
    category = ticket.get('category', 'Other')
    subcategory = ticket.get('subcategory', '')
    channel = ticket.get('channel', '')
    
    l1_category = _determine_l1_category(category, subcategory, channel)
    l3_feasibility = 'High' if is_already_automated else ('Medium' if can_be_automated else 'Low')
    
    return {
        # Classification result
        'status': final_status,
        'confidence': final_confidence,
        'evidence': rule_result['evidence'],
        'solution_lever': solution_lever,
        'tools': tools,
        'effort': tool_info.get('effort', 'Unknown'),
        'tool_description': tool_info.get('description', ''),
        'reasoning': rule_result['reasoning'],
        'predicted_by': predicted_by,
        'needs_review': needs_review,
        
        # ML info (if available)
        'ml_prediction': ml_result,
        
        # For DB storage - Ticket model fields
        'is_already_automated': is_already_automated,
        'can_be_automated': can_be_automated,
        'automation_potential_score': float(final_confidence),
        
        # AiOps columns
        'aiops_automation_status': final_status,
        'aiops_solution_lever': solution_lever,
        'aiops_keywords': evidence_str,
        'aiops_additional_info': rule_result['reasoning'],
        'aiops_confidence': final_confidence / 100.0,
        'aiops_predicted_by': predicted_by,
        'aiops_type': 'Technical' if 'event' in channel.lower() else 'Functional',
        'aiops_category': category.title() if category else 'Other',
        'aiops_subcategory': subcategory.title() if subcategory else '',
        
        # L1-L4
        'l1_category': l1_category,
        'l2_subcategory': subcategory.title() if subcategory else '',
        'l3_automation_feasibility': l3_feasibility,
        'l4_automation_type': solution_lever,
    }


def _determine_l1_category(category: str, subcategory: str, channel: str) -> str:
    """Determine L1 category from ticket data"""
    cat_lower = (category or '').lower()
    sub_lower = (subcategory or '').lower()
    channel_lower = (channel or '').lower()
    
    # Access Management
    if any(x in cat_lower + sub_lower for x in ['password', 'access', 'user admin', 'account', 'vpn', 'permission', 'locked', 'unlock']):
        return 'Access Management'
    
    # Event Management (monitoring alerts)
    if any(x in channel_lower for x in ['event', 'monitoring', 'alert']):
        return 'Event Management'
    
    # Infrastructure
    if any(x in cat_lower + sub_lower for x in ['server', 'storage', 'backup', 'network', 'database', 'compute', 'linux', 'windows', 'unix', 'vmware']):
        return 'Infrastructure'
    
    # Application
    if any(x in cat_lower + sub_lower for x in ['application', 'software', 'app', 'sap', 'oracle']):
        return 'Application'
    
    # Security
    if any(x in cat_lower + sub_lower for x in ['security', 'firewall', 'antivirus', 'malware']):
        return 'Security'
    
    # Email
    if any(x in cat_lower + sub_lower for x in ['email', 'mail', 'exchange', 'outlook']):
        return 'Email'
    
    # End User
    if any(x in cat_lower + sub_lower for x in ['desktop', 'laptop', 'printer', 'hardware', 'end user']):
        return 'End User Support'
    
    # Service Fulfillment
    if any(x in cat_lower + sub_lower for x in ['request', 'provision', 'install', 'onboard']):
        return 'Service Fulfillment'
    
    # Return actual category if no match
    return category.title() if category else 'Other'

def classify_batch(tickets: List[Dict]) -> List[Dict]:
    """Classify multiple tickets"""
    return [classify_ticket(t) for t in tickets]


def get_classification_summary(results: List[Dict]) -> Dict:
    """
    Get summary statistics from classification results.
    
    Returns:
        {
            'total': int,
            'by_status': {'Already Automated': count, ...},
            'by_solution': {'Self-Service Portal': count, ...},
            'by_confidence': {'high': count, 'medium': count, 'low': count},
            'needs_review': count,
        }
    """
    summary = {
        'total': len(results),
        'by_status': {},
        'by_solution': {},
        'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
        'needs_review': 0,
    }
    
    for r in results:
        # By status
        status = r.get('status', 'Unknown')
        summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
        
        # By solution
        solution = r.get('solution_lever', 'Unknown')
        summary['by_solution'][solution] = summary['by_solution'].get(solution, 0) + 1
        
        # By confidence
        conf = r.get('confidence', 0)
        if conf >= 80:
            summary['by_confidence']['high'] += 1
        elif conf >= 60:
            summary['by_confidence']['medium'] += 1
        else:
            summary['by_confidence']['low'] += 1
        
        # Needs review
        if r.get('needs_review'):
            summary['needs_review'] += 1
    
    return summary