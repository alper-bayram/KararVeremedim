from urllib.parse import quote

from django.urls import reverse


def create_poll_url(request):
    """Where the "create poll" buttons point: the form for members, sign-up for guests."""
    create = reverse("polls:create")
    if request.user.is_authenticated:
        return {"create_poll_url": create}
    return {"create_poll_url": f"{reverse('accounts:register')}?next={quote(create)}"}
