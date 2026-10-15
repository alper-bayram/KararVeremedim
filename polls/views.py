from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import services, utils
from .forms import PollEditForm, PollForm
from .models import CATEGORY_COLOR, CATEGORY_EMOJI, Category, Poll, Vote

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


def _attach_viewer_state(request, polls) -> None:
    """Annotates polls with what *this viewer* may see and do.

    Sets `is_owner`, `my_option_id`, `can_vote`, `show_results` and `results`.
    `results` stays None unless the visibility rule allows it, so per-option
    numbers never reach a template (or JSON) for people who may not see them.
    """
    polls = list(polls)
    voter_key = utils.read_voter_key(request)
    poll_ids = [poll.pk for poll in polls]
    my_votes = {}
    if voter_key and poll_ids:
        my_votes = dict(Vote.objects.filter(voter_key=voter_key, poll_id__in=poll_ids).values_list("poll_id", "option_id"))

    for poll in polls:
        poll.is_owner = request.user.is_authenticated and poll.author_id == request.user.pk
        poll.my_option_id = my_votes.get(poll.pk)
        poll.can_vote = poll.is_open and not poll.is_owner
        poll.can_edit = poll.is_owner and services.is_editable(
            poll, has_votes=getattr(poll, "total_votes", 0) > 0
        )
        poll.show_results = services.results_visible(
            poll=poll, is_owner=poll.is_owner, has_voted=poll.my_option_id is not None
        )
        poll.results = None

    visible = [poll for poll in polls if poll.show_results]
    counts = services.option_vote_counts([poll.pk for poll in visible]) if visible else {}
    for poll in visible:
        poll.results = services.build_results(poll, counts, poll.my_option_id)


