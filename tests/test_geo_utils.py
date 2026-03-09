"""Tests for src/utils/geo_utils.py — Haversine distance."""
import math
from src.utils.geo_utils import calculate_distance


class TestCalculateDistance:
    def test_same_point_is_zero(self):
        assert calculate_distance(25.0, 121.5, 25.0, 121.5) == 0.0

    def test_known_distance(self):
        # Taipei 101 → Taipei Main Station ≈ ~3.3 km
        d = calculate_distance(25.0336, 121.5650, 25.0478, 121.5170)
        assert 3.0 < d < 6.0  # rough sanity

    def test_antipodal_points(self):
        d = calculate_distance(0, 0, 0, 180)
        assert abs(d - math.pi * 6371) < 1  # half circumference

    def test_symmetry(self):
        d1 = calculate_distance(10, 20, 30, 40)
        d2 = calculate_distance(30, 40, 10, 20)
        assert abs(d1 - d2) < 1e-9
