"""
automation_config.py
--------------------
Central configuration for automation classification.
All patterns, keywords, thresholds in ONE place.
Easy to update without touching logic.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MTTR THRESHOLDS (in minutes)
# ═══════════════════════════════════════════════════════════════════════════════

MTTR_THRESHOLDS = {
    'auto_fast': 15,        # < 15 min = truly automated
    'auto_medium': 30,      # 15-30 min = likely automated
    'scriptable': 60,       # < 60 min human = can be scripted
    'routine': 120,         # < 2 hours = routine work
    'complex': 240,         # > 4 hours = complex
}

# ═══════════════════════════════════════════════════════════════════════════════
# COMPLEXITY THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

COMPLEXITY_THRESHOLDS = {
    'reassignment_complex': 3,      # >= 3 reassignments = complex
    'reassignment_moderate': 2,     # 2 reassignments = moderate
    'reopen_complex': 2,            # >= 2 reopens = quality issue
    'work_notes_long': 500,         # > 500 chars = investigation
    'work_notes_very_long': 1000,   # > 1000 chars = deep investigation
}

# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING TOOLS (Create tickets automatically)
# ═══════════════════════════════════════════════════════════════════════════════

MONITORING_TOOLS = [
    # Generic
    'sciencelogic', 'netcool', 'solarwinds', 'nagios', 'zabbix', 'datadog',
    'dynatrace', 'appdynamics', 'splunk', 'prometheus', 'grafana', 'pagerduty',
    'opsgenie', 'newrelic', 'thousandeyes', 'catchpoint',
    
    # ServiceNow specific
    'event management', 'monitoring', 'automated alert', 'system alert',
    'automated id', 'integration user', 'discovery', 'orchestration',
    
    # Cloud
    'cloudwatch', 'azure monitor', 'stackdriver', 'gcp monitoring',
]

# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION RESOLVERS (Close tickets automatically)
# ═══════════════════════════════════════════════════════════════════════════════

AUTOMATION_RESOLVERS = [
    # Generic automation
    'automated', 'automation', 'auto-', 'autobot', 'bot', 'script',
    'system', 'integration', 'orchestration', 'workflow',
    
    # Specific tools
    'ignio', 'netcool', 'ansible', 'puppet', 'chef', 'terraform',
    'jenkins', 'rundeck', 'stackstorm', 'servicenow flow',
    
    # Account patterns
    'svc-', 'svc_', 'service account', 'scheduled task', 'cron',
    'external tool', 'api user', 'batch',
    
    # Vendor specific
    'verizon proactive', 'ibm automation', 'dxc automation',
]

# ═══════════════════════════════════════════════════════════════════════════════
# SELF-HEALING PATTERNS (In resolution notes)
# ═══════════════════════════════════════════════════════════════════════════════

SELF_HEAL_PATTERNS = [
    # Threshold based
    'below threshold', 'under threshold', 'within threshold',
    'threshold normalized', 'back to normal', 'currently normal',
    
    # Auto resolution
    'auto-resolved', 'auto resolved', 'resolved automatically',
    'self-healed', 'self healed', 'auto-closed', 'auto closed',
    
    # No action needed
    'no action required', 'no action needed', 'no action taken',
    'resolved itself', 'cleared automatically', 'recovered',
    
    # Alert specific
    'alert cleared', 'alert resolved', 'no longer occurring',
    'issue no longer exists', 'normalized', 'stabilized',
]

# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION WORK PATTERNS (In work notes - automation attempted)
# ═══════════════════════════════════════════════════════════════════════════════

AUTOMATION_WORK_PATTERNS = [
    'ignio is working', 'ignio integration', 'ignio executed',
    'automation executed', 'script executed', 'runbook executed',
    'bot processed', 'workflow triggered', 'auto-remediation',
    'ansible playbook', 'puppet applied', 'chef recipe',
]

# ═══════════════════════════════════════════════════════════════════════════════
# HUMAN INVESTIGATION PATTERNS (In work notes - human did work)
# ═══════════════════════════════════════════════════════════════════════════════

HUMAN_INVESTIGATION_PATTERNS = [
    # Analysis
    'investigated', 'investigation', 'analyzed', 'analysis',
    'troubleshoot', 'troubleshooting', 'diagnosed', 'diagnosis',
    'root cause', 'rca', 'found that', 'identified',
    
    # Communication
    'checked with', 'confirmed with', 'spoke to', 'spoke with',
    'called', 'contacted', 'coordinated', 'discussed',
    
    # Actions
    'escalated to', 'escalated', 'vendor involved', 'third party',
    'manual intervention', 'manually', 'restarted manually',
    'applied fix', 'patched', 'reconfigured', 'rebuilt',
]

# ═══════════════════════════════════════════════════════════════════════════════
# SIMPLE RESOLUTION PATTERNS (In resolution notes - can be automated)
# ═══════════════════════════════════════════════════════════════════════════════

SIMPLE_RESOLUTION_PATTERNS = [
    # Restarts
    'restarted service', 'service restarted', 'restart service',
    'rebooted', 'reboot', 'bounced', 'recycled',
    
    # Cleanup
    'cleared disk', 'disk cleanup', 'cleared space', 'freed space',
    'cleared cache', 'cache cleared', 'cleared logs', 'log cleanup',
    'deleted old files', 'archived files', 'purged',
    
    # Reset/Unlock
    'reset password', 'password reset', 'unlocked account',
    'account unlocked', 'reset credentials', 'access granted',
    
    # Process
    'killed process', 'process killed', 'terminated process',
    'stopped service', 'started service',
    
    # Standard fixes
    'applied patch', 'patched', 'updated', 'upgraded',
    'renewed certificate', 'certificate renewed',
    'restored backup', 'backup restored',
]

# ═══════════════════════════════════════════════════════════════════════════════
# COMPLEX RESOLUTION PATTERNS (In resolution notes - manual only)
# ═══════════════════════════════════════════════════════════════════════════════

COMPLEX_RESOLUTION_PATTERNS = [
    # Investigation
    'after investigation', 'after analysis', 'root cause was',
    'found the issue', 'identified the problem',
    
    # External
    'escalated to vendor', 'vendor fix', 'third party',
    'awaiting vendor', 'vendor confirmed',
    
    # Development
    'code fix', 'code change', 'deployed fix', 'hotfix',
    'design change', 'architecture change',
    
    # Complex actions
    'data recovery', 'data corruption', 'hardware replacement',
    'hardware failure', 'network reconfiguration',
    'security incident', 'security review',
    
    # Approvals
    'awaiting approval', 'change request', 'cab approval',
]

# ═══════════════════════════════════════════════════════════════════════════════
# EXCLUSION PATTERNS (Not real tickets)
# ═══════════════════════════════════════════════════════════════════════════════

EXCLUSION_RESOLUTION_CODES = [
    'cancelled', 'canceled', 'duplicate', 'withdrawn',
    'rejected', 'invalid', 'user error', 'no fault found',
    'not reproducible', 'no action required', 'false alarm',
]

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_CHANNELS = [
    'event management', 'monitoring', 'api', 'integration',
    'automated', 'discovery', 'orchestration', 'alert',
]

MANUAL_CHANNELS = [
    'phone', 'walk-in', 'chat', 'in person',
]

SELF_SERVICE_CHANNELS = [
    'self-service', 'portal', 'email', 'web',
]

# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_CATEGORIES = [
    'automated alerts', 'monitoring event', 'event management',
    'automated', 'system generated',
]

SELF_SERVICE_CATEGORIES = [
    'password', 'access', 'user administration', 'account',
    'vpn', 'permissions', 'unlock',
]

INFRASTRUCTURE_CATEGORIES = [
    'server', 'storage', 'backup', 'database', 'network',
    'compute', 'linux', 'windows', 'unix', 'vmware',
]

# ═══════════════════════════════════════════════════════════════════════════════
# SHORT DESCRIPTION PATTERNS (For solution lever detection)
# ═══════════════════════════════════════════════════════════════════════════════

SHORT_DESC_PATTERNS = {
    'Self-Service Portal': [
        'password', 'reset password', 'forgot password', 'change password',
        'account locked', 'unlock account', 'locked out',
        'access request', 'request access', 'vpn access',
        'new user', 'create user', 'onboard',
    ],
    'Auto-Remediation': [
        'disk space', 'disk full', 'low disk', 'high space used',
        'memory', 'high memory', 'out of memory', 'memory utilization',
        'cpu', 'high cpu', 'cpu utilization', 'cpu exceeded',
        'threshold', 'alert', 'monitoring',
    ],
    'Script/Runbook': [
        'restart', 'reboot', 'bounce', 'recycle',
        'service down', 'service not running', 'service stopped',
        'clear cache', 'clear logs', 'cleanup',
        'certificate expir', 'cert expir', 'ssl expir',
        'backup failed', 'backup failure', 'restore',
        'job failed', 'batch failed', 'scheduled task',
    ],
    'RPA': [
        'install software', 'software install', 'application install',
        'provision', 'onboard', 'offboard', 'new hire',
        'update', 'upgrade', 'patch',
    ],
    'Chatbot': [
        'how to', 'how do i', 'help with', 'question about',
        'information', 'inquiry', 'status of',
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# TOOL RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_RECOMMENDATIONS = {
    'Self-Healing': {
        'tools': ['Ignio', 'Netcool', 'Dynatrace', 'AppDynamics', 'Moogsoft'],
        'effort': 'Already Implemented',
        'description': 'Infrastructure auto-recovers without human intervention',
    },
    'Auto-Remediation': {
        'tools': ['Ignio', 'Ansible', 'StackStorm', 'Rundeck', 'SaltStack'],
        'effort': 'Low (1-2 weeks)',
        'description': 'Add auto-fix scripts to monitoring alerts',
    },
    'Self-Service Portal': {
        'tools': ['ServiceNow Portal', 'BMC Helix', 'Freshservice', 'Custom Portal'],
        'effort': 'Medium (2-4 weeks)',
        'description': 'User can perform action without IT involvement',
    },
    'Script/Runbook': {
        'tools': ['Ansible', 'PowerShell', 'Python', 'Bash', 'Rundeck'],
        'effort': 'Low (1-2 weeks)',
        'description': 'Automated script to perform repetitive task',
    },
    'RPA': {
        'tools': ['UiPath', 'Automation Anywhere', 'Blue Prism', 'Power Automate'],
        'effort': 'Medium (2-4 weeks)',
        'description': 'Bot performs UI-based repetitive tasks',
    },
    'Chatbot': {
        'tools': ['ServiceNow Virtual Agent', 'IBM Watson', 'Microsoft Copilot'],
        'effort': 'Medium (3-6 weeks)',
        'description': 'AI-powered self-service for user queries',
    },
    'Automation Tuning': {
        'tools': ['Existing Tool Optimization'],
        'effort': 'Low (1 week)',
        'description': 'Existing automation needs configuration improvement',
    },
    'Monitoring Optimization': {
        'tools': ['Alert Rule Tuning', 'Threshold Adjustment', 'Noise Reduction'],
        'effort': 'Low (1 week)',
        'description': 'Reduce false alerts and noise',
    },
    'Manual Process': {
        'tools': ['N/A'],
        'effort': 'N/A',
        'description': 'Complex work requiring human judgment',
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# ASSIGNMENT GROUP PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_ASSIGNMENT_GROUPS = [
    'automation', 'netcool', 'integration', 'orchestration',
    'monitoring', 'event management',
]

L1_ASSIGNMENT_GROUPS = [
    'service desk', 'helpdesk', 'l1', 'level 1', 'first line',
]

L3_ASSIGNMENT_GROUPS = [
    'l3', 'level 3', 'architect', 'specialist', 'expert',
    'vendor', 'external', 'security',
]