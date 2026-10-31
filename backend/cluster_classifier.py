"""
Cluster Category Classifier
Maps ML clusters to business-friendly categories using keyword matching
"""

from typing import Dict, List, Tuple
from utils import automation_savings

# Business categories with keywords, icons, and story templates
BUSINESS_CATEGORIES = {
    "Password & Access Requests": {
        "keywords": ["password", "reset", "unlock", "pin", "access", "locked", "credential", 
                     "login", "sso", "mfa", "ims", "racf", "vpn", "domain", "gui", "sso",
                     "account", "disabled", "expired", "authentication", "ldap", "ad"],
        "icon": "🔐",
        "color": "#7C3AED",
        "what": "Users requesting password resets, account unlocks, or access changes",
        "why": "No self-service portal available - users must contact helpdesk for basic credential changes",
        "impact_template": "{can_automate} tickets handled manually, costing ₹{monthly_cost}L/month in technician time",
        "solution": "Self-Service Portal",
        "solution_detail": "Deploy password reset portal with MFA verification and automated provisioning",
        "implementation": "4-6 weeks",
        "investment": "₹15-20L",
    },
    "Batch Job Failures": {
        "keywords": ["batch", "job", "failed", "abend", "jcl", "mvs", "eqqe", "mainframe", 
                     "scheduler", "opc", "twsz", "ctrl-m", "autosys", "batch_detail", "u3e7"],
        "icon": "⚙️",
        "color": "#EF4444",
        "what": "Mainframe/server batch jobs failing and requiring manual restart",
        "why": "Jobs fail due to resource locks, timeouts, dependency issues, or transient errors",
        "impact_template": "{can_automate} job failures need manual intervention, costing ₹{monthly_cost}L/month",
        "solution": "Auto-Remediation",
        "solution_detail": "Deploy auto-restart scripts with dependency checks and smart retry logic",
        "implementation": "3-4 weeks",
        "investment": "₹10-15L",
    },
    "Disk Space Alerts": {
        "keywords": ["disk", "space", "storage", "capacity", "volume", "filesystem", "full",
                     "threshold", "90%", "95%", "98%", "drive", "partition", "quota", "logs"],
        "icon": "💾",
        "color": "#F59E0B",
        "what": "Servers running low on disk space triggering monitoring alerts",
        "why": "Log files, temp files, or data growth not cleaned up automatically",
        "impact_template": "{can_automate} alerts require manual cleanup, costing ₹{monthly_cost}L/month",
        "solution": "Auto-Remediation",
        "solution_detail": "Deploy automated log rotation, temp cleanup, and archive scripts",
        "implementation": "2-3 weeks",
        "investment": "₹5-10L",
    },
    "Service Health Issues": {
        "keywords": ["service", "stopped", "down", "restart", "state", "hung", "unresponsive",
                     "windows", "linux", "daemon", "process", "crashed", "not running", "failed to start"],
        "icon": "🔄",
        "color": "#2563EB",
        "what": "Critical services stopping or becoming unresponsive on servers",
        "why": "Memory leaks, application crashes, or dependency service failures",
        "impact_template": "{can_automate} service outages need manual restart, costing ₹{monthly_cost}L/month",
        "solution": "Auto-Remediation",
        "solution_detail": "Deploy service monitoring with auto-restart and health checks",
        "implementation": "2-3 weeks",
        "investment": "₹8-12L",
    },
    "CPU & Memory Alerts": {
        "keywords": ["cpu", "memory", "high", "workload", "threshold", "performance", "utilization",
                     "ram", "swap", "load", "busy", "spike", "bottleneck", "resource"],
        "icon": "📈",
        "color": "#10B981",
        "what": "Servers experiencing high CPU or memory utilization alerts",
        "why": "Resource-intensive processes, memory leaks, or insufficient capacity planning",
        "impact_template": "{can_automate} performance alerts need investigation, costing ₹{monthly_cost}L/month",
        "solution": "Automation Tuning",
        "solution_detail": "Tune alert thresholds, add auto-scaling, implement process management",
        "implementation": "2-4 weeks",
        "investment": "₹5-8L",
    },
    "Backup Failures": {
        "keywords": ["backup", "restore", "failed", "missed", "tape", "veeam", "netbackup",
                     "commvault", "avamar", "snapshot", "replication", "dr", "recovery"],
        "icon": "🛡️",
        "color": "#6366F1",
        "what": "Scheduled backups failing or missing their backup windows",
        "why": "Network issues, storage capacity, or backup job conflicts",
        "impact_template": "{can_automate} backup failures need manual intervention, costing ₹{monthly_cost}L/month",
        "solution": "Auto-Remediation",
        "solution_detail": "Deploy backup monitoring with auto-retry and capacity management",
        "implementation": "3-4 weeks",
        "investment": "₹10-15L",
    },
    "Network Connectivity Issues": {
        "keywords": ["network", "unreachable", "ping", "connectivity", "timeout", "packet",
                     "switch", "router", "firewall", "vpn", "latency", "dns", "dhcp"],
        "icon": "🔌",
        "color": "#EC4899",
        "what": "Network connectivity issues causing server or application unreachability",
        "why": "Network device issues, configuration changes, or intermittent connectivity",
        "impact_template": "{can_automate} network alerts need manual diagnosis, costing ₹{monthly_cost}L/month",
        "solution": "Script/Runbook",
        "solution_detail": "Deploy network diagnostic automation and failover scripts",
        "implementation": "4-6 weeks",
        "investment": "₹12-18L",
    },
    "Database Issues": {
        "keywords": ["database", "oracle", "sql", "mysql", "postgres", "db", "tablespace",
                     "query", "deadlock", "connection", "instance", "listener", "rman"],
        "icon": "🗄️",
        "color": "#14B8A6",
        "what": "Database alerts including tablespace, connection, and performance issues",
        "why": "Data growth, query performance, or connection pool exhaustion",
        "impact_template": "{can_automate} database alerts need DBA intervention, costing ₹{monthly_cost}L/month",
        "solution": "Automation Tuning",
        "solution_detail": "Implement auto-extend tablespace, connection pool management, query optimization alerts",
        "implementation": "4-6 weeks",
        "investment": "₹15-20L",
    },
    "Email & Messaging Issues": {
        "keywords": ["email", "outlook", "exchange", "mailbox", "smtp", "mail", "calendar",
                     "teams", "skype", "messaging", "inbox", "quota"],
        "icon": "📧",
        "color": "#F97316",
        "what": "Email delivery failures, mailbox issues, or messaging platform problems",
        "why": "Mailbox quotas, server issues, or configuration problems",
        "impact_template": "{can_automate} email issues need manual resolution, costing ₹{monthly_cost}L/month",
        "solution": "Self-Service Portal",
        "solution_detail": "Deploy self-service mailbox management and automated quota alerts",
        "implementation": "3-4 weeks",
        "investment": "₹8-12L",
    },
    "User Provisioning & Onboarding": {
        "keywords": ["onboarding", "new joiner", "provision", "create user", "new hire",
                     "termination", "offboarding", "access request", "role", "permission"],
        "icon": "👤",
        "color": "#8B5CF6",
        "what": "New user account creation, access provisioning, or offboarding requests",
        "why": "Manual provisioning process across multiple systems",
        "impact_template": "{can_automate} provisioning requests handled manually, costing ₹{monthly_cost}L/month",
        "solution": "Self-Service Portal",
        "solution_detail": "Deploy automated provisioning workflow with approval routing",
        "implementation": "6-8 weeks",
        "investment": "₹20-30L",
    },
    "Application Errors": {
        "keywords": ["application", "error", "exception", "crash", "bug", "issue", "incident",
                     "app", "software", "code", "deployment", "release"],
        "icon": "🐛",
        "color": "#DC2626",
        "what": "Application-level errors, exceptions, or functional issues",
        "why": "Code bugs, configuration issues, or integration failures",
        "impact_template": "{can_automate} app errors need developer investigation, costing ₹{monthly_cost}L/month",
        "solution": "Script/Runbook",
        "solution_detail": "Implement application health checks and automated diagnostic collection",
        "implementation": "4-6 weeks",
        "investment": "₹10-15L",
    },
    "Certificate & Security": {
        "keywords": ["certificate", "ssl", "tls", "expired", "cert", "security", "vulnerability",
                     "patch", "antivirus", "firewall", "compliance"],
        "icon": "🔒",
        "color": "#059669",
        "what": "SSL certificate expiry, security patches, or compliance alerts",
        "why": "Manual certificate management and patch tracking",
        "impact_template": "{can_automate} security items need manual tracking, costing ₹{monthly_cost}L/month",
        "solution": "Auto-Remediation",
        "solution_detail": "Deploy certificate auto-renewal and automated patch management",
        "implementation": "4-6 weeks",
        "investment": "₹12-18L",
    },
    "Hardware & Infrastructure": {
        "keywords": ["hardware", "server", "physical", "rack", "power", "cooling", "fan",
                     "temperature", "ups", "pdu", "chassis", "blade"],
        "icon": "🖥️",
        "color": "#78716C",
        "what": "Physical hardware alerts including power, cooling, and component failures",
        "why": "Aging infrastructure or environmental issues",
        "impact_template": "{can_automate} hardware alerts need datacenter response, costing ₹{monthly_cost}L/month",
        "solution": "Manual Process",
        "solution_detail": "Physical intervention required - focus on predictive alerting",
        "implementation": "N/A",
        "investment": "N/A",
    },
    "Scheduled Maintenance": {
        "keywords": ["maintenance", "scheduled", "planned", "change", "window", "patching",
                     "upgrade", "migration", "reboot", "restart"],
        "icon": "🔧",
        "color": "#6B7280",
        "what": "Scheduled maintenance activities and planned changes",
        "why": "Regular maintenance windows for updates and patches",
        "impact_template": "{can_automate} maintenance tickets created manually, costing ₹{monthly_cost}L/month",
        "solution": "Existing Automation",
        "solution_detail": "Already part of change management - optimize scheduling",
        "implementation": "N/A",
        "investment": "N/A",
    },
    "External/Vendor Issues": {
        "keywords": ["external", "vendor", "third party", "itsm", "incident#", "reference",
                     "partner", "supplier", "sla", "escalation"],
        "icon": "🤝",
        "color": "#0EA5E9",
        "what": "Issues requiring external vendor or third-party involvement",
        "why": "Dependencies on external service providers",
        "impact_template": "{can_automate} tickets need vendor coordination, costing ₹{monthly_cost}L/month",
        "solution": "Script/Runbook",
        "solution_detail": "Automate vendor ticket creation and SLA tracking",
        "implementation": "3-4 weeks",
        "investment": "₹8-12L",
    },
}

