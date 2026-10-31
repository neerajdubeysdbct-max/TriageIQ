"""
Cluster Intelligence API — Deep BERT cluster analysis for RFP storytelling.

Provides:
- Cluster naming from ticket descriptions
- Problem statements per cluster
- Solution recommendations with ROI
- Team mapping from assignment_group
- Trend analysis from opened dates
- Full drill-down data
"""

from fastapi import APIRouter, Depends, HTTPException
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import re
import math
from sqlalchemy import func
# Import from your existing project structure
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import SessionLocal, Ticket, Upload
from dependencies import get_current_user, require_upload_access

router = APIRouter(prefix="/api/cluster-intelligence", tags=["Cluster Intelligence"])

# ── Stop words for keyword extraction ──
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "up",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "as", "until", "while", "and", "but", "or", "if",
    "this", "that", "these", "those", "it", "its", "i", "me", "my", "we",
    "our", "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "their", "what", "which", "who", "whom", "when", "where", "inc", "ticket",
    "issue", "problem", "error", "request", "please", "help", "unable", "not",
    "working", "work", "user", "system", "server", "service", "application",
    "null", "none", "n/a", "na", "", "-", "--",
}

# ── Solution mapping based on automation type ──
SOLUTION_MAP = {
    "Self-Service Portal": {
        "solution": "Self-Service Portal with Knowledge Base",
        "effort": "Medium",
        "timeline": "Q2",
        "reduction_pct": 75,
    },
    "Automation Tuning": {
        "solution": "Automation Tuning & Optimization",
        "effort": "Low",
        "timeline": "Q1",
        "reduction_pct": 85,
    },
    "Auto-Remediation": {
        "solution": "Auto-Remediation Scripts with AIOps",
        "effort": "Low",
        "timeline": "Q1",
        "reduction_pct": 90,
    },
    "Script/Runbook": {
        "solution": "Automated Runbook Execution",
        "effort": "Low",
        "timeline": "Q1",
        "reduction_pct": 80,
    },
    "RPA": {
        "solution": "Robotic Process Automation Bot",
        "effort": "Medium",
        "timeline": "Q2",
        "reduction_pct": 70,
    },
    "Chatbot/Virtual Agent": {
        "solution": "AI Chatbot with NLP",
        "effort": "Medium",
        "timeline": "Q2",
        "reduction_pct": 65,
    },
}



def extract_keywords(descriptions: list[str], top_n: int = 8) -> list[str]:
    """Extract top keywords from ticket descriptions."""
    word_counts: Counter = Counter()
    for desc in descriptions:
        if not desc:
            continue
        words = re.findall(r'[a-zA-Z0-9_-]+', desc.lower())
        for w in words:
            if w not in STOP_WORDS and len(w) > 2 and not w.isdigit():
                word_counts[w] += 1
    return [w for w, _ in word_counts.most_common(top_n)]


def generate_cluster_name(keywords: list[str], assignment_groups: list[str]) -> str:
    """Generate a human-readable cluster name from keywords and teams."""
    if not keywords:
        return "Miscellaneous Issues"

    # Try to build a meaningful name from top 2-3 keywords
    name_parts = []
    for kw in keywords[:3]:
        name_parts.append(kw.replace("_", " ").replace("-", " ").title())

    return " / ".join(name_parts)


def map_team(assignment_groups: list[tuple[str, int]]) -> str:
    """Map assignment groups to team category."""
    if not assignment_groups:
        return "Unassigned"

    top_group = assignment_groups[0][0].lower() if assignment_groups else ""

    if any(x in top_group for x in ["network", "nw-", "nw_", "wan", "lan", "dns", "firewall"]):
        return "Network Operations"
    elif any(x in top_group for x in ["desktop", "euc", "end user", "laptop", "workstation"]):
        return "End User Computing"
    elif any(x in top_group for x in ["server", "unix", "linux", "windows", "vmware", "compute"]):
        return "Server & Infrastructure"
    elif any(x in top_group for x in ["service desk", "sd-", "sd_", "helpdesk", "help desk"]):
        return "Service Desk"
    elif any(x in top_group for x in ["database", "db-", "db_", "sql", "oracle"]):
        return "Database Administration"
    elif any(x in top_group for x in ["security", "iam", "identity", "access"]):
        return "Security & IAM"
    elif any(x in top_group for x in ["storage", "backup", "san", "nas"]):
        return "Storage & Backup"
    elif any(x in top_group for x in ["middleware", "mq", "websphere", "jboss"]):
        return "Middleware"
    elif any(x in top_group for x in ["email", "exchange", "o365", "office"]):
        return "Messaging & Collaboration"
    elif any(x in top_group for x in ["batch", "scheduler", "autosys", "cron"]):
        return "Batch Operations"
    else:
        return "IT Operations"


