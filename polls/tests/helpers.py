from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from polls.models import Option, Poll

User = get_user_model()
PASSWORD = "Kuvvetli-Parola-2026"


def make_user(username="ayse", email=None):
    return User.objects.create_user(
        username=username, email=email or f"{username}@example.com", password=PASSWORD
    )


def make_poll(author, question="Bu akşam sinemaya mı gitsem?", options=("Sinema", "Restoran"), **overrides):
    """Creates a poll directly (bypassing the service) so tests can control any field."""
    defaults = {
        "question": question,
        "category": "entertainment",
        "expires_at": timezone.now() + timedelta(hours=24),
    }
    defaults.update(overrides)
    poll = Poll.objects.create(author=author, **defaults)
    for position, label in enumerate(options):
        Option.objects.create(poll=poll, label=label, position=position)
    return poll
