from django.conf import settings


def features(request):
    """Feature flags templates need (read per request so tests can override settings)."""
    return {"password_reset_enabled": settings.PASSWORD_RESET_PAGE_ENABLED}