@router.get("/{upload_id}")
async def get_cluster_intelligence(
    upload_id: int,
    user: dict = Depends(require_upload_access),
):
    """Full BERT cluster intelligence for RFP storytelling."""
    db = SessionLocal()
    try:
        # Verify upload
        upload = db.query(Upload).filter(
            Upload.id == upload_id,
            Upload.team_id == user["team_id"]
        ).first()
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")

        # Get all tickets with cluster assignments
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
        ).all()

        if not tickets:
            raise HTTPException(status_code=404, detail="No clustered tickets found")

        total_tickets = len(tickets)

        # ── Group tickets by cluster ──
        clusters_data: dict = defaultdict(list)
        for t in tickets:
            clusters_data[t.cluster_id].append(t)

        # ── Build intelligence for each cluster ──
        cluster_results = []
        total_annual_savings = 0
        team_summary: dict = defaultdict(lambda: {
            "clusters": [], "ticket_count": 0, "total_mttr_hours": 0,
            "automatable": 0, "savings": 0
        })

        # Calculate overall dataset date range for annualization
        first_ticket_date = db.query(func.min(Ticket.opened)).filter(
            Ticket.upload_id == upload_id
        ).scalar()
        last_ticket_date = db.query(func.max(Ticket.opened)).filter(
            Ticket.upload_id == upload_id
        ).scalar()
        if first_ticket_date and last_ticket_date and last_ticket_date != first_ticket_date:
            overall_data_days = max((last_ticket_date - first_ticket_date).days, 1)
        else:
            overall_data_days = 365

        for cluster_id in sorted(clusters_data.keys()):
            ctix = clusters_data[cluster_id]
            count = len(ctix)
            pct_of_total = round(count / total_tickets * 100, 1)

            # ── Keywords ──
            descriptions = [t.short_description or "" for t in ctix]
            keywords = extract_keywords(descriptions)

            # ── Assignment group distribution ──
            ag_counts: Counter = Counter()
            for t in ctix:
                ag = t.assignment_group or "Unknown"
                ag_counts[ag] += 1
            top_groups = ag_counts.most_common(5)
            team = map_team(top_groups)

            # ── Cluster name ──
            cluster_name = generate_cluster_name(keywords, [g[0] for g in top_groups])

            # ── MTTR stats ──
            mttrs = [t.mttr_hours for t in ctix if t.mttr_hours and t.mttr_hours > 0]
            avg_mttr = round(sum(mttrs) / len(mttrs), 2) if mttrs else 0
            total_mttr = sum(mttrs) if mttrs else 0

            # ── Priority distribution ──
            pri_counts: Counter = Counter()
            for t in ctix:
                pri_counts[t.priority or "Unknown"] += 1

            # ── Automation stats ──
            auto_status: Counter = Counter()
            solution_levers: Counter = Counter()
            for t in ctix:
                auto_status[t.aiops_automation_status or "Unknown"] += 1
                if t.aiops_solution_lever:
                    solution_levers[t.aiops_solution_lever] += 1

            already_automated = auto_status.get("Already Automated", 0)
            can_automate = auto_status.get("Can Automate", 0) + auto_status.get("Can Be Automated", 0)
            manual_only = auto_status.get("Manual Only", 0) + auto_status.get("Manual", 0)
            automatable_pct = round((can_automate + already_automated) / max(count, 1) * 100, 1)

            # ── Top solution lever ──
            top_solution = solution_levers.most_common(1)[0][0] if solution_levers else "Manual"
            solution_info = SOLUTION_MAP.get(top_solution, {
                "solution": "Process Optimization",
                "effort": "Medium",
                "timeline": "Q2",
                "reduction_pct": 50,
            })

             # ── ROI calculation (Cost Per Ticket model) ──
            cluster_current_cost = 0
            cluster_post_auto_cost = 0
            
            for t in ctix:
                ra = getattr(t, 'reassignment_count', 0) or 0
                ro = getattr(t, 'reopen_count', 0) or 0
                mt = getattr(t, 'mttr_hours', 0) or 0
                auto = getattr(t, 'is_already_automated', False)
                
                # Classify complexity
                if auto:
                    base = 100
                elif ra >= 2 or ro >= 1 or mt > 48:
                    base = 2500
                elif ra >= 1 or mt > 8:
                    base = 900
                else:
                    base = 500
                
                # Add waste costs
                total = base + (ra * 700) + (ro * 900)
                cluster_current_cost += total
                
                # Post-automation cost
                if getattr(t, 'can_be_automated', False) or (getattr(t, 'automation_potential_score', 0) or 0) > 60:
                    cluster_post_auto_cost += 120
                else:
                    cluster_post_auto_cost += total
            
            # Annualize
            if overall_data_days > 60:
                ann = 365 / overall_data_days
            else:
                ann = 1.0
            
            annual_cost = round(cluster_current_cost * ann)
            savings = round((cluster_current_cost - cluster_post_auto_cost) * ann)
            total_annual_savings += savings

            # ── Monthly trend ──
            monthly: dict = defaultdict(int)
            for t in ctix:
                if t.opened:
                    key = t.opened.strftime("%Y-%m")
                    monthly[key] += 1
            monthly_trend = [{"month": k, "count": v} for k, v in sorted(monthly.items())]

            # Trend direction
            if len(monthly_trend) >= 3:
                recent_avg = sum(m["count"] for m in monthly_trend[-3:]) / 3
                earlier_avg = sum(m["count"] for m in monthly_trend[:3]) / 3
                if recent_avg > earlier_avg * 1.15:
                    trend = "increasing"
                elif recent_avg < earlier_avg * 0.85:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # ── Reassignment & reopen stats ──
            reassignments = [t.reassignment_count or 0 for t in ctix]
            reopens = [t.reopen_count or 0 for t in ctix]
            avg_reassign = round(sum(reassignments) / max(len(reassignments), 1), 1)
            avg_reopen = round(sum(reopens) / max(len(reopens), 1), 2)

            # ── Sample tickets ──
            samples = []
            for t in ctix[:5]:
                samples.append({
                    "ticket_id": t.ticket_number or str(t.id),
                    "short_description": t.short_description or "",
                    "priority": t.priority or "",
                    "mttr_hours": t.mttr_hours,
                    "assignment_group": t.assignment_group or "",
                    "automation_status": t.aiops_automation_status or "",
                })

            # ── Problem statement ──
            top_keyword_str = ", ".join(keywords[:4]) if keywords else "various issues"
            daily_volume = round(count / max((ctix[-1].opened - ctix[0].opened).days, 1)) if ctix[0].opened and ctix[-1].opened and ctix[-1].opened != ctix[0].opened else round(count / 365)

            problem_statement = (
                f"{count:,} tickets related to {top_keyword_str}. "
                f"Averaging {daily_volume} tickets/day with {avg_mttr}h mean resolution time. "
                f"{avg_reassign} avg reassignments per ticket."
            )

            if avg_reassign > 2:
                problem_statement += f" High reassignment rate indicates routing/knowledge issues."
            if avg_mttr > 24:
                problem_statement += f" Resolution time significantly exceeds 24h target."

            # ── Impact statement ──
            annual_cost_lakhs = round(annual_cost / 100000, 1)
            impact_statement = f"₹{annual_cost_lakhs}L annual cost (₹{round(savings / 100000, 1)}L potential savings/year)"

            # ── Build result ──
            cluster_result = {
                "cluster_id": cluster_id,
                "cluster_name": cluster_name,
                "ticket_count": count,
                "pct_of_total": pct_of_total,
                "team": team,
                "keywords": keywords,
                "problem_statement": problem_statement,
                "impact": impact_statement,
                "annual_cost": annual_cost,
                "annual_cost_lakhs": annual_cost_lakhs,
                "solution": {
                    "name": solution_info["solution"],
                    "type": top_solution,
                    "effort": solution_info["effort"],
                    "timeline": solution_info["timeline"],
                    "reduction_pct": solution_info["reduction_pct"],
                    "annual_savings": savings,
                    "annual_savings_lakhs": round(savings / 100000, 1),
                },
                "mttr": {
                    "avg_hours": avg_mttr,
                    "total_hours": round(total_mttr, 1),
                    "ticket_count_with_mttr": len(mttrs),
                },
                "automation": {
                    "already_automated": already_automated,
                    "can_automate": can_automate,
                    "manual_only": manual_only,
                    "automatable_pct": automatable_pct,
                    "top_solution_lever": top_solution,
                },
                "quality": {
                    "avg_reassignments": avg_reassign,
                    "avg_reopens": avg_reopen,
                },
                "priority_distribution": dict(pri_counts.most_common()),
                "assignment_groups": [{"group": g, "count": c} for g, c in top_groups],
                "trend": trend,
                "monthly_trend": monthly_trend,
                "sample_tickets": samples,
            }
            cluster_results.append(cluster_result)

            # ── Aggregate to team summary ──
            team_summary[team]["clusters"].append(cluster_id)
            team_summary[team]["ticket_count"] += count
            team_summary[team]["total_mttr_hours"] += total_mttr
            team_summary[team]["automatable"] += can_automate + already_automated
            team_summary[team]["savings"] += savings

        # ── Sort clusters by ticket count (largest first) ──
        cluster_results.sort(key=lambda x: x["ticket_count"], reverse=True)

        # ── Build team summary ──
        team_results = []
        for team_name, data in sorted(team_summary.items(), key=lambda x: x[1]["ticket_count"], reverse=True):
            team_results.append({
                "team": team_name,
                "cluster_count": len(data["clusters"]),
                "cluster_ids": data["clusters"],
                "ticket_count": data["ticket_count"],
                "pct_of_total": round(data["ticket_count"] / total_tickets * 100, 1),
                "total_mttr_hours": round(data["total_mttr_hours"], 1),
                "automatable_tickets": data["automatable"],
                "annual_savings_lakhs": round(data["savings"] / 100000, 1),
            })

        # ── t-SNE data for scatter plot ──
        tsne_points = []
        for t in tickets[:3000]:  # Limit for frontend performance
            if t.tsne_x is not None and t.tsne_y is not None:
                tsne_points.append({
                    "x": round(float(t.tsne_x), 2),
                    "y": round(float(t.tsne_y), 2),
                    "cluster_id": t.cluster_id,
                    "ticket_id": t.ticket_number or str(t.id),
                    "short_description": (t.short_description or "")[:80],
                })

        # ── CXO Summary ──
        top5_by_cost = sorted(cluster_results, key=lambda x: x["annual_cost"], reverse=True)[:5]
        total_savings_cr = round(total_annual_savings / 10000000, 1)

        cxo_summary = {
            "total_clusters": len(cluster_results),
            "total_tickets_analyzed": total_tickets,
            "total_annual_savings_cr": total_savings_cr,
            "top_5_problems": [
                {
                    "cluster_name": c["cluster_name"],
                    "ticket_count": c["ticket_count"],
                    "annual_cost_lakhs": c["annual_cost_lakhs"],
                    "solution": c["solution"]["name"],
                    "savings_lakhs": c["solution"]["annual_savings_lakhs"],
                    "effort": c["solution"]["effort"],
                }
                for c in top5_by_cost
            ],
            "quick_wins": [
                c for c in cluster_results
                if c["solution"]["effort"] == "Low" and c["solution"]["annual_savings"] > 100000
            ][:5],
            "headline": (
                f"Analysis of {total_tickets:,} tickets reveals {len(cluster_results)} distinct issue patterns. "
                f"Total automation potential: ₹{total_savings_cr}Cr/year. "
                f"Top 5 problems account for {sum(c['ticket_count'] for c in top5_by_cost):,} tickets "
                f"({round(sum(c['ticket_count'] for c in top5_by_cost) / total_tickets * 100)}% of total)."
            ),
        }

        return {
            "upload_id": upload_id,
            "model_info": {
                "name": "BERT Semantic Clustering",
                "model": "all-MiniLM-L6-v2",
                "dimensions": 768,
                "total_clusters": len(cluster_results),
                "total_tickets": total_tickets,
            },
            "cxo_summary": cxo_summary,
            "clusters": cluster_results,
            "team_summary": team_results,
            "tsne_data": tsne_points,
        }

    finally:
        db.close()


