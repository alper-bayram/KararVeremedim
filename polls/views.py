from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from . import services
from .forms import PollForm
from .models import CATEGORY_COLOR, CATEGORY_EMOJI, Category, Poll

User = get_user_model()

PAGE_SIZE = 20
SORT_NEW, SORT_POPULAR = "yeni", "populer"



def _with_counts(queryset):
    """Adds `total_votes` and prefetches options for poll cards (newest first).

    The explicit ordering matters: Django drops `Meta.ordering` for GROUP BY queries,
    so without it pagination would be unordered.
    """
    return (
        queryset.select_related("author")
        .prefetch_related("options")
        .annotate(total_votes=Count("votes"))
        .order_by("-created_at")
    )


def _url(path: str, **params) -> str:
    params = {key: value for key, value in params.items() if value}
    return f"{path}?{urlencode(params)}" if params else path


def _render_poll_list(request, queryset, *, template, context):
    """Paginates `queryset` and renders either the full page or just the list fragment."""
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("sayfa"))
    params = {key: request.GET.get(key) for key in ("sirala", "kategori")}
    context = {
        **context,
        "page": page,
        "next_page_url": _url(request.path, **params, sayfa=page.next_page_number()) if page.has_next() else "",
    }
    if request.GET.get("partial"):
        return render(request, "partials/_poll_list.html", context)
    return render(request, template, context)


def feed(request):
    sort = SORT_POPULAR if request.GET.get("sirala") == SORT_POPULAR else SORT_NEW
    category = request.GET.get("kategori")
    if category not in Category.values:
        category = ""

    polls = _with_counts(Poll.objects.open())
    if category:
        polls = polls.filter(category=category)
    if sort == SORT_POPULAR:
        since = timezone.now() - timedelta(hours=24)
        polls = polls.annotate(recent_votes=Count("votes", filter=Q(votes__created_at__gte=since))).order_by(
            "-recent_votes", "-created_at"
        )

    chips = [
        {
            "label": "Tümü",
            "emoji": "",
            "color": "violet",
            "active": not category,
            "url": _url("/", sirala=sort if sort == SORT_POPULAR else ""),
        }
    ]
    for value, label in Category.choices:
        chips.append(
            {
                "label": label,
                "emoji": CATEGORY_EMOJI[value],
                "color": CATEGORY_COLOR[value],
                "active": category == value,
                "url": _url("/", sirala=sort if sort == SORT_POPULAR else "", kategori=value),
            }
        )

    return _render_poll_list(
        request,
        polls,
        template="polls/feed.html",
        context={
            "sort": sort,
            "chips": chips,
            "tab_new_url": _url("/", kategori=category),
            "tab_popular_url": _url("/", sirala=SORT_POPULAR, kategori=category),
            "has_filter": bool(category),
        },
    )


@never_cache
@login_required
def create(request):
    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            duplicate = services.find_recent_duplicate(
                author=request.user, question=data["question"], options=data["options"]
            )
            if duplicate:
                # Same form submitted again (double click, Back button): show the existing poll.
                messages.info(request, "Bu anketi zaten yayınladın.")
                return redirect("polls:detail", pk=duplicate.pk)
            try:
                poll = services.create_poll(
                    author=request.user,
                    question=data["question"],
                    description=data["description"],
                    category=data["category"],
                    options=data["options"],
                    duration=data["duration"],
                )
            except services.PollError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Anketin yayında! 🎉")
                return redirect("polls:detail", pk=poll.pk)
    else:
        form = PollForm(initial={"duration": services.DEFAULT_DURATION})

    categories = [
        {"value": value, "label": label, "emoji": CATEGORY_EMOJI[value], "color": CATEGORY_COLOR[value]}
        for value, label in Category.choices
    ]
    return render(request, "polls/create.html", {"form": form, "categories": categories})


def detail(request, pk):
    poll = get_object_or_404(_with_counts(Poll.objects.all()), pk=pk)
    return render(request, "polls/detail.html", {"poll": poll})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username.lower())
    polls = _with_counts(Poll.objects.filter(author=profile_user))
    return _render_poll_list(
        request,
        polls,
        template="polls/profile.html",
        context={"profile_user": profile_user, "poll_count": polls.count()},
    )
