from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models

username_validator = RegexValidator(
    regex=r"^[a-z0-9_]{3,20}$",
    message="Kullanıcı adı 3-20 karakter olmalı ve yalnızca a-z, 0-9 ve _ içerebilir.",
)


class CaseInsensitiveUserManager(UserManager):
    """Looks users up by lowercased e-mail, matching how they are stored."""

    def get_by_natural_key(self, email):
        return super().get_by_natural_key(email.strip().lower())


class User(AbstractUser):
    # Both fields are stored lowercased, so plain unique constraints are
    # effectively case-insensitive.
    email = models.EmailField("e-posta", unique=True)
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CaseInsensitiveUserManager()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.username = self.username.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