@router.get("/{upload_id}/cluster/{cluster_id}")
async def get_cluster_detail(
    upload_id: int,
    cluster_id: int,
    limit: int = 100,
    user: dict = Depends(require_upload_access),
):
    """Deep dive into a single cluster — all tickets with full details."""
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id == cluster_id,
        ).order_by(Ticket.opened.desc()).limit(limit).all()

        if not tickets:
            raise HTTPException(status_code=404, detail="No tickets found for this cluster")

        result_tickets = []
        for t in tickets:
            result_tickets.append({
                "ticket_id": t.ticket_number or str(t.id),
                "short_description": t.short_description or "",
                "priority": t.priority or "",
                "urgency": t.urgency or "",
                "impact": t.impact or "",
                "assignment_group": t.assignment_group or "",
                "mttr_hours": t.mttr_hours,
                "opened": t.opened.isoformat() if t.opened else None,
                "resolved": t.resolved.isoformat() if t.resolved else None,
                "channel": t.channel or "",
                "company": t.company or "",
                "business_unit": t.business_unit or "",
                "l1_category": t.l1_category or "",
                "l2_subcategory": t.l2_subcategory or "",
                "l3_automation_feasibility": t.l3_automation_feasibility or "",
                "l4_automation_type": t.l4_automation_type or "",
                "aiops_automation_status": t.aiops_automation_status or "",
                "aiops_solution_lever": t.aiops_solution_lever or "",
                "aiops_confidence": t.aiops_confidence,
                "automation_potential_score": t.automation_potential_score,
                "reassignment_count": t.reassignment_count or 0,
                "reopen_count": t.reopen_count or 0,
                "cluster_similarity": t.cluster_similarity,
                "tsne_x": float(t.tsne_x) if t.tsne_x else None,
                "tsne_y": float(t.tsne_y) if t.tsne_y else None,
            })

        return {
            "cluster_id": cluster_id,
            "total_tickets": len(result_tickets),
            "tickets": result_tickets,
        }

    finally:
        db.close()


