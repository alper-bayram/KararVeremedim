from django.contrib import messages
from django.contrib.auth import login, password_validation
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import RegisterForm


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
