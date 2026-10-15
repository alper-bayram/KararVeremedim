from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from polls import services
from polls.models import Poll, Vote

from .helpers import make_poll, make_user


class MyPollsTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", email="sahip.gizli@example.com")
        self.other = make_user("baska")
        self.poll = make_poll(self.owner, question="Sahibin düzenlenebilir anketi?", options=("A", "B"))
        self.edit_url = reverse("polls:edit", args=[self.poll.pk])
        self.detail_url = reverse("polls:detail", args=[self.poll.pk])

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def payload(self, **overrides):
        data = {
            "question": "Güncellenmiş soru metni burada?",
            "description": "Yeni açıklama",
            "category": "food",
            "option_1": "Yeni A",
            "option_2": "Yeni B",
            "option_3": "Yeni C",
        }
        data.update(overrides)
        return data


class AnketlerimPageTests(MyPollsTestCase):
    url = reverse("polls:mine")

    def test_guest_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_lists_only_own_polls_including_finished_ones(self):
        make_poll(self.owner, question="Süresi dolmuş benim anketim?", expires_at=timezone.now() - timedelta(hours=1))
        make_poll(self.other, question="Başkasının anketi burada duruyor?")
        response = self.client_for(self.owner).get(self.url)
        self.assertContains(response, "Sahibin düzenlenebilir anketi?")
        self.assertContains(response, "Süresi dolmuş benim anketim?")
        self.assertNotContains(response, "Başkasının anketi burada duruyor?")
        self.assertContains(response, "2 anket")

    def test_cards_show_edit_close_and_delete(self):
        response = self.client_for(self.owner).get(self.url)
        self.assertContains(response, self.edit_url)
        self.assertContains(response, reverse("polls:close", args=[self.poll.pk]))
        self.assertContains(response, reverse("polls:delete", args=[self.poll.pk]))

    def test_voted_poll_shows_note_instead_of_edit(self):
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key="a:1")
        response = self.client_for(self.owner).get(self.url)
        self.assertNotContains(response, self.edit_url)
        self.assertContains(response, "Oy aldığı için düzenlenemez")

    def test_finished_poll_offers_only_delete(self):
        self.poll.closed_at = timezone.now()
        self.poll.save()
        response = self.client_for(self.owner).get(self.url)
        self.assertNotContains(response, self.edit_url)
        self.assertNotContains(response, reverse("polls:close", args=[self.poll.pk]))
        self.assertContains(response, reverse("polls:delete", args=[self.poll.pk]))

    def test_empty_state(self):
        response = self.client_for(self.other).get(self.url)
        self.assertContains(response, "0 anket")
        self.assertContains(response, "Burası çok sessiz")

    def test_header_menu_links_to_anketlerim(self):
        response = self.client_for(self.owner).get("/")
        self.assertContains(response, 'class="usermenu"')
        self.assertContains(response, f'href="{self.url}"')

    def test_page_does_not_leak_email(self):
        response = self.client_for(self.owner).get(self.url)
        self.assertNotContains(response, "sahip.gizli")


