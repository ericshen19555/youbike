from src.utils.rrule_utils import format_rrule_for_display

def test_format_once():
    # Test valid ONCE
    assert format_rrule_for_display("ONCE:2026-04-13T11:30:00") == "單次提醒 (04/13 11:30)"
    # Test invalid ONCE
    assert format_rrule_for_display("ONCE:invalid") == "單次提醒 (格式錯誤)"

def test_format_daily():
    rrule = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=22;BYMINUTE=30"
    assert format_rrule_for_display(rrule) == "每天 22:30"

def test_format_weekdays():
    rrule = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=8;BYMINUTE=0"
    assert format_rrule_for_display(rrule) == "平日 (一至五) 08:00"

def test_format_weekends():
    rrule = "FREQ=WEEKLY;BYDAY=SA,SU;BYHOUR=9;BYMINUTE=0"
    assert format_rrule_for_display(rrule) == "週末 (六日) 09:00"

def test_format_specific_days():
    rrule = "FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=17;BYMINUTE=15"
    assert format_rrule_for_display(rrule) == "每週一,三,五 17:15"
    
def test_format_single_day():
    rrule = "FREQ=WEEKLY;BYDAY=SA;BYHOUR=12;BYMINUTE=0"
    assert format_rrule_for_display(rrule) == "每週六 12:00"

def test_format_fallback():
    assert format_rrule_for_display("INVALID_FORMAT") == "規律提醒 (INVALID_FORMAT)"
    assert format_rrule_for_display("") == "未知規則"
