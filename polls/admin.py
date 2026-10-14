from django.contrib import admin
from django.db.models import Count

from .models import Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    fields = ("position", "label")
    readonly_fields = ("position", "label")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    """Moderation: list, inspect and delete polls (polls cannot be edited by users)."""

    list_display = ("question", "author", "category", "created_at", "expires_at", "closed_at", "vote_count")
    list_filter = ("category", "created_at")
    search_fields = ("question", "author__username")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "author", "created_at", "expires_at", "closed_at")
    inlines = [OptionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author").annotate(_vote_count=Count("votes"))

    @admin.display(description="Oy", ordering="_vote_count")
    def vote_count(self, obj):
        return obj._vote_count


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "option", "voter_key", "created_at")
    readonly_fields = ("poll", "option", "user", "voter_key", "created_at", "updated_at")
    search_fields = ("poll__question",)
    list_select_related = ("poll", "option")

    def has_add_permission(self, request):
        return False
