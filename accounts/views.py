from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, password_validation
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import PasswordResetRequestForm, RegisterForm


def _safe_next_url(request) -> str:
    """Returns the `next` parameter if it points back to this site, else an empty string."""
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    allowed = url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    return candidate if allowed else ""


def register(request):
    if request.user.is_authenticated:
        return redirect("polls:feed")

    next_url = _safe_next_url(request)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Aramıza hoş geldin, @{user.username}! 🎉")
            return redirect(next_url or "polls:feed")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "next": next_url,
            "password_help": password_validation.password_validators_help_texts(),
        },
    )


def password_reset_request(request):
    """"Parolamı unuttum": collects the e-mail address, then only shows a waiting notice.

    Deliberately inert: nothing is stored or sent, and the answer is identical for
    existing and unknown addresses. Hidden (404) unless PASSWORD_RESET_PAGE_ENABLED is on.
    """
    if not settings.PASSWORD_RESET_PAGE_ENABLED:
        raise Http404
    if request.user.is_authenticated:
        return redirect("polls:feed")

    submitted = False
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        submitted = form.is_valid()
    else:
        form = PasswordResetRequestForm()
    return render(request, "accounts/password_reset.html", {"form": form, "submitted": submitted})
