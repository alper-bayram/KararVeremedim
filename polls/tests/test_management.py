from datetime import timedelta

from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.views.defaults import server_error

from polls import services
from polls.models import Option, Poll, Vote

from .helpers import make_poll, make_user


class ManagementTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", email="sahip.gizli@example.com")
        self.other = make_user("baska")
        self.poll = make_poll(self.owner, options=("Sinema", "Restoran"))
        self.detail_url = reverse("polls:detail", args=[self.poll.pk])
        self.close_url = reverse("polls:close", args=[self.poll.pk])
        self.delete_url = reverse("polls:delete", args=[self.poll.pk])

    def as_owner(self):
        client = Client()
        client.force_login(self.owner)
        return client

    def as_other(self):
        client = Client()
        client.force_login(self.other)
        return client

    def add_vote(self, key="a:1"):
        return Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key=key)


class ClosePollTests(ManagementTestCase):
    def test_owner_can_close_early(self):
        response = self.as_owner().post(self.close_url, follow=True)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, "Anket bitirildi.")
        self.poll.refresh_from_db()
        self.assertIsNotNone(self.poll.closed_at)
        self.assertFalse(self.poll.is_open)

    def test_closing_makes_results_visible_to_everyone(self):
        self.add_vote()
        guest = Client()
        self.assertNotContains(guest.get(self.detail_url), "result__bar")
        self.as_owner().post(self.close_url)
        after = guest.get(self.detail_url)
        self.assertContains(after, "result__bar")
        self.assertContains(after, "Bitti")

    def test_closed_poll_rejects_votes(self):
        self.as_owner().post(self.close_url)
        option = self.poll.options.first()
        response = Client().post(
            reverse("polls:vote", args=[self.poll.pk]),
            {"option_id": option.pk},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.count(), 0)

    def test_closing_keeps_existing_votes(self):
        self.add_vote()
        self.as_owner().post(self.close_url)
        self.assertEqual(Vote.objects.count(), 1)

    def test_non_owner_gets_403_and_poll_stays_open(self):
        response = self.as_other().post(self.close_url)
        self.assertEqual(response.status_code, 403)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_open)

    def test_guest_is_sent_to_login_and_poll_stays_open(self):
        response = Client().post(self.close_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_open)

    def test_close_requires_post(self):
        self.assertEqual(self.as_owner().get(self.close_url).status_code, 405)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_open)

    def test_closing_twice_explains_instead_of_failing(self):
        owner = self.as_owner()
        owner.post(self.close_url)
        first_closed_at = Poll.objects.get(pk=self.poll.pk).closed_at
        response = owner.post(self.close_url, follow=True)
        self.assertContains(response, "Bu anket zaten sona ermiş.")
        self.assertEqual(Poll.objects.get(pk=self.poll.pk).closed_at, first_closed_at)

    def test_expired_poll_cannot_be_closed(self):
        self.poll.expires_at = timezone.now() - timedelta(hours=1)
        self.poll.save()
        response = self.as_owner().post(self.close_url, follow=True)
        self.assertContains(response, "Bu anket zaten sona ermiş.")
        self.assertIsNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.close_url).status_code, 403)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_open)

    def test_service_raises_typed_errors(self):
        with self.assertRaises(services.NotOwnerError):
            services.close_poll(poll=self.poll, user=self.other)
        services.close_poll(poll=self.poll, user=self.owner)
        with self.assertRaises(services.PollClosedError):
            services.close_poll(poll=self.poll, user=self.owner)


