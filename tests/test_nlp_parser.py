"""Tests for src/utils/nlp_parser.py — NLP-to-RRule conversion.
Covers every branch: 每天, 平日, 一到五, 週末, 六日, individual days,
AM/PM logic, 下午/晚上/pm, 早上/上午/am, no-day default, 點 syntax.
"""
from src.utils.nlp_parser import parse_natural_language_to_rrule


class TestParseNlpRrule:
    def test_every_day(self):
        r = parse_natural_language_to_rrule("每天 08:30")
        assert "BYDAY=MO,TU,WE,TH,FR,SA,SU" in r
        assert "BYHOUR=8" in r
        assert "BYMINUTE=30" in r

    def test_everyday_english(self):
        r = parse_natural_language_to_rrule("everyday 09:00")
        assert "BYDAY=MO,TU,WE,TH,FR,SA,SU" in r

    def test_weekdays_一到五(self):
        r = parse_natural_language_to_rrule("一到五 08:30")
        assert "BYDAY=MO,TU,WE,TH,FR" in r

    def test_weekdays_平日(self):
        r = parse_natural_language_to_rrule("平日 17:00")
        assert "BYDAY=MO,TU,WE,TH,FR" in r

    def test_weekend_週末(self):
        r = parse_natural_language_to_rrule("週末 10:00")
        assert "BYDAY=SA,SU" in r

    def test_weekend_六日(self):
        r = parse_natural_language_to_rrule("六日 10:00")
        assert "BYDAY=SA,SU" in r

    def test_individual_day_五(self):
        r = parse_natural_language_to_rrule("每週五 20:00")
        assert "FR" in r
        assert "BYHOUR=20" in r

    def test_individual_day_english(self):
        r = parse_natural_language_to_rrule("mon 07:15")
        assert "MO" in r

    def test_no_day_defaults_every_day(self):
        r = parse_natural_language_to_rrule("08:30")
        assert "BYDAY=MO,TU,WE,TH,FR,SA,SU" in r

    def test_time_colon_fullwidth(self):
        r = parse_natural_language_to_rrule("每天 08：30")
        assert "BYHOUR=8" in r
        assert "BYMINUTE=30" in r

    def test_time_點_syntax(self):
        r = parse_natural_language_to_rrule("每天 5點")
        assert "BYHOUR=5" in r
        assert "BYMINUTE=0" in r

    def test_pm_下午(self):
        r = parse_natural_language_to_rrule("每天 下午 3:00")
        assert "BYHOUR=15" in r

    def test_pm_晚上(self):
        r = parse_natural_language_to_rrule("每天 晚上 8:00")
        assert "BYHOUR=20" in r

    def test_pm_english(self):
        r = parse_natural_language_to_rrule("每天 3:00 pm")
        assert "BYHOUR=15" in r

    def test_am_早上(self):
        r = parse_natural_language_to_rrule("每天 早上 12:00")
        assert "BYHOUR=0" in r

    def test_am_上午(self):
        r = parse_natural_language_to_rrule("每天 上午 12:00")
        assert "BYHOUR=0" in r

    def test_am_english(self):
        r = parse_natural_language_to_rrule("每天 12:00 am")
        assert "BYHOUR=0" in r

    def test_no_time_defaults_zero(self):
        r = parse_natural_language_to_rrule("每天")
        assert "BYHOUR=0" in r
        assert "BYMINUTE=0" in r

    def test_pm_no_change_when_hour_ge_12(self):
        r = parse_natural_language_to_rrule("每天 下午 13:00")
        assert "BYHOUR=13" in r  # already >= 12, no +12

    def test_am_no_change_when_not_12(self):
        r = parse_natural_language_to_rrule("每天 早上 9:00")
        assert "BYHOUR=9" in r
