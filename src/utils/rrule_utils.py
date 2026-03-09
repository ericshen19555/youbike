from datetime import datetime
from dateutil.rrule import rrulestr
from typing import Optional

def get_next_occurrence(rrule_str: str, after_dt: Optional[datetime] = None) -> Optional[datetime]:
    """
    Calculate the next occurrence of an RRule after a given datetime.
    """
    if after_dt is None:
        after_dt = datetime.now()
    
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
    pass
