from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import User, username_validator


class LowercaseMixin:
    """Strips and lowercases input *before* validators run, so `Ali` is accepted as `ali`."""

    def to_python(self, value):
        value = super().to_python(value)
        return value.lower() if value else value


class LowercaseCharField(LowercaseMixin, forms.CharField):
    pass


class LowercaseEmailField(LowercaseMixin, forms.EmailField):
    pass


class RegisterForm(forms.Form):
    email = LowercaseEmailField(
        label="E-posta",
        max_length=254,
        error_messages={"invalid": "Geçerli bir e-posta adresi gir."},
        widget=forms.EmailInput(
            attrs={"class": "field__input", "autocomplete": "email", "autofocus": True}
        ),
    )
    username = LowercaseCharField(
        label="Kullanıcı adı",
        help_text="3-20 karakter; yalnızca küçük harf (a-z), rakam (0-9) ve _ kullanılabilir.",
        validators=[username_validator],
        # Length is enforced by the validator's regex (one clear message);
        # `maxlength` on the widget only helps the browser.
        widget=forms.TextInput(
            attrs={
                "class": "field__input",
                "autocomplete": "username",
                "autocapitalize": "none",
                "maxlength": 20,
            }
        ),
    )
    password1 = forms.CharField(
        label="Parola",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Parola (tekrar)",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Bu e-posta adresiyle zaten bir hesap var.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu kullanıcı adı zaten alınmış.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "Parolalar eşleşmiyor.")
            else:
                # Pass an unsaved user so the similarity validator can compare fields.
                candidate = User(email=cleaned.get("email", ""), username=cleaned.get("username", ""))
                try:
                    password_validation.validate_password(password1, candidate)
                except ValidationError as error:
                    self.add_error("password1", error)
        return cleaned

    def save(self) -> User:
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )


class LoginForm(AuthenticationForm):
    # Accepts an e-mail address or a username; accounts.backends.EmailOrUsernameBackend resolves it.
    username = forms.CharField(
        label="E-posta veya kullanıcı adı",
        widget=forms.TextInput(
            attrs={
                "class": "field__input",
                "autocomplete": "username",
                "autocapitalize": "none",
                "autocorrect": "off",
                "spellcheck": "false",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Parola",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "field__input", "autocomplete": "current-password"}
        ),
    )

    error_messages = {
        "invalid_login": "E-posta/kullanıcı adı veya parola hatalı.",
        "inactive": "Bu hesap pasif durumda.",
    }


class PasswordResetRequestForm(forms.Form):
    """Collects the e-mail address of the account to recover. Nothing is processed yet."""

    email = LowercaseEmailField(
        label="E-posta",
        max_length=254,
        error_messages={
            "required": "E-posta adresini yazmalısın.",
            "invalid": "Geçerli bir e-posta adresi gir.",
        },
        widget=forms.EmailInput(
            attrs={"class": "field__input", "autocomplete": "email", "autofocus": True}
        ),
    )