class EditPollTests(MyPollsTestCase):
    def test_owner_sees_prefilled_form(self):
        response = self.client_for(self.owner).get(self.edit_url)
        self.assertContains(response, "Anketi düzenle")
        self.assertContains(response, "Sahibin düzenlenebilir anketi?")
        self.assertContains(response, 'value="A"')
        self.assertContains(response, 'value="B"')
        self.assertNotContains(response, 'name="duration"')
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_owner_can_update_question_options_and_category(self):
        response = self.client_for(self.owner).post(self.edit_url, self.payload(), follow=True)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, "Anket güncellendi.")
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.question, "Güncellenmiş soru metni burada?")
        self.assertEqual(self.poll.category, "food")
        self.assertEqual([(o.position, o.label) for o in self.poll.options.all()], [(0, "Yeni A"), (1, "Yeni B"), (2, "Yeni C")])

    def test_expiry_is_not_changed_by_editing(self):
        before = self.poll.expires_at
        self.client_for(self.owner).post(self.edit_url, self.payload())
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.expires_at, before)

    def test_option_rules_apply_on_edit(self):
        owner = self.client_for(self.owner)
        one = owner.post(self.edit_url, self.payload(option_2="", option_3=""))
        self.assertContains(one, "En az 2 seçenek girmelisin.")
        duplicate = owner.post(self.edit_url, self.payload(option_1="Aynı", option_2=" aynı "))
        self.assertContains(duplicate, "Bu seçenek zaten eklenmiş.")
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.question, "Sahibin düzenlenebilir anketi?")

    def test_voted_poll_cannot_be_edited(self):
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key="a:1")
        owner = self.client_for(self.owner)
        get = owner.get(self.edit_url, follow=True)
        self.assertRedirects(get, self.detail_url)
        self.assertContains(get, "oy almış anketler düzenlenemez")
        owner.post(self.edit_url, self.payload())
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.question, "Sahibin düzenlenebilir anketi?")
        self.assertEqual(self.poll.options.count(), 2)

    def test_closed_and_expired_polls_cannot_be_edited(self):
        owner = self.client_for(self.owner)
        self.poll.closed_at = timezone.now()
        self.poll.save()
        self.assertRedirects(owner.get(self.edit_url), self.detail_url)
        self.poll.closed_at = None
        self.poll.expires_at = timezone.now() - timedelta(minutes=1)
        self.poll.save()
        self.assertRedirects(owner.get(self.edit_url), self.detail_url)

    def test_non_owner_gets_403_and_guest_is_sent_to_login(self):
        self.assertEqual(self.client_for(self.other).get(self.edit_url).status_code, 403)
        self.assertEqual(self.client_for(self.other).post(self.edit_url, self.payload()).status_code, 403)
        guest = self.client.get(self.edit_url)
        self.assertEqual(guest.status_code, 302)
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.question, "Sahibin düzenlenebilir anketi?")

    def test_service_blocks_a_vote_that_arrived_after_the_form_was_opened(self):
        # The form was rendered while there were no votes; a vote lands before the save.
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key="a:late")
        with self.assertRaises(services.PollNotEditableError):
            services.update_poll(
                poll=self.poll, user=self.owner, question="Geç kalan düzenleme sorusu?",
                category="food", options=["X", "Y"],
            )

    def test_service_rejects_other_users(self):
        with self.assertRaises(services.NotOwnerError):
            services.update_poll(
                poll=self.poll, user=self.other, question="Yetkisiz düzenleme sorusu?",
                category="food", options=["X", "Y"],
            )

    def test_edit_button_on_detail_only_for_editable_own_poll(self):
        self.assertContains(self.client_for(self.owner).get(self.detail_url), self.edit_url)
        self.assertNotContains(self.client_for(self.other).get(self.detail_url), self.edit_url)
        self.assertNotContains(self.client.get(self.detail_url), self.edit_url)
        Vote.objects.create(poll=self.poll, option=self.poll.options.first(), voter_key="a:1")
        self.assertNotContains(self.client_for(self.owner).get(self.detail_url), self.edit_url)


class OwnerActionsOnFeedTests(MyPollsTestCase):
    def test_owner_sees_delete_on_own_cards_in_feed_but_not_on_others(self):
        theirs = make_poll(self.other, question="Başkasının ana sayfadaki anketi?")
        response = self.client_for(self.owner).get("/")
        self.assertContains(response, reverse("polls:delete", args=[self.poll.pk]))
        self.assertNotContains(response, reverse("polls:delete", args=[theirs.pk]))

    def test_feed_cards_do_not_show_edit_or_close(self):
        response = self.client_for(self.owner).get("/")
        self.assertNotContains(response, self.edit_url)
        self.assertNotContains(response, reverse("polls:close", args=[self.poll.pk]))

    def test_guests_and_others_see_no_delete_in_feed(self):
        for client in (Client(), self.client_for(self.other)):
            self.assertNotContains(client.get("/"), reverse("polls:delete", args=[self.poll.pk]))

    def test_delete_from_feed_returns_to_the_feed_with_filters(self):
        owner = self.client_for(self.owner)
        response = owner.post(
            reverse("polls:delete", args=[self.poll.pk]), {"next": "/?kategori=entertainment"}, follow=True
        )
        self.assertRedirects(response, "/?kategori=entertainment")
        self.assertContains(response, "Anket silindi.")
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_delete_return_url_is_the_page_without_fragment_flags(self):
        for index in range(21):
            make_poll(self.owner, question=f"Sayfalama için anket sorusu {index:02d}?")
        response = self.client_for(self.owner).get("/?kategori=entertainment&sayfa=2&partial=1")
        self.assertContains(response, 'name="next" value="/?kategori=entertainment"')
        self.assertNotContains(response, "partial=1&")

    def test_delete_ignores_external_next(self):
        owner = self.client_for(self.owner)
        response = owner.post(reverse("polls:delete", args=[self.poll.pk]), {"next": "https://evil.example/x"})
        self.assertRedirects(response, reverse("polls:profile", args=["sahip"]))

    def test_close_from_anketlerim_returns_there(self):
        owner = self.client_for(self.owner)
        response = owner.post(reverse("polls:close", args=[self.poll.pk]), {"next": reverse("polls:mine")})
        self.assertRedirects(response, reverse("polls:mine"))
        self.poll.refresh_from_db()
        self.assertFalse(self.poll.is_open)

    def test_delete_from_anketlerim_returns_there(self):
        owner = self.client_for(self.owner)
        response = owner.post(reverse("polls:delete", args=[self.poll.pk]), {"next": reverse("polls:mine")})
        self.assertRedirects(response, reverse("polls:mine"))
