import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    FOOD = "food", "Yemek"
    ENTERTAINMENT = "entertainment", "Eğlence"
    SHOPPING = "shopping", "Alışveriş"
    TRAVEL = "travel", "Seyahat"
    CAREER = "career", "Okul & Kariyer"
    RELATIONSHIPS = "relationships", "İlişkiler"
    TECHNOLOGY = "technology", "Teknoloji"
    OTHER = "other", "Diğer"


# Presentation data for categories (emoji and the accent colour used by chips/badges).
CATEGORY_EMOJI = {
    Category.FOOD: "🍕",
    Category.ENTERTAINMENT: "🎬",
    Category.SHOPPING: "🛍️",
    Category.TRAVEL: "✈️",
    Category.CAREER: "🎓",
    Category.RELATIONSHIPS: "💬",
    Category.TECHNOLOGY: "📱",
    Category.OTHER: "✨",
}
CATEGORY_COLOR = {
    Category.FOOD: "orange",
    Category.ENTERTAINMENT: "pink",
    Category.SHOPPING: "mint",
    Category.TRAVEL: "sky",
    Category.CAREER: "yellow",
    Category.RELATIONSHIPS: "pink",
    Category.TECHNOLOGY: "violet",
    Category.OTHER: "mint",
}

# Options take these accent colours in order of their position (0-4).
OPTION_COLORS = ["violet", "pink", "orange", "mint", "sky"]

MIN_OPTIONS = 2
MAX_OPTIONS = 5


class PollQuerySet(models.QuerySet):
    def open(self):
        """Polls that are neither closed early nor expired."""
        return self.filter(closed_at__isnull=True, expires_at__gt=timezone.now())


class Poll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(max_length=200)
    description = models.TextField(max_length=500, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)  # set when closed early

    objects = PollQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return self.question

    @property
    def is_open(self) -> bool:
        return self.closed_at is None and self.expires_at > timezone.now()

    @property
    def category_emoji(self) -> str:
        return CATEGORY_EMOJI.get(self.category, "")

    @property
    def category_color(self) -> str:
        return CATEGORY_COLOR.get(self.category, "violet")


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField()  # 0-4

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["poll", "position"], name="unique_option_position"),
        ]

    def __str__(self):
        return self.label

    @property
    def color(self) -> str:
        return OPTION_COLORS[self.position % len(OPTION_COLORS)]


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    voter_key = models.CharField(max_length=64)  # "u:<user_id>" or "a:<uuid>"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["poll", "voter_key"], name="one_vote_per_voter"),
        ]

    def __str__(self):
        return f"{self.voter_key} -> {self.option_id}"
