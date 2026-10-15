from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

PASSWORD = "Kuvvetli-Parola-2026"


def make_user(email="ali@example.com", username="ali", password=PASSWORD):
    return User.objects.create_user(username=username, email=email, password=password)


class RegisterTests(TestCase):
    url = reverse("accounts:register")

    def post(self, **overrides):
        data = {
            "email": "yeni@example.com",
            "username": "yeni_kullanici",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_register_creates_user_and_logs_in(self):
        response = self.post()
        self.assertRedirects(response, reverse("polls:feed"))
        user = User.objects.get(email="yeni@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_email_and_username_are_stored_lowercased(self):
        self.post(email="Yeni@Example.COM", username="Yeni_Ali")
        user = User.objects.get()
        self.assertEqual(user.email, "yeni@example.com")
        self.assertEqual(user.username, "yeni_ali")

    def test_duplicate_email_rejected_case_insensitively(self):
        make_user(email="ali@example.com", username="ali")
        response = self.post(email="ALI@Example.com", username="baska")
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email", "Bu e-posta adresiyle zaten bir hesap var.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected_case_insensitively(self):
        make_user(email="ali@example.com", username="ali")
        response = self.post(email="baska@example.com", username="ALI")
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "username", "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_usernames_rejected(self):
        for username in ["ab", "Ali Veli", "çağrı", "a" * 21, "ali-veli", "ali.veli"]:
            with self.subTest(username=username):
                response = self.post(username=username)
                self.assertEqual(response.status_code, 200)
                self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_valid_username_boundaries_accepted(self):
        self.assertRedirects(self.post(email="a@example.com", username="abc"), reverse("polls:feed"))
        self.client.logout()
        self.assertRedirects(
            self.post(email="b@example.com", username="a" * 10 + "0" * 5 + "_" * 5),
            reverse("polls:feed"),
        )

    def test_password_mismatch_rejected(self):
        response = self.post(password2="baska-bir-parola-1")
        self.assertFormError(response.context["form"], "password2", "Parolalar eşleşmiyor.")
        self.assertEqual(User.objects.count(), 0)

    def test_weak_password_rejected(self):
        response = self.post(password1="12345678", password2="12345678")
        self.assertIn("password1", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_redirects_to_next_after_register(self):
        response = self.client.post(
            self.url + "?next=/anket/yeni/",
            {
                "email": "yeni@example.com",
                "username": "yeni",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "next": "/anket/yeni/",
            },
        )
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        response = self.client.post(
            self.url,
            {
                "email": "yeni@example.com",
                "username": "yeni",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(response, reverse("polls:feed"))

    def test_authenticated_user_is_redirected_away(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(self.url), reverse("polls:feed"))


class LoginLogoutTests(TestCase):
    login_url = reverse("accounts:login")

    def setUp(self):
        self.user = make_user(email="ali@example.com", username="ali")

    def test_login_with_email_is_case_insensitive(self):
        response = self.client.post(self.login_url, {"username": "ALI@Example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_username_is_possible(self):
        response = self.client.post(self.login_url, {"username": "ali", "password": PASSWORD})
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_username_is_case_insensitive_and_trimmed(self):
        response = self.client.post(self.login_url, {"username": "  ALI ", "password": PASSWORD})
        self.assertRedirects(response, "/")

    def test_username_login_honours_next(self):
        response = self.client.post(
            self.login_url, {"username": "ali", "password": PASSWORD, "next": "/anket/yeni/"}
        )
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_wrong_password_fails_for_both_identifiers(self):
        for identifier in ("ali", "ali@example.com"):
            with self.subTest(identifier=identifier):
                response = self.client.post(self.login_url, {"username": identifier, "password": "yanlis-1"})
                self.assertContains(response, "E-posta/kullanıcı adı veya parola hatalı.")
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_error_is_the_same_for_unknown_and_known_accounts(self):
        known = self.client.post(self.login_url, {"username": "ali", "password": "yanlis-1"})
        unknown = self.client.post(self.login_url, {"username": "yok_boyle_biri", "password": "yanlis-1"})
        self.assertContains(known, "E-posta/kullanıcı adı veya parola hatalı.")
        self.assertContains(unknown, "E-posta/kullanıcı adı veya parola hatalı.")

    def test_inactive_user_cannot_log_in_with_either_identifier(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        for identifier in ("ali", "ali@example.com"):
            with self.subTest(identifier=identifier):
                response = self.client.post(self.login_url, {"username": identifier, "password": PASSWORD})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_identifiers_do_not_cross_over(self):
        # Another user's username must not log in as someone whose e-mail merely starts the same way.
        make_user(email="baska@example.com", username="baska")
        response = self.client.post(self.login_url, {"username": "ali@example", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_page_label_mentions_both(self):
        self.assertContains(self.client.get(self.login_url), "E-posta veya kullanıcı adı")

    def test_admin_login_accepts_username_for_staff(self):
        staff = User.objects.create_superuser(
            username="yonetici", email="yonetici@example.com", password=PASSWORD
        )
        self.assertTrue(self.client.login(username="yonetici", password=PASSWORD))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.assertEqual(staff.username, "yonetici")

    def test_wrong_password_shows_error(self):
        response = self.client.post(self.login_url, {"username": "ali@example.com", "password": "yanlis"})
        self.assertContains(response, "E-posta/kullanıcı adı veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_redirects_to_next(self):
        response = self.client.post(
            self.login_url, {"username": "ali@example.com", "password": PASSWORD, "next": "/anket/yeni/"}
        )
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_login_ignores_external_next(self):
        response = self.client.post(
            self.login_url,
            {"username": "ali@example.com", "password": PASSWORD, "next": "https://evil.example/"},
        )
        self.assertRedirects(response, "/")

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_logs_out(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_header_links_follow_auth_state(self):
        guest = self.client.get("/")
        self.assertContains(guest, reverse("accounts:login"))
        self.assertContains(guest, reverse("accounts:register"))
        self.assertNotContains(guest, reverse("accounts:logout"))

        self.client.force_login(self.user)
        member = self.client.get("/")
        self.assertContains(member, "@ali")
        self.assertContains(member, reverse("accounts:logout"))
        self.assertNotContains(member, reverse("accounts:register"))


class PrivacyTests(TestCase):
    EMAIL = "gizli.adres@example.com"

    def setUp(self):
        self.user = make_user(email=self.EMAIL, username="gizli")

    def assert_no_email(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertNotContains(response, self.EMAIL)
        self.assertNotContains(response, "gizli.adres")

    def test_public_pages_do_not_leak_email_to_guests(self):
        for url in ["/", reverse("accounts:login"), reverse("accounts:register")]:
            with self.subTest(url=url):
                self.assert_no_email(url)

    def test_pages_do_not_leak_email_to_logged_in_user(self):
        self.client.force_login(self.user)
        self.assert_no_email("/")


class AdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="yonetici", email="yonetici@example.com", password=PASSWORD
        )
        self.client.force_login(self.admin)

    def test_admin_lists_and_shows_email(self):
        make_user(email="uye@example.com", username="uye")
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertContains(response, "uye@example.com")

    def test_admin_add_user_page_loads(self):
        self.assertEqual(self.client.get(reverse("admin:accounts_user_add")).status_code, 200)

    def test_admin_can_create_user(self):
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "email": "Yeni@Example.com",
                "username": "yeni",
                "usable_password": "true",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="yeni@example.com", username="yeni").exists())


class PasswordResetPageTests(TestCase):
    """The page is inert and hidden (404) unless PASSWORD_RESET_PAGE_ENABLED is on.

    Every test pins the flag explicitly so results do not depend on the developer's `.env`.
    """

    url = reverse("accounts:password_reset")

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=False)
    def test_page_is_hidden_while_the_flag_is_off(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {"email": "a@example.com"}).status_code, 404)

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=False)
    def test_login_page_has_no_link_while_disabled(self):
        self.assertNotContains(self.client.get(reverse("accounts:login")), "Parolamı unuttum")

    def test_env_flag_helper_is_off_unless_explicitly_enabled(self):
        import os
        from unittest import mock

        from config.settings import env_flag

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env_flag("PASSWORD_RESET_PAGE_ENABLED"))  # missing -> off
        for value, expected in [("True", True), ("1", True), ("yes", True), ("False", False), ("0", False), ("", False)]:
            with self.subTest(value=value), mock.patch.dict(os.environ, {"PASSWORD_RESET_PAGE_ENABLED": value}):
                self.assertEqual(env_flag("PASSWORD_RESET_PAGE_ENABLED"), expected)

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=True)
    def test_enabled_page_and_login_link(self):
        self.assertContains(self.client.get(self.url), "Parolanı mı unuttun?")
        self.assertContains(self.client.get(reverse("accounts:login")), "Parolamı unuttum")

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=True)
    def test_submission_only_shows_a_waiting_notice(self):
        make_user(email="ali@example.com", username="ali")
        response = self.client.post(self.url, {"email": "ali@example.com"})
        self.assertContains(response, "Talebini aldık")
        self.assertContains(response, "henüz etkin değil")
        self.assertEqual(mail.outbox, [])

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=True)
    def test_answer_is_the_same_for_unknown_addresses(self):
        make_user(email="ali@example.com", username="ali")
        known = self.client.post(self.url, {"email": "ali@example.com"}).content.decode()
        unknown = self.client.post(self.url, {"email": "yok@example.com"}).content.decode()

        def without_csrf(html):
            return "".join(line for line in html.splitlines() if "csrf" not in line.lower())

        self.assertEqual(without_csrf(known), without_csrf(unknown))

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=True)
    def test_invalid_email_is_rejected_with_a_message(self):
        response = self.client.post(self.url, {"email": "bu-bir-eposta-degil"})
        self.assertContains(response, "Geçerli bir e-posta adresi gir.")
        self.assertNotContains(response, "Talebini aldık")
        response = self.client.post(self.url, {"email": ""})
        self.assertContains(response, "E-posta adresini yazmalısın.")

    @override_settings(PASSWORD_RESET_PAGE_ENABLED=True)
    def test_nothing_is_stored(self):
        before = User.objects.count()
        self.client.post(self.url, {"email": "yeni@example.com"})
        self.assertEqual(User.objects.count(), before)
