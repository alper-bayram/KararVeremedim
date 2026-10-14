"""Small helpers: Turkish time formatting."""

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
