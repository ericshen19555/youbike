from datetime import datetime
from dateutil.rrule import rrulestr
from typing import Optional

def get_next_occurrence(rrule_str: str, after_dt: Optional[datetime] = None) -> Optional[datetime]:
    """
    Calculate the next occurrence of an RRule after a given datetime.
    Supports standard RFC 5545 RRules and custom 'ONCE:ISO_DATETIME' format.
    """
    if after_dt is None:
        after_dt = datetime.now()
    
    # 1. Handle custom ONCE format
    if rrule_str.startswith("ONCE:"):
        try:
            target_dt = datetime.fromisoformat(rrule_str[5:])
            return target_dt if target_dt > after_dt else None
        except (ValueError, IndexError):
            return None

    # 2. Handle standard RRule
    try:
        rule = rrulestr(rrule_str)
        return rule.after(after_dt)
    except Exception:
        return None

def is_rrule_active_now(rrule_str: str, current_dt: Optional[datetime] = None) -> bool:
    """
    Checks if the current time matches an occurrence in the RRule.
    Note: For simplicity in this monitoring context, we usually check if we are 
    within a small window of an occurrence, or if the RRule defines a 'start' 
    time that we are currently monitoring for.
    
    Actually, for BikeGuard, Layer 1 will use get_next_occurrence to schedule 
    the first Layer 2 task.
    """
    # TODO: Implement real-time status check if needed for a "monitoring dashboard" feature.
    # Current architecture uses proactive scheduling (Layer 1 -> Task -> Layer 2).
    raise NotImplementedError("is_rrule_active_now is not implemented in the current proactive scheduling model.")

