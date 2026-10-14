"""Business rules for polls. Views stay thin and call into this module."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User

from .models import MAX_OPTIONS, MIN_OPTIONS, Category, Option, Poll

QUESTION_MIN, QUESTION_MAX = 10, 200
DESCRIPTION_MAX = 500
OPTION_MAX = 80
DAILY_POLL_LIMIT = 10
# Re-submitting an identical poll within this window (double click, Back button)
# returns the existing poll instead of publishing a duplicate.
DUPLICATE_WINDOW = timedelta(minutes=10)

# key -> (label, lifetime)
DURATIONS = {
    "1h": ("1 saat", timedelta(hours=1)),
    "6h": ("6 saat", timedelta(hours=6)),
    "24h": ("24 saat", timedelta(hours=24)),
    "3d": ("3 gün", timedelta(days=3)),
    "7d": ("7 gün", timedelta(days=7)),
}
DEFAULT_DURATION = "24h"
DURATION_CHOICES = [(key, label) for key, (label, _) in DURATIONS.items()]


class PollError(Exception):
    """Base class for rule violations; `str(error)` is a user-facing Turkish message."""


class InvalidPollError(PollError):
    pass


class DailyLimitError(PollError):
    pass


def normalize_options(raw_options) -> list[str]:
    """Trims options and drops blank ones."""
    return [option.strip() for option in raw_options if option and option.strip()]


def find_recent_duplicate(*, author: User, question: str, options: list[str]) -> Poll | None:
    """The author's poll with the same question and options created moments ago, if any."""
    wanted = [option.lower() for option in normalize_options(options)]
    recent = Poll.objects.filter(
        author=author,
        question__iexact=(question or "").strip(),
        created_at__gte=timezone.now() - DUPLICATE_WINDOW,
    ).prefetch_related("options")
    for poll in recent:
        if [option.label.lower() for option in poll.options.all()] == wanted:
            return poll
    return None


def create_poll(
    *,
    author: User,
    question: str,
    description: str = "",
    category: str,
    options: list[str],
    duration: str = DEFAULT_DURATION,
) -> Poll:
    question = (question or "").strip()
    description = (description or "").strip()
    options = normalize_options(options)

    if not QUESTION_MIN <= len(question) <= QUESTION_MAX:
        raise InvalidPollError(f"Soru {QUESTION_MIN}-{QUESTION_MAX} karakter arasında olmalı.")
    if len(description) > DESCRIPTION_MAX:
        raise InvalidPollError(f"Açıklama en fazla {DESCRIPTION_MAX} karakter olabilir.")
    if category not in Category.values:
        raise InvalidPollError("Geçerli bir kategori seç.")
    if duration not in DURATIONS:
        raise InvalidPollError("Geçerli bir süre seç.")
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise InvalidPollError(f"Anket {MIN_OPTIONS}-{MAX_OPTIONS} seçenek içermeli.")
    if any(len(option) > OPTION_MAX for option in options):
        raise InvalidPollError(f"Her seçenek en fazla {OPTION_MAX} karakter olabilir.")
    if len({option.lower() for option in options}) != len(options):
        raise InvalidPollError("Aynı seçenek birden fazla kez eklenemez.")

    now = timezone.now()
    with transaction.atomic():
        # Lock the author's row so two simultaneous requests cannot both pass the limit.
        User.objects.select_for_update().get(pk=author.pk)
        recent = Poll.objects.filter(author=author, created_at__gte=now - timedelta(hours=24)).count()
        if recent >= DAILY_POLL_LIMIT:
            raise DailyLimitError(f"Günde en fazla {DAILY_POLL_LIMIT} anket açabilirsin.")

        poll = Poll.objects.create(
            author=author,
            question=question,
            description=description,
            category=category,
            expires_at=now + DURATIONS[duration][1],
        )
        Option.objects.bulk_create(
            [Option(poll=poll, label=label, position=index) for index, label in enumerate(options)]
        )
    return poll
