import re
from typing import Optional, Tuple

def parse_natural_language_to_rrule(text: str) -> Optional[str]:
    """
    Very basic NLP-to-RRule parser for BikeGuard.
    Supports examples like:
    - "每週五 17:00"
    - "一到五 08:30"
    - "每天 22:00"
    """
    text = text.strip().lower()
    
    # 1. Day patterns
    day_map = {
        "一": "MO", "二": "TU", "三": "WE", "四": "TH", "五": "FR", "六": "SA", "日": "SU",
        "mon": "MO", "tue": "TU", "wed": "WE", "thu": "TH", "fri": "FR", "sat": "SA", "sun": "SU"
    }
    
    byday = ""
    if "每天" in text or "everyday" in text:
        byday = "MO,TU,WE,TH,FR,SA,SU"
    elif "平日" in text or "一到五" in text:
        byday = "MO,TU,WE,TH,FR"
    elif "週末" in text or "六日" in text:
        byday = "SA,SU"
    else:
        # Match individual days
        found_days = []
        for day_name, code in day_map.items():
            if day_name in text:
                found_days.append(code)
        if found_days:
            # deduplicate and sort if needed (not strictly required by rrule but good)
            byday = ",".join(list(set(found_days)))

    if not byday:
        byday = "MO,TU,WE,TH,FR,SA,SU" # Default to every day if no day specified
        
    # 2. Time Patterns (HH:MM)
    time_match = re.search(r'(\d{1,2})[:：](\d{1,2})', text)
    hour, minute = 0, 0
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        # Match "5點", "17點"
        hour_match = re.search(r'(\d{1,2})\s*點', text)
        if hour_match:
            hour = int(hour_match.group(1))
            
    # Handle AM/PM if "下午" or "晚上" is present
    if ("下午" in text or "晚上" in text or "pm" in text) and hour < 12:
        hour += 12
    elif ("早上" in text or "上午" in text or "am" in text) and hour == 12:
        hour = 0
        
    # Build RRule
    rrule = f"FREQ=WEEKLY;BYDAY={byday};BYHOUR={hour};BYMINUTE={minute}"
    return rrule

def test_parser():
    test_cases = [
        "每週五 17:00",
        "一到五 08:30",
        "每天 22:30",
        "週六日 早上 9點",
        "五 20:00"
    ]
    for tc in test_cases:
        print(f"'{tc}' -> {parse_natural_language_to_rrule(tc)}")

if __name__ == "__main__":
    test_parser()
