"""
Canonical ticket metrics. Every page that shows resolution time by automation
status reads it from here, so the numbers agree everywhere.

Definitions (tickets with a positive resolution time only):
  overall        all tickets
  automated      Already Automated (resolved by automation)
  human_handled  everything else: Can Be Automated + Manual Only
  can_automate   Can Be Automated (human-handled today, automatable)
  manual_only    Manual Only
"""

from typing import Dict

from sqlalchemy import and_, func

from models import Ticket


def mttr_by_status(db, upload_id: int, team_id: str) -> Dict:
    base = [Ticket.upload_id == upload_id, Ticket.team_id == team_id,
            Ticket.mttr_hours != None, Ticket.mttr_hours > 0]
    automated = Ticket.is_already_automated == True
    not_automated = func.coalesce(Ticket.is_already_automated, False) == False
    can = and_(not_automated, Ticket.can_be_automated == True)
    manual = and_(not_automated, func.coalesce(Ticket.can_be_automated, False) == False)

    def stat(*conds):
        avg, n = db.query(func.avg(Ticket.mttr_hours), func.count(Ticket.id)).filter(*base, *conds).first()
        return {"avg_hours": round(float(avg), 2) if avg is not None else None, "tickets": int(n)}

    out = {
        "overall": stat(),
        "automated": stat(automated),
        "human_handled": stat(not_automated),
        "can_automate": stat(can),
        "manual_only": stat(manual),
        "definitions": {
            "automated": "Already Automated tickets",
            "human_handled": "Can Be Automated + Manual Only tickets",
        },
    }
    a, h = out["automated"]["avg_hours"], out["human_handled"]["avg_hours"]
    # Plain comparison of two different ticket populations, not a measured saving
    out["human_to_automated_ratio"] = round(h / a, 1) if a and h else None
    return out