@router.get("/{upload_id}/dynamic-chart")
async def get_dynamic_chart_data(
    upload_id: int,
    x_axis: str = "cluster_id",
    y_axis: str = "count",
    group_by: str = "",
    user: dict = Depends(require_upload_access),
):
    """
    Dynamic chart data generator.

    x_axis: cluster_id, priority, assignment_group, l1_category, channel, month
    y_axis: count, avg_mttr, total_mttr, automation_score, reassignment_count
    group_by: priority, assignment_group, automation_status (optional)
    """
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
        ).all()

        if not tickets:
            raise HTTPException(status_code=404, detail="No tickets found")

        # ── Build data groups ──
        groups: dict = defaultdict(lambda: defaultdict(list))

        for t in tickets:
            # Determine x value
            if x_axis == "cluster_id":
                x_val = str(t.cluster_id) if t.cluster_id is not None else "Unclustered"
            elif x_axis == "priority":
                x_val = t.priority or "Unknown"
            elif x_axis == "assignment_group":
                x_val = (t.assignment_group or "Unknown")[:30]
            elif x_axis == "l1_category":
                x_val = t.l1_category or "Unknown"
            elif x_axis == "channel":
                x_val = t.channel or "Unknown"
            elif x_axis == "month":
                x_val = t.opened.strftime("%Y-%m") if t.opened else "Unknown"
            else:
                x_val = str(getattr(t, x_axis, "Unknown"))

            # Determine group value
            if group_by:
                g_val = str(getattr(t, group_by, "Unknown") or "Unknown")
            else:
                g_val = "all"

            groups[x_val][g_val].append(t)

        # ── Compute y values ──
        chart_data = []
        for x_val, group_data in sorted(groups.items()):
            point = {"x": x_val}
            for g_val, g_tickets in group_data.items():
                if y_axis == "count":
                    point[g_val] = len(g_tickets)
                elif y_axis == "avg_mttr":
                    mttrs = [t.mttr_hours for t in g_tickets if t.mttr_hours]
                    point[g_val] = round(sum(mttrs) / max(len(mttrs), 1), 2)
                elif y_axis == "total_mttr":
                    mttrs = [t.mttr_hours for t in g_tickets if t.mttr_hours]
                    point[g_val] = round(sum(mttrs), 1)
                elif y_axis == "automation_score":
                    scores = [t.automation_potential_score for t in g_tickets if t.automation_potential_score]
                    point[g_val] = round(sum(scores) / max(len(scores), 1), 1)
                elif y_axis == "reassignment_count":
                    reassigns = [t.reassignment_count or 0 for t in g_tickets]
                    point[g_val] = round(sum(reassigns) / max(len(reassigns), 1), 2)
            chart_data.append(point)

        # Get unique group keys
        all_groups = set()
        for point in chart_data:
            all_groups.update(k for k in point.keys() if k != "x")

        return {
            "chart_data": chart_data,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "group_by": group_by or None,
            "groups": sorted(all_groups),
            "total_points": len(chart_data),
        }

    finally:
        db.close()
