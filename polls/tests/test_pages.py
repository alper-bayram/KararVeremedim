from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from polls.models import Vote

from .helpers import make_poll, make_user


class FeedTests(TestCase):
    def setUp(self):
        self.author = make_user("ayse", email="ayse.gizli@example.com")

    def test_empty_feed_shows_friendly_message(self):
        response = self.client.get("/")
        self.assertContains(response, "Burası çok sessiz")

    def test_open_polls_are_listed_newest_first(self):
        old = make_poll(self.author, question="Eski anket sorusu burada?")
        new = make_poll(self.author, question="Yeni anket sorusu burada?")
        content = self.client.get("/").content.decode()
        self.assertLess(content.index(new.question), content.index(old.question))

    def test_expired_and_closed_polls_are_hidden(self):
        make_poll(self.author, question="Süresi dolmuş anket sorusu?", expires_at=timezone.now() - timedelta(hours=1))
        make_poll(self.author, question="Kapatılmış anket sorusu burada?", closed_at=timezone.now())
        response = self.client.get("/")
        self.assertNotContains(response, "Süresi dolmuş anket sorusu?")
        self.assertNotContains(response, "Kapatılmış anket sorusu burada?")

    def test_category_filter(self):
        make_poll(self.author, question="Yemek kategorisinde soru var?", category="food")
        make_poll(self.author, question="Teknoloji kategorisinde soru?", category="technology")
        response = self.client.get("/?kategori=food")
        self.assertContains(response, "Yemek kategorisinde soru var?")
        self.assertNotContains(response, "Teknoloji kategorisinde soru?")

    def test_unknown_category_is_ignored(self):
        make_poll(self.author, question="Herhangi bir kategoride soru?")
        response = self.client.get("/?kategori=yok")
        self.assertContains(response, "Herhangi bir kategoride soru?")

    def test_popular_orders_by_votes_in_last_24_hours(self):
        quiet = make_poll(self.author, question="Sessiz anket sorusu burada?")
        busy = make_poll(self.author, question="Hareketli anket sorusu burada?")
        # `quiet` is newer but has no votes; `busy` has two recent votes.
        quiet.created_at = timezone.now()
        quiet.save()
        for index in range(2):
            Vote.objects.create(poll=busy, option=busy.options.first(), voter_key=f"a:{index}")
        content = self.client.get("/?sirala=populer").content.decode()
        self.assertLess(content.index(busy.question), content.index(quiet.question))

    def test_old_votes_do_not_count_as_popular(self):
        older = make_poll(self.author, question="Eski oylu anket sorusu?")
        newer = make_poll(self.author, question="Yeni oysuz anket sorusu?")
        vote = Vote.objects.create(poll=older, option=older.options.first(), voter_key="a:1")
        Vote.objects.filter(pk=vote.pk).update(created_at=timezone.now() - timedelta(days=2))
        content = self.client.get("/?sirala=populer").content.decode()
        self.assertLess(content.index(newer.question), content.index(older.question))

    def test_pagination_and_partial_fragment(self):
        for index in range(25):
            make_poll(self.author, question=f"Sayfalama deneme sorusu {index:02d}?")
        first = self.client.get("/")
        self.assertContains(first, "Daha fazla göster")
        self.assertEqual(first.content.decode().count('class="card poll-card"'), 20)

        partial = self.client.get("/?sayfa=2&partial=1")
        text = partial.content.decode()
        self.assertEqual(text.count('class="card poll-card"'), 5)
        self.assertNotIn("<html", text)
        self.assertNotIn("Daha fazla göster", text)

    def test_load_more_link_keeps_filters(self):
        for index in range(21):
            make_poll(self.author, question=f"Filtreli sayfalama sorusu {index:02d}?", category="food")
        response = self.client.get("/?sirala=populer&kategori=food")
        self.assertContains(response, "sirala=populer")
        self.assertContains(response, "kategori=food")
        self.assertContains(response, "sayfa=2")

    def test_card_shows_totals_and_author_without_email(self):
        make_poll(self.author)
        response = self.client.get("/")
        self.assertContains(response, "@ayse")
        self.assertContains(response, "<span data-total-votes>0</span> oy")
        self.assertNotContains(response, "ayse.gizli")

    def test_invite_banner_only_for_guests(self):
        self.assertContains(self.client.get("/"), "Ücretsiz üye ol")
        self.client.force_login(self.author)
        self.assertNotContains(self.client.get("/"), "Ücretsiz üye ol")


