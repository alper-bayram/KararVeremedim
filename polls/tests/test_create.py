from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from polls import services
from polls.models import Option, Poll

from .helpers import PASSWORD, make_poll, make_user


def poll_data(**overrides):
    data = {
        "question": "Bu akşam sinemaya mı gitsem, restorana mı?",
        "description": "",
        "category": "entertainment",
        "duration": "24h",
        "option_1": "Sinema",
        "option_2": "Restoran",
    }
    data.update(overrides)
    return data


class CreatePollViewTests(TestCase):
    url = reverse("polls:create")

    def setUp(self):
        self.user = make_user("ayse")

    def login(self):
        self.client.force_login(self.user)

    def test_guest_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_guest_create_buttons_point_to_register_with_next(self):
        response = self.client.get("/")
        self.assertContains(response, f"{reverse('accounts:register')}?next=/anket/yeni/")

    def test_member_create_buttons_point_to_form(self):
        self.login()
        response = self.client.get("/")
        self.assertContains(response, 'href="/anket/yeni/"')

    def test_create_redirects_to_detail_with_message(self):
        self.login()
        response = self.client.post(self.url, poll_data(), follow=True)
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("polls:detail", args=[poll.pk]))
        self.assertContains(response, "Anketin yayında! 🎉")

    def test_options_are_stored_in_order_and_blanks_dropped(self):
        self.login()
        self.client.post(self.url, poll_data(option_2="", option_3="B", option_4="  ", option_5="C", option_1="A"))
        poll = Poll.objects.get()
        self.assertEqual([(o.position, o.label) for o in poll.options.all()], [(0, "A"), (1, "B"), (2, "C")])

    def test_one_option_is_rejected(self):
        self.login()
        response = self.client.post(self.url, poll_data(option_2=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_two_and_five_options_are_accepted(self):
        self.login()
        self.client.post(self.url, poll_data())
        self.client.post(
            self.url,
            poll_data(option_1="1", option_2="2", option_3="3", option_4="4", option_5="5"),
        )
        self.assertEqual(Poll.objects.count(), 2)
        self.assertEqual(sorted(p.options.count() for p in Poll.objects.all()), [2, 5])

    def test_duplicate_options_are_rejected_case_insensitively(self):
        self.login()
        response = self.client.post(self.url, poll_data(option_1="Sinema", option_2="  sinema "))
        self.assertContains(response, "Bu seçenek zaten eklenmiş.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_question_length_limits(self):
        self.login()
        for question in ["kısa", "x" * 201]:
            with self.subTest(length=len(question)):
                response = self.client.post(self.url, poll_data(question=question))
                self.assertEqual(response.status_code, 200)
                self.assertIn("question", response.context["form"].errors)
        self.assertEqual(Poll.objects.count(), 0)

    def test_description_is_optional_but_limited(self):
        self.login()
        self.client.post(self.url, poll_data(description=""))
        response = self.client.post(self.url, poll_data(description="x" * 501))
        self.assertEqual(Poll.objects.count(), 1)
        self.assertIn("description", response.context["form"].errors)

    def test_category_is_required_and_validated(self):
        self.login()
        for category in ["", "yok-boyle-kategori"]:
            response = self.client.post(self.url, poll_data(category=category))
            self.assertIn("category", response.context["form"].errors)
        self.assertEqual(Poll.objects.count(), 0)

    def test_option_longer_than_80_chars_is_rejected(self):
        self.login()
        response = self.client.post(self.url, poll_data(option_1="x" * 81))
        self.assertIn("option_1", response.context["form"].errors)

    def test_daily_limit_is_shown_in_the_form(self):
        self.login()
        for _ in range(services.DAILY_POLL_LIMIT):
            make_poll(self.user)
        response = self.client.post(self.url, poll_data())
        self.assertContains(response, "Günde en fazla 10 anket açabilirsin.")
        self.assertEqual(Poll.objects.count(), services.DAILY_POLL_LIMIT)

    def test_form_escapes_user_input(self):
        self.login()
        self.client.post(self.url, poll_data(question="<script>alert(1)</script> soru?", option_1="<b>x</b>"))
        poll = Poll.objects.get()
        response = self.client.get(reverse("polls:detail", args=[poll.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")


class CreatePollServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("ayse")

    def create(self, **overrides):
        kwargs = {
            "author": self.user,
            "question": "Hangisini seçmeliyim bilemedim?",
            "category": "food",
            "options": ["A", "B"],
        }
        kwargs.update(overrides)
        return services.create_poll(**kwargs)

    def test_service_enforces_option_count(self):
        for options in [["A"], ["1", "2", "3", "4", "5", "6"], [" ", ""]]:
            with self.subTest(options=options), self.assertRaises(services.InvalidPollError):
                self.create(options=options)
        self.assertEqual(self.create(options=["1", "2", "3", "4", "5"]).options.count(), 5)

    def test_service_rejects_duplicates_after_trimming(self):
        with self.assertRaises(services.InvalidPollError):
            self.create(options=["Kedi", " kedi "])

    def test_service_rejects_bad_question_category_and_duration(self):
        with self.assertRaises(services.InvalidPollError):
            self.create(question="kısa")
        with self.assertRaises(services.InvalidPollError):
            self.create(category="nope")
        with self.assertRaises(services.InvalidPollError):
            self.create(duration="2y")

    def test_duration_sets_expiry(self):
        before = timezone.now()
        poll = self.create(duration="7d")
        self.assertAlmostEqual(
            (poll.expires_at - before).total_seconds(), timedelta(days=7).total_seconds(), delta=5
        )

    def test_daily_limit_blocks_the_eleventh_poll(self):
        for _ in range(services.DAILY_POLL_LIMIT):
            self.create()
        with self.assertRaises(services.DailyLimitError):
            self.create()

    def test_daily_limit_ignores_polls_older_than_a_day_and_other_users(self):
        for _ in range(services.DAILY_POLL_LIMIT):
            make_poll(self.user)
        Poll.objects.update(created_at=timezone.now() - timedelta(hours=25))
        self.create()  # does not raise

        other = make_user("mehmet")
        for _ in range(services.DAILY_POLL_LIMIT):
            self.create(author=other)
        self.assertEqual(Poll.objects.filter(author=self.user).count(), services.DAILY_POLL_LIMIT + 1)

    def test_options_belong_to_the_created_poll(self):
        poll = self.create()
        self.assertEqual(Option.objects.filter(poll=poll).count(), 2)

    def test_is_open_reflects_expiry_and_early_close(self):
        poll = self.create()
        self.assertTrue(poll.is_open)
        poll.closed_at = timezone.now()
        self.assertFalse(poll.is_open)
        poll.closed_at = None
        poll.expires_at = timezone.now() - timedelta(minutes=1)
        self.assertFalse(poll.is_open)


class PasswordNotUsedTest(TestCase):
    def test_helper_password_is_valid(self):
        # Guards the shared test password against validator changes.
        user = make_user("kontrol")
        self.assertTrue(user.check_password(PASSWORD))