# Default category for unmatched clusters
DEFAULT_CATEGORY = {
    "name": "Other IT Issues",
    "icon": "📋",
    "color": "#9CA3AF",
    "what": "Miscellaneous IT support requests and issues",
    "why": "Various IT issues requiring case-by-case analysis",
    "impact_template": "{can_automate} tickets need manual review, costing ₹{monthly_cost}L/month",
    "solution": "Manual Process",
    "solution_detail": "Requires analysis to identify automation opportunities",
    "implementation": "TBD",
    "investment": "TBD",
}


def classify_cluster(keywords: List[str], sample_descriptions: List[str] = None) -> Dict:
    """
    Classify a cluster into a business category based on keywords.
    
    Args:
        keywords: List of top keywords from the cluster
        sample_descriptions: Optional list of sample ticket descriptions
    
    Returns:
        Dictionary with category info and story template
    """
    # Normalize keywords
    keyword_set = set(word.lower().strip() for word in keywords if word)
    
    # Sub-label detection for more specific naming
    SUB_LABELS = {
        "Password & Access Requests": [
            (["ims", "pin", "racf"], "IMS/RACF"),
            (["vpn"], "VPN"),
            (["domain", "ad", "ldap"], "Domain/AD"),
            (["gui", "application"], "Application"),
            (["outlook", "email"], "Email"),
            (["sso", "mfa"], "SSO/MFA"),
        ],
        "Batch Job Failures": [
            (["mvs", "mainframe", "jcl"], "Mainframe"),
            (["opc", "twsz", "ctrl-m"], "Scheduler"),
            (["etl", "data"], "ETL"),
        ],
        "Service Health Issues": [
            (["windows"], "Windows"),
            (["linux", "unix"], "Linux"),
            (["sql", "database"], "Database"),
        ],
    }
    
    # Also extract keywords from sample descriptions if provided
    if sample_descriptions:
        for desc in sample_descriptions[:10]:
            if desc:
                words = desc.lower().split()
                keyword_set.update(w for w in words if len(w) > 3)
    
    best_match = None
    best_score = 0
    
    for category_name, config in BUSINESS_CATEGORIES.items():
        category_keywords = set(k.lower() for k in config["keywords"])
        
        # Calculate match score (intersection count + weighted by specificity)
        intersection = keyword_set & category_keywords
        score = len(intersection)
        
        # Bonus for highly specific keywords
        specific_keywords = {"eqqe", "racf", "ims", "tablespace", "netbackup", "veeam"}
        specific_matches = intersection & specific_keywords
        score += len(specific_matches) * 2
        
        if score > best_score:
            best_score = score
            best_match = category_name
    
    # Return match or default
    if best_score >= 1 and best_match:
        config = BUSINESS_CATEGORIES[best_match]
        
        # Determine sub-label for more specific naming
        sub_label = ""
        if best_match in SUB_LABELS:
            for sub_keywords, label in SUB_LABELS[best_match]:
                if any(sk in keyword_set for sk in sub_keywords):
                    sub_label = f" - {label}"
                    break
        
        return {
            "name": best_match + sub_label,
            "confidence": min(best_score * 20, 95),  # Cap at 95%
            "icon": config["icon"],
            "color": config["color"],
            "what": config["what"],
            "why": config["why"],
            "impact_template": config["impact_template"],
            "solution": config["solution"],
            "solution_detail": config["solution_detail"],
            "implementation": config["implementation"],
            "investment": config["investment"],
        }
    else:
        return {
            "name": DEFAULT_CATEGORY["name"],
            "confidence": 30,
            **DEFAULT_CATEGORY,
        }


