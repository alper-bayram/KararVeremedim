from django.contrib.auth import get_user_model
from django.test import TestCase
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

    def test_login_with_username_is_not_possible(self):
        response = self.client.post(self.login_url, {"username": "ali", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_shows_error(self):
        response = self.client.post(self.login_url, {"username": "ali@example.com", "password": "yanlis"})
        self.assertContains(response, "E-posta veya parola hatalı.")
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