class DetailTests(TestCase):
    def setUp(self):
        self.author = make_user("ayse", email="ayse.gizli@example.com")
        self.poll = make_poll(self.author, description="Biraz bağlam ekliyorum.")

    def test_detail_shows_question_description_options_and_total(self):
        response = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(response, self.poll.question)
        self.assertContains(response, "Biraz bağlam ekliyorum.")
        self.assertContains(response, "Sinema")
        self.assertContains(response, "Restoran")
        self.assertContains(response, "<span data-total-votes>0</span> oy")

    def test_detail_hides_percentages(self):
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key="a:1")
        response = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(response, "<span data-total-votes>1</span> oy")
        self.assertNotContains(response, "%")

    def test_detail_title_contains_question(self):
        response = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(response, f"<title>{self.poll.question} — KararVeremedim</title>", html=True)

    def test_expired_poll_detail_is_still_reachable(self):
        self.poll.expires_at = timezone.now() - timedelta(hours=1)
        self.poll.save()
        response = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(response, "Bitti")

    def test_unknown_poll_is_404(self):
        response = self.client.get(reverse("polls:detail", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertEqual(response.status_code, 404)

    def test_detail_does_not_leak_author_email(self):
        response = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertNotContains(response, "ayse.gizli")


class ProfileTests(TestCase):
    def setUp(self):
        self.author = make_user("ayse", email="ayse.gizli@example.com")
        self.other = make_user("mehmet")

    def test_profile_lists_only_that_users_polls(self):
        make_poll(self.author, question="Ayşe'nin anket sorusu burada?")
        make_poll(self.other, question="Mehmet'in anket sorusu burada?")
        response = self.client.get(reverse("polls:profile", args=["ayse"]))
        self.assertContains(response, "Ayşe&#x27;nin anket sorusu burada?")
        self.assertNotContains(response, "Mehmet&#x27;in anket sorusu burada?")
        self.assertContains(response, "@ayse")
        self.assertContains(response, "1 anket")

    def test_profile_includes_closed_polls(self):
        make_poll(self.author, question="Bitmiş anket sorusu burada?", expires_at=timezone.now() - timedelta(days=1))
        response = self.client.get(reverse("polls:profile", args=["ayse"]))
        self.assertContains(response, "Bitmiş anket sorusu burada?")

    def test_profile_username_lookup_is_case_insensitive(self):
        self.assertEqual(self.client.get("/u/AYSE/").status_code, 200)

    def test_unknown_profile_is_404(self):
        self.assertEqual(self.client.get("/u/kimse/").status_code, 404)

    def test_profile_does_not_leak_email(self):
        response = self.client.get(reverse("polls:profile", args=["ayse"]))
        self.assertNotContains(response, "ayse.gizli")

    def test_empty_profile_shows_friendly_message(self):
        response = self.client.get(reverse("polls:profile", args=["mehmet"]))
        self.assertContains(response, "0 anket")
        self.assertContains(response, "Burası çok sessiz")


class AdminPollTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.admin = get_user_model().objects.create_superuser(
            username="yonetici", email="yonetici@example.com", password="Kuvvetli-Parola-2026"
        )
        self.client.force_login(self.admin)
        self.poll = make_poll(make_user("ayse"))

    def test_changelist_and_delete(self):
        response = self.client.get(reverse("admin:polls_poll_changelist"))
        self.assertContains(response, self.poll.question)
        response = self.client.post(
            reverse("admin:polls_poll_delete", args=[self.poll.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(type(self.poll).objects.filter(pk=self.poll.pk).exists())
