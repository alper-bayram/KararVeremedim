"""Business rules for polls. Views stay thin and call into this module."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from accounts.models import User

from . import utils
from .models import MAX_OPTIONS, MIN_OPTIONS, Category, Option, Poll, Vote

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


class NotOwnerError(PollError):
    """Only the author may close or delete a poll."""

    status_code = 403


class VoteError(PollError):
    """Base class for voting rule violations; `status_code` is the HTTP status the endpoint uses."""

    status_code = 400


class PollClosedError(VoteError):
    status_code = 409


class OwnVoteError(VoteError):
    status_code = 403


class InvalidOptionError(VoteError):
    status_code = 400


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


# --- Voting -----------------------------------------------------------------


def cast_vote(*, poll: Poll, option_id, voter_key: str, user: User | None = None) -> Vote:
    """Records the voter's vote, or moves their existing vote to another option.

    Rules: poll must be open, the author cannot vote, and the option must belong to the poll.
    """
    with transaction.atomic():
        # Lock the poll row so a vote cannot slip in while the poll is being closed.
        poll = Poll.objects.select_for_update().get(pk=poll.pk)
        if not poll.is_open:
            raise PollClosedError("Bu anket sona ermiş.")
        if user is not None and poll.author_id == user.pk:
            raise OwnVoteError("Kendi anketine oy veremezsin.")
        try:
            option = Option.objects.get(pk=int(option_id), poll=poll)
        except (TypeError, ValueError, Option.DoesNotExist):
            raise InvalidOptionError("Geçersiz seçenek.") from None

        vote, _ = Vote.objects.update_or_create(
            poll=poll, voter_key=voter_key, defaults={"option": option, "user": user}
        )
    return vote


def results_visible(*, poll: Poll, is_owner: bool, has_voted: bool) -> bool:
    """Spec 4.2: results are shown to people who voted, to the owner, and once the poll is over."""
    return (not poll.is_open) or is_owner or has_voted


def can_see_results(poll: Poll, *, user, voter_key: str | None) -> bool:
    is_owner = bool(user is not None and user.is_authenticated and poll.author_id == user.pk)
    has_voted = bool(voter_key) and Vote.objects.filter(poll=poll, voter_key=voter_key).exists()
    return results_visible(poll=poll, is_owner=is_owner, has_voted=has_voted)


def option_vote_counts(poll_ids) -> dict[int, int]:
    """{option_id: vote count} for the given polls (one query)."""
    rows = Vote.objects.filter(poll_id__in=poll_ids).values("option_id").annotate(count=Count("id"))
    return {row["option_id"]: row["count"] for row in rows}


def build_results(poll: Poll, counts: dict[int, int], my_option_id: int | None = None) -> dict:
    """Per-option results for one poll from pre-fetched counts. Only call this when results are visible."""
    options = list(poll.options.all())
    votes = [counts.get(option.pk, 0) for option in options]
    shares = utils.percentages(votes)
    top = max(votes, default=0)
    return {
        "total": sum(votes),
        "options": [
            {
                "id": option.pk,
                "label": option.label,
                "color": option.color,
                "votes": count,
                "percent": percent,
                "is_mine": option.pk == my_option_id,
                "is_leading": top > 0 and count == top,
            }
            for option, count, percent in zip(options, votes, shares)
        ],
    }


def get_results(poll: Poll, *, my_option_id: int | None = None) -> dict:
    return build_results(poll, option_vote_counts([poll.pk]), my_option_id)


# --- Poll management (owner only) -------------------------------------------


def close_poll(*, poll: Poll, user: User) -> Poll:
    """Ends a poll early. Results become visible to everyone and voting stops."""
    with transaction.atomic():
        poll = Poll.objects.select_for_update().get(pk=poll.pk)
        if poll.author_id != user.pk:
            raise NotOwnerError("Bu anketi yalnızca sahibi bitirebilir.")
        if not poll.is_open:
            raise PollClosedError("Bu anket zaten sona ermiş.")
        poll.closed_at = timezone.now()
        poll.save(update_fields=["closed_at"])
    return poll


def delete_poll(*, poll: Poll, user: User) -> None:
    """Permanently deletes a poll together with its options and votes."""
    with transaction.atomic():
        poll = Poll.objects.select_for_update().get(pk=poll.pk)
        if poll.author_id != user.pk:
            raise NotOwnerError("Bu anketi yalnızca sahibi silebilir.")
        poll.delete()