def generate_cluster_story(
    category: Dict,
    ticket_count: int,
    can_automate: int,
    already_automated: int,
    hours_saved: float,
    months: float = 1.0
) -> Dict:
    """
    Generate a complete story for a cluster.
    
    Args:
        category: Category dict from classify_cluster()
        ticket_count: Total tickets in cluster
        can_automate: Tickets that can be automated
        already_automated: Tickets already automated
        hours_saved: Estimated hours saved over the whole dump (unused; kept for callers)
        months: Months the dump covers, to turn totals into monthly figures
    
    Returns:
        Complete story dict for CXO presentation
    """
    savings = automation_savings(can_automate, months)
    monthly_cost = round(savings["monthly_savings_inr"] / 100000, 2)  # In Lakhs
    annual_cost = round(savings["annual_savings_inr"] / 100000, 1)
    
    # Calculate ROI
    investment_str = category.get("investment", "TBD")
    if investment_str and investment_str != "TBD" and investment_str != "N/A":
        # Parse investment range (e.g., "₹15-20L" -> average 17.5)
        try:
            nums = [int(n) for n in investment_str.replace("₹", "").replace("L", "").split("-")]
            avg_investment = sum(nums) / len(nums)
            payback_months = round(avg_investment / monthly_cost, 1) if monthly_cost > 0 else 0
            roi_percent = round((annual_cost / avg_investment) * 100, 0) if avg_investment > 0 else 0
        except:
            payback_months = 0
            roi_percent = 0
    else:
        payback_months = 0
        roi_percent = 0
    
    # Format impact
    impact = category["impact_template"].format(
        can_automate=f"{can_automate:,}",
        monthly_cost=monthly_cost
    )
    
    return {
        # Category info
        "name": category["name"],
        "icon": category["icon"],
        "color": category["color"],
        "confidence": category["confidence"],
        
        # Story
        "what": category["what"],
        "why": category["why"],
        "impact": impact,
        
        # Numbers
        "ticket_count": ticket_count,
        "can_automate": can_automate,
        "already_automated": already_automated,
        "manual_only": ticket_count - can_automate - already_automated,
        "automation_pct": round((can_automate + already_automated) / ticket_count * 100, 1) if ticket_count > 0 else 0,
        
        # Savings
        "hours_saved_monthly": savings["hours_saved_monthly"],
        "monthly_savings_lakhs": monthly_cost,
        "annual_savings_lakhs": annual_cost,
        
        # Solution
        "solution": category["solution"],
        "solution_detail": category["solution_detail"],
        "implementation": category["implementation"],
        "investment": category["investment"],
        
        # ROI
        "payback_months": payback_months,
        "roi_percent": roi_percent,
    }


def get_all_categories() -> List[Dict]:
    """Get list of all available categories for reference"""
    return [
        {
            "name": name,
            "icon": config["icon"],
            "color": config["color"],
            "solution": config["solution"],
        }
        for name, config in BUSINESS_CATEGORIES.items()
    ]


# Test function
if __name__ == "__main__":
    # Test with sample cluster keywords
    test_cases = [
        ["password", "reset", "unlock", "pin", "ims"],
        ["failed", "batch", "eqqe036i", "mvs1", "job"],
        ["disk", "space", "95%", "logs", "volume"],
        ["cpu", "high", "workload", "memory", "threshold"],
        ["service", "stopped", "state", "restart"],
    ]
    
    for keywords in test_cases:
        result = classify_cluster(keywords)
        print(f"Keywords: {keywords}")
        print(f"  → {result['icon']} {result['name']} ({result['confidence']}% confidence)")
        print(f"  → Solution: {result['solution']}")
        print()