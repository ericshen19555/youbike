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


def format_rrule_for_display(rrule_str: str) -> str:
    """
    Convert an RRule string or custom 'ONCE:' format into a user-friendly Chinese string.
    """
    if not rrule_str:
        return "未知規則"

    # 1. Handle custom ONCE format
    if rrule_str.startswith("ONCE:"):
        dt_str = rrule_str[5:]
        try:
            dt = datetime.fromisoformat(dt_str)
            return f"單次提醒 ({dt.strftime('%m/%d %H:%M')})"
        except (ValueError, IndexError):
            return "單次提醒 (格式錯誤)"

    # 2. Handle standard RRule
    if "FREQ=" not in rrule_str:
        return f"規律提醒 ({rrule_str})"

    try:
        # Split into key-value pairs
        parts = {}
        for item in rrule_str.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                parts[k] = v
        
        # Day description
        byday = parts.get("BYDAY", "")
        days_map = {
            "MO": "一", "TU": "二", "WE": "三", "TH": "四", 
            "FR": "五", "SA": "六", "SU": "日"
        }
        
        # Check predefined patterns
        all_days = "MO,TU,WE,TH,FR,SA,SU"
        weekdays = "MO,TU,WE,TH,FR"
        weekends = "SA,SU"
        
        # Sort incoming days to match canonical order for comparison
        target_days_set = set(byday.split(","))
        
        if target_days_set == set(all_days.split(",")):
            day_desc = "每天"
        elif target_days_set == set(weekdays.split(",")):
            day_desc = "平日 (一至五)"
        elif target_days_set == set(weekends.split(",")):
            day_desc = "週末 (六日)"
        else:
            found_names = []
            for code in ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]:
                if code in target_days_set:
                    found_names.append(days_map[code])
            day_desc = f"每週{','.join(found_names)}"
            
        # Time description
        hour = int(parts.get("BYHOUR", 0))
        minute = int(parts.get("BYMINUTE", 0))
        time_desc = f"{hour:02d}:{minute:02d}"
        
        return f"{day_desc} {time_desc}"
    except Exception:
        return f"規律提醒 ({rrule_str})"

