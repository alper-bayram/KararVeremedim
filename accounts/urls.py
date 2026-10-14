from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path(
        "giris/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    # LogoutView only accepts POST (the header renders a small form).
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
]