class DeletePollTests(ManagementTestCase):
    def test_owner_can_delete_with_options_and_votes(self):
        self.add_vote("a:1")
        self.add_vote("a:2")
        response = self.as_owner().post(self.delete_url, follow=True)
        self.assertRedirects(response, reverse("polls:profile", args=["sahip"]))
        self.assertContains(response, "Anket silindi.")
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())
        self.assertEqual(Option.objects.count(), 0)
        self.assertEqual(Vote.objects.count(), 0)

    def test_deleted_poll_is_gone_everywhere(self):
        self.as_owner().post(self.delete_url)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertNotContains(self.client.get("/"), self.poll.question)

    def test_non_owner_cannot_delete(self):
        response = self.as_other().post(self.delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_guest_cannot_delete(self):
        response = Client().post(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_delete_requires_post(self):
        self.assertEqual(self.as_owner().get(self.delete_url).status_code, 405)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_can_delete_a_finished_poll(self):
        self.poll.expires_at = timezone.now() - timedelta(days=1)
        self.poll.save()
        self.as_owner().post(self.delete_url)
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_deleting_unknown_poll_is_404(self):
        url = reverse("polls:delete", args=["00000000-0000-0000-0000-000000000000"])
        self.assertEqual(self.as_owner().post(url).status_code, 404)

    def test_deleting_frees_the_daily_limit_slot(self):
        for _ in range(services.DAILY_POLL_LIMIT - 1):
            make_poll(self.owner)
        with self.assertRaises(services.DailyLimitError):
            services.create_poll(
                author=self.owner, question="Limit dolmuş mu acaba bakalım?", category="food", options=["A", "B"]
            )
        services.delete_poll(poll=self.poll, user=self.owner)
        services.create_poll(
            author=self.owner, question="Limit dolmuş mu acaba bakalım?", category="food", options=["A", "B"]
        )


class OwnerButtonsTests(ManagementTestCase):
    def test_owner_sees_close_and_delete_with_confirmations(self):
        response = self.as_owner().get(self.detail_url)
        self.assertContains(response, "Anketi bitir")
        self.assertContains(response, self.close_url)
        self.assertContains(response, self.delete_url)
        self.assertContains(response, "data-confirm")

    def test_owner_of_a_closed_poll_only_sees_delete(self):
        self.poll.closed_at = timezone.now()
        self.poll.save()
        response = self.as_owner().get(self.detail_url)
        self.assertNotContains(response, "Anketi bitir")
        self.assertContains(response, self.delete_url)

    def test_other_members_and_guests_see_no_management_buttons(self):
        for client in (self.as_other(), Client()):
            response = client.get(self.detail_url)
            self.assertNotContains(response, self.close_url)
            self.assertNotContains(response, self.delete_url)
            self.assertNotContains(response, "Anketi bitir")

    def test_share_button_is_present_with_absolute_url(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, "data-share")
        self.assertContains(response, f"http://testserver{self.detail_url}")
        self.assertContains(response, "Linki kopyala")


class FinishedFilterTests(ManagementTestCase):
    def setUp(self):
        super().setUp()
        self.old = make_poll(
            self.owner,
            question="Süresi dolmuş anket sorusu burada?",
            expires_at=timezone.now() - timedelta(hours=1),
            category="food",
        )

    def test_default_feed_hides_finished_polls(self):
        response = self.client.get("/")
        self.assertContains(response, self.poll.question)
        self.assertNotContains(response, self.old.question)

    def test_show_finished_lists_them_with_the_finished_badge(self):
        response = self.client.get("/?bitenler=1")
        self.assertContains(response, self.old.question)
        self.assertContains(response, self.poll.question)
        self.assertContains(response, "Bitti")

    def test_toggle_link_flips_and_keeps_category(self):
        off = self.client.get("/?kategori=food")
        self.assertContains(off, "Bitenleri de göster")
        self.assertContains(off, "bitenler=1")
        on = self.client.get("/?kategori=food&bitenler=1")
        self.assertContains(on, "Sadece açık anketleri göster")
        self.assertContains(on, self.old.question)

    def test_finished_filter_combines_with_category(self):
        response = self.client.get("/?kategori=entertainment&bitenler=1")
        self.assertContains(response, self.poll.question)
        self.assertNotContains(response, self.old.question)

    def test_popular_tab_ignores_the_finished_filter(self):
        response = self.client.get("/?sirala=populer&bitenler=1")
        self.assertNotContains(response, self.old.question)
        self.assertNotContains(response, "Bitenleri de göster")

    def test_chips_and_tabs_carry_the_filter(self):
        response = self.client.get("/?bitenler=1")
        self.assertContains(response, "kategori=food&amp;bitenler=1")
        self.assertContains(response, "sirala=populer&amp;bitenler=1")

    def test_pagination_keeps_the_filter(self):
        for index in range(21):
            make_poll(self.owner, question=f"Sayfalama için ek anket sorusu {index:02d}?")
        response = self.client.get("/?bitenler=1")
        self.assertContains(response, "bitenler=1")
        self.assertContains(response, "sayfa=2")

    def test_filtered_empty_state_mentions_the_category(self):
        response = self.client.get("/?kategori=travel")
        self.assertContains(response, "Bu kategoride şimdilik anket yok")


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_404_page_is_friendly_and_uses_the_site_layout(self):
        response = self.client.get("/olmayan/sayfa/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Bu sayfa kararını verip gitmiş", status_code=404)
        self.assertContains(response, "Anketlere dön", status_code=404)

    def test_unknown_poll_uses_the_404_page(self):
        response = self.client.get(reverse("polls:detail", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertContains(response, "Bu sayfa kararını verip gitmiş", status_code=404)

    def test_403_page_is_friendly(self):
        owner, other = make_user("sahip"), make_user("baska")
        poll = make_poll(owner)
        self.client.force_login(other)
        response = self.client.post(reverse("polls:delete", args=[poll.pk]))
        self.assertContains(response, "Buna iznin yok", status_code=403)

    def test_500_page_renders_standalone(self):
        request = RequestFactory().get("/")
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn("Bir şeyler ters gitti", body)
        self.assertIn("Ana sayfaya dön", body)
        self.assertNotIn("csrfmiddlewaretoken", body)


class MetaAndAccessibilityTests(ManagementTestCase):
    def test_detail_has_question_title_and_open_graph_tags(self):
        self.poll.description = "Kısa bir açıklama yazıyorum."
        self.poll.save()
        response = self.client.get(self.detail_url)
        self.assertContains(response, f"<title>{self.poll.question} — KararVeremedim</title>", html=True)
        self.assertContains(response, f'<meta property="og:title" content="{self.poll.question}">', html=True)
        self.assertContains(response, '<meta name="description" content="Kısa bir açıklama yazıyorum.">', html=True)

    def test_every_page_has_skip_link_main_landmark_and_favicon(self):
        for url in ["/", "/giris/", "/kayit/", self.detail_url]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'class="skip-link"')
                self.assertContains(response, '<main id="main"')
                self.assertContains(response, "favicon.svg")
                self.assertContains(response, 'lang="tr"')

    def test_question_in_meta_is_escaped(self):
        poll = make_poll(self.owner, question='Tırnak "içeren" <b>soru</b> burada?')
        response = self.client.get(reverse("polls:detail", args=[poll.pk]))
        self.assertNotContains(response, "<b>soru</b>")
        self.assertContains(response, "&lt;b&gt;soru&lt;/b&gt;")