def _render_poll_list(request, queryset, *, template, context):
    """Paginates `queryset` and renders either the full page or just the list fragment."""
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("sayfa"))
    page.object_list = list(page.object_list)  # same instances the template will iterate
    _attach_viewer_state(request, page.object_list)
    params = {key: request.GET.get(key) for key in ("sirala", "kategori", "bitenler")}
    context = {
        **context,
        "page": page,
        # Where owner actions on cards send the user back to (first page, same filters, never a fragment).
        "return_url": _url(request.path, **params),
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
    # "Bitenleri de göster" only applies to the New tab: Popular is defined over open polls.
    finished_requested = request.GET.get("bitenler") == "1"
    show_finished = finished_requested and sort == SORT_NEW
    finished = "1" if finished_requested else ""

    polls = _with_counts(Poll.objects.all() if show_finished else Poll.objects.open())
    if category:
        polls = polls.filter(category=category)
    if sort == SORT_POPULAR:
        since = timezone.now() - timedelta(hours=24)
        polls = polls.annotate(recent_votes=Count("votes", filter=Q(votes__created_at__gte=since))).order_by(
            "-recent_votes", "-created_at"
        )

    popular = SORT_POPULAR if sort == SORT_POPULAR else ""
    chips = [
        {
            "label": "Tümü",
            "emoji": "",
            "color": "violet",
            "active": not category,
            "url": _url("/", sirala=popular, bitenler=finished),
        }
    ]
    for value, label in Category.choices:
        chips.append(
            {
                "label": label,
                "emoji": CATEGORY_EMOJI[value],
                "color": CATEGORY_COLOR[value],
                "active": category == value,
                "url": _url("/", sirala=popular, kategori=value, bitenler=finished),
            }
        )

    return _render_poll_list(
        request,
        polls,
        template="polls/feed.html",
        context={
            "sort": sort,
            "chips": chips,
            "tab_new_url": _url("/", kategori=category, bitenler=finished),
            "tab_popular_url": _url("/", sirala=SORT_POPULAR, kategori=category, bitenler=finished),
            "show_finished": show_finished,
            "finished_toggle_url": _url("/", kategori=category, bitenler="" if finished_requested else "1"),
            "has_filter": bool(category),
        },
    )


def _safe_next(request, default: str) -> str:
    """The `next` form value if it points back to this site, otherwise `default`."""
    candidate = request.POST.get("next", "")
    allowed = url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return candidate if allowed and candidate else default


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
    _attach_viewer_state(request, [poll])
    # "Oyumu değiştir": people who already voted may reopen the vote form.
    editing = bool(request.GET.get("degistir")) and poll.can_vote and poll.my_option_id is not None
    share_url = request.build_absolute_uri(reverse("polls:detail", args=[poll.pk]))
    return render(request, "polls/detail.html", {"poll": poll, "editing": editing, "share_url": share_url})


@require_POST
def vote(request, pk):
    """Casts or changes a vote. Answers JSON for fetch() and redirects for plain form posts."""
    poll = get_object_or_404(Poll, pk=pk)
    wants_json = "application/json" in request.headers.get("Accept", "")
    voter_key, new_cookie = utils.ensure_voter_key(request)
    user = request.user if request.user.is_authenticated else None

    try:
        cast = services.cast_vote(
            poll=poll, option_id=request.POST.get("option_id"), voter_key=voter_key, user=user
        )
    except services.VoteError as error:
        if wants_json:
            return JsonResponse({"ok": False, "error": str(error)}, status=error.status_code)
        messages.error(request, str(error))
        return redirect("polls:detail", pk=poll.pk)

    if wants_json:
        data = services.get_results(poll, my_option_id=cast.option_id)
        response = JsonResponse(
            {
                "ok": True,
                "total": data["total"],
                "my_option_id": cast.option_id,
                "results": [
                    {"id": o["id"], "label": o["label"], "votes": o["votes"], "percent": o["percent"]}
                    for o in data["options"]
                ],
            }
        )
    else:
        messages.success(request, "Oyun kaydedildi ✅")
        response = redirect("polls:detail", pk=poll.pk)

    if new_cookie:
        utils.set_voter_cookie(response, request, new_cookie)
    return response


def profile(request, username):
    profile_user = get_object_or_404(User, username=username.lower())
    polls = _with_counts(Poll.objects.filter(author=profile_user))
    return _render_poll_list(
        request,
        polls,
        template="polls/profile.html",
        context={"profile_user": profile_user, "poll_count": polls.count()},
    )


@require_POST
@login_required
def close(request, pk):
    """Ends the viewer's own poll early."""
    poll = get_object_or_404(Poll, pk=pk)
    try:
        services.close_poll(poll=poll, user=request.user)
    except services.NotOwnerError:
        raise PermissionDenied from None
    except services.PollClosedError as error:
        messages.info(request, str(error))
    else:
        messages.success(request, "Anket bitirildi. Sonuçlar artık herkese açık.")
    return redirect(_safe_next(request, reverse("polls:detail", args=[poll.pk])))


@require_POST
@login_required
def delete(request, pk):
    """Permanently deletes the viewer's own poll."""
    poll = get_object_or_404(Poll, pk=pk)
    try:
        services.delete_poll(poll=poll, user=request.user)
    except services.NotOwnerError:
        raise PermissionDenied from None
    messages.success(request, "Anket silindi.")
    return redirect(_safe_next(request, reverse("polls:profile", args=[request.user.username])))


@login_required
def mine(request):
    """"Anketlerim": the viewer's own polls with edit / close / delete actions."""
    polls = _with_counts(Poll.objects.filter(author=request.user))
    return _render_poll_list(request, polls, template="polls/mine.html", context={"manage": True})


@never_cache
@login_required
def edit(request, pk):
    poll = get_object_or_404(Poll.objects.prefetch_related("options"), pk=pk)
    if poll.author_id != request.user.pk:
        raise PermissionDenied
    if not services.is_editable(poll, has_votes=poll.votes.exists()):
        messages.error(request, "Sona ermiş ya da oy almış anketler düzenlenemez.")
        return redirect("polls:detail", pk=poll.pk)

    if request.method == "POST":
        form = PollEditForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                services.update_poll(
                    poll=poll,
                    user=request.user,
                    question=data["question"],
                    description=data["description"],
                    category=data["category"],
                    options=data["options"],
                )
            except services.PollNotEditableError as error:
                messages.error(request, str(error))
                return redirect("polls:detail", pk=poll.pk)
            except services.PollError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Anket güncellendi.")
                return redirect("polls:detail", pk=poll.pk)
    else:
        form = PollEditForm(initial=PollEditForm.initial_for(poll))

    categories = [
        {"value": value, "label": label, "emoji": CATEGORY_EMOJI[value], "color": CATEGORY_COLOR[value]}
        for value, label in Category.choices
    ]
    return render(request, "polls/create.html", {"form": form, "categories": categories, "editing_poll": poll})
