"""Small helpers: Turkish time formatting."""

import uuid
from datetime import datetime

from django.utils import timezone


def time_ago(moment: datetime) -> str:
    """'3 saat önce' style relative time."""
    seconds = int((timezone.now() - moment).total_seconds())
    if seconds < 60:
        return "az önce"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} dakika önce"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} saat önce"
    days = hours // 24
    if days < 30:
        return f"{days} gün önce"
    return f"{days // 30} ay önce"


def time_left(expires_at: datetime) -> str:
    """'5 saat kaldı' style remaining time; 'Bitti' once the moment has passed."""
    seconds = int((expires_at - timezone.now()).total_seconds())
    if seconds <= 0:
        return "Bitti"
    minutes = max(seconds // 60, 1)
    if minutes < 60:
        return f"{minutes} dakika kaldı"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} saat kaldı"
    return f"{hours // 24} gün kaldı"


# --- Voter identity ---------------------------------------------------------
# Members vote as "u:<user_id>"; guests as "a:<uuid>" taken from a signed cookie.

VOTER_COOKIE = "kv_voter"
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def read_voter_key(request) -> str | None:
    """The viewer's existing voter key, or None for a guest who has no valid cookie yet."""
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    raw = request.get_signed_cookie(VOTER_COOKIE, default=None, max_age=VOTER_COOKIE_MAX_AGE)
    try:
        return f"a:{uuid.UUID(raw)}" if raw else None
    except ValueError:
        return None  # tampered or malformed value counts as "no cookie"


def ensure_voter_key(request) -> tuple[str, str | None]:
    """Returns `(voter_key, new_cookie_value)`; the second item is set only when a cookie must be issued."""
    existing = read_voter_key(request)
    if existing:
        return existing, None
    new_id = str(uuid.uuid4())
    return f"a:{new_id}", new_id


def set_voter_cookie(response, request, value: str) -> None:
    response.set_signed_cookie(
        VOTER_COOKIE,
        value,
        max_age=VOTER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure(),
    )


# --- Percentages -----------------------------------------------------------


def percentages(counts: list[int]) -> list[int]:
    """Integer percentages that never exceed 100 in total (largest remainder method).

    With no votes everything is 0, so there is no division by zero.
    """
    total = sum(counts)
    if total == 0:
        return [0 for _ in counts]
    floors = [count * 100 // total for count in counts]
    remainders = [count * 100 % total for count in counts]
    missing = 100 - sum(floors)
    # Give the leftover points to the options with the largest remainders.
    for index in sorted(range(len(counts)), key=lambda i: remainders[i], reverse=True)[:missing]:
        floors[index] += 1
    return floors
