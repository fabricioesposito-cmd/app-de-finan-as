"""Recurring savings targets, resolved without creating unlimited monthly rows."""
from app.planning import valid_month


def savings_plan(plans,schedules,month):
    valid_month(month)
    plan=dict(next((p for p in plans if p['month']==month),{}))
    eligible=[s for s in schedules if s['start_month']<=month]
    active=max(eligible,key=lambda s:s['start_month']) if eligible else None
    override=plan.get('savings_override',False)
    if active and not override:plan['savings_target_cents']=active['amount_cents']
    return plan,active,override
