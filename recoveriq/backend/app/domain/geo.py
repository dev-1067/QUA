from __future__ import annotations

import math


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


VERIFY_RADIUS_M = 300
LOW_ACCURACY_M = 100
MAX_SPEED_KMH = 120


def verify_visit(distance_m: float, accuracy_m: float, prev: tuple[float, float, float] | None,
                 lat: float, lng: float, ts_epoch: float) -> tuple[str, str]:
    """Returns (verification, explanation). prev = (lat, lng, epoch_seconds) of the agent's previous check-in."""
    if prev is not None:
        hours = max((ts_epoch - prev[2]) / 3600.0, 1 / 3600)
        km = haversine_m(prev[0], prev[1], lat, lng) / 1000
        speed = km / hours
        if speed > MAX_SPEED_KMH and km > 1:
            return "suspicious", f"Impossible travel: {km:.1f} km since previous check-in ({speed:.0f} km/h)"
    if accuracy_m > LOW_ACCURACY_M:
        return "low_conf", f"GPS accuracy ±{accuracy_m:.0f} m is too low to verify"
    if distance_m <= VERIFY_RADIUS_M:
        return "verified", f"Within {distance_m:.0f} m of the borrower's address"
    return "flagged", f"{distance_m / 1000:.2f} km from the borrower's address (limit {VERIFY_RADIUS_M} m)"
