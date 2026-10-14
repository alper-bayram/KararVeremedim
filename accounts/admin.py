from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import User


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # The e-mail address is visible only here, to staff, never on public pages.
    add_form = UserCreationForm
    ordering = ("-date_joined",)
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Kişisel bilgiler", {"fields": ("first_name", "last_name")}),
        (
            "Yetkiler",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Önemli tarihler", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "usable_password", "password1", "password2"),
            },
        ),
    )
