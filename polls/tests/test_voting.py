import json
import uuid
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from polls import services, utils
from polls.models import Vote

from .helpers import make_poll, make_user

JSON = {"HTTP_ACCEPT": "application/json"}


class VotingTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", email="sahip.gizli@example.com")
        self.poll = make_poll(self.owner, options=("Sinema", "Restoran", "Ev"))
        self.sinema, self.restoran, self.ev = list(self.poll.options.all())
        self.vote_url = reverse("polls:vote", args=[self.poll.pk])
        self.detail_url = reverse("polls:detail", args=[self.poll.pk])

    def vote(self, option, client=None, **extra):
        client = client or self.client
        return client.post(self.vote_url, {"option_id": option.pk}, **extra)

    def vote_json(self, option, client=None):
        response = self.vote(option, client=client, **JSON)
        return response, json.loads(response.content)


class GuestVotingTests(VotingTestCase):
    def test_guest_can_vote_and_gets_a_signed_cookie(self):
        response, data = self.vote_json(self.sinema)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["my_option_id"], self.sinema.pk)
        self.assertIn(utils.VOTER_COOKIE, response.cookies)
        vote = Vote.objects.get()
        self.assertTrue(vote.voter_key.startswith("a:"))
        self.assertIsNone(vote.user)

    def test_cookie_is_httponly_lax_and_one_year(self):
        response, _ = self.vote_json(self.sinema)
        cookie = response.cookies[utils.VOTER_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(int(cookie["max-age"]), 60 * 60 * 24 * 365)

    def test_same_guest_second_vote_updates_the_existing_vote(self):
        self.vote_json(self.sinema)
        _, data = self.vote_json(self.restoran)
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().option, self.restoran)
        self.assertEqual(data["my_option_id"], self.restoran.pk)
        self.assertEqual(data["total"], 1)

    def test_cookie_is_not_reissued_on_later_votes(self):
        self.vote_json(self.sinema)
        response, _ = self.vote_json(self.restoran)
        self.assertNotIn(utils.VOTER_COOKIE, response.cookies)

    def test_different_guests_are_counted_separately(self):
        self.vote_json(self.sinema)
        _, data = self.vote_json(self.sinema, client=Client())
        self.assertEqual(Vote.objects.count(), 2)
        self.assertEqual(data["total"], 2)

    def test_tampered_cookie_is_ignored_and_replaced(self):
        client = Client()
        client.cookies[utils.VOTER_COOKIE] = "not-a-signed-value"
        response, _ = self.vote_json(self.sinema, client=client)
        self.assertEqual(response.status_code, 200)
        self.assertIn(utils.VOTER_COOKIE, response.cookies)
        self.assertNotEqual(response.cookies[utils.VOTER_COOKIE].value, "not-a-signed-value")

    def test_signed_cookie_with_garbage_payload_is_ignored(self):
        from django.core import signing

        client = Client()
        # Validly signed, but the payload is not a UUID.
        client.cookies[utils.VOTER_COOKIE] = signing.get_cookie_signer(salt=utils.VOTER_COOKIE).sign("garbage")
        response, _ = self.vote_json(self.sinema, client=client)
        self.assertEqual(response.status_code, 200)
        self.assertIn(utils.VOTER_COOKIE, response.cookies)
        self.assertRegex(Vote.objects.get().voter_key, r"^a:[0-9a-f-]{36}$")

    def test_cookie_identity_is_not_shared_with_members(self):
        self.vote_json(self.sinema)  # guest
        member = make_user("uye")
        client = Client()
        client.force_login(member)
        self.vote_json(self.sinema, client=client)
        self.assertEqual(Vote.objects.count(), 2)


class MemberVotingTests(VotingTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_user("uye")
        self.client.force_login(self.member)

    def test_member_vote_uses_user_key_and_user_fk(self):
        self.vote_json(self.sinema)
        vote = Vote.objects.get()
        self.assertEqual(vote.voter_key, f"u:{self.member.pk}")
        self.assertEqual(vote.user, self.member)

    def test_member_vote_sets_no_guest_cookie(self):
        response, _ = self.vote_json(self.sinema)
        self.assertNotIn(utils.VOTER_COOKIE, response.cookies)

    def test_member_cannot_create_two_votes_on_one_poll(self):
        self.vote_json(self.sinema)
        self.vote_json(self.restoran)
        self.assertEqual(Vote.objects.filter(poll=self.poll).count(), 1)
        self.assertEqual(Vote.objects.get().option, self.restoran)

    def test_database_rejects_a_duplicate_voter_key(self):
        from django.db import IntegrityError, transaction

        Vote.objects.create(poll=self.poll, option=self.sinema, voter_key="u:1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=self.restoran, voter_key="u:1")

    def test_owner_cannot_vote_on_own_poll(self):
        client = Client()
        client.force_login(self.owner)
        response, data = self.vote_json(self.sinema, client=client)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(data["ok"])
        self.assertEqual(Vote.objects.count(), 0)

    def test_service_raises_own_vote_error(self):
        with self.assertRaises(services.OwnVoteError):
            services.cast_vote(
                poll=self.poll, option_id=self.sinema.pk, voter_key=f"u:{self.owner.pk}", user=self.owner
            )


class VotingRuleTests(VotingTestCase):
    def test_closed_early_poll_rejects_votes(self):
        self.poll.closed_at = timezone.now()
        self.poll.save()
        response, data = self.vote_json(self.sinema)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(data["error"], "Bu anket sona ermiş.")
        self.assertEqual(Vote.objects.count(), 0)

    def test_expired_poll_rejects_votes(self):
        self.poll.expires_at = timezone.now() - timedelta(minutes=1)
        self.poll.save()
        response, _ = self.vote_json(self.sinema)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.count(), 0)

    def test_changing_a_vote_after_expiry_is_rejected(self):
        self.vote_json(self.sinema)
        self.poll.expires_at = timezone.now() - timedelta(minutes=1)
        self.poll.save()
        response, _ = self.vote_json(self.restoran)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.get().option, self.sinema)

    def test_option_of_another_poll_is_rejected(self):
        other = make_poll(self.owner, question="Başka bir anket sorusu burada?", options=("X", "Y"))
        foreign_option = other.options.first()
        response, data = self.vote_json(foreign_option)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data["error"], "Geçersiz seçenek.")
        self.assertEqual(Vote.objects.count(), 0)

    def test_missing_or_non_numeric_option_is_rejected(self):
        for payload in [{}, {"option_id": ""}, {"option_id": "abc"}, {"option_id": "99999"}]:
            with self.subTest(payload=payload):
                response = self.client.post(self.vote_url, payload, **JSON)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_endpoint_requires_post(self):
        response = self.client.get(self.vote_url, **JSON)
        self.assertEqual(response.status_code, 405)

    def test_unknown_poll_is_404(self):
        url = reverse("polls:vote", args=[uuid.uuid4()])
        self.assertEqual(self.client.post(url, {"option_id": 1}, **JSON).status_code, 404)

    def test_csrf_is_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        response = strict.post(self.vote_url, {"option_id": self.sinema.pk}, **JSON)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)


class ResponseShapeTests(VotingTestCase):
    def test_json_success_shape_and_totals(self):
        self.vote_json(self.sinema, client=Client())
        self.vote_json(self.sinema, client=Client())
        response, data = self.vote_json(self.restoran, client=Client())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(data), {"ok", "total", "my_option_id", "results"})
        self.assertEqual(data["total"], 3)
        by_label = {item["label"]: item for item in data["results"]}
        self.assertEqual(by_label["Sinema"]["votes"], 2)
        self.assertEqual(by_label["Restoran"]["votes"], 1)
        self.assertEqual(by_label["Ev"]["votes"], 0)
        self.assertEqual(set(by_label["Sinema"]), {"id", "label", "votes", "percent"})
        self.assertEqual(sum(item["percent"] for item in data["results"]), 100)

    def test_json_never_exposes_email_or_user_ids(self):
        response, _ = self.vote_json(self.sinema)
        self.assertNotContains(response, "gizli")
        self.assertNotContains(response, "voter_key")

    def test_plain_form_post_redirects_to_detail(self):
        response = self.vote(self.sinema)
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(Vote.objects.count(), 1)

    def test_plain_form_post_error_redirects_with_message(self):
        self.poll.closed_at = timezone.now()
        self.poll.save()
        response = self.client.post(self.vote_url, {"option_id": self.sinema.pk}, follow=True)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, "Bu anket sona ermiş.")


class ResultVisibilityTests(VotingTestCase):
    """Spec 4.2: results appear only after voting, for the owner, or once the poll is over."""

    def assert_results_hidden(self, response):
        self.assertNotContains(response, "result__bar")
        self.assertNotContains(response, "data-results")
        self.assertContains(response, "data-vote-form")

    def assert_results_shown(self, response):
        self.assertContains(response, "result__bar")

    def seed_votes(self):
        for option in (self.sinema, self.sinema, self.restoran):
            self.vote(option, client=Client())

    def test_non_voter_sees_only_the_total_on_detail_and_feed(self):
        self.seed_votes()
        detail = self.client.get(self.detail_url)
        self.assert_results_hidden(detail)
        self.assertContains(detail, "<span data-total-votes>3</span> oy")
        self.assertNotContains(detail, "67%")
        self.assertNotContains(detail, "33%")
        feed = self.client.get("/")
        self.assert_results_hidden(feed)
        self.assertContains(feed, "<span data-total-votes>3</span> oy")

    def test_voter_sees_results_after_voting(self):
        self.seed_votes()
        self.vote(self.restoran)
        detail = self.client.get(self.detail_url)
        self.assert_results_shown(detail)
        self.assertContains(detail, "50% · 2")  # 4 votes: 2 sinema, 2 restoran
        self.assertContains(detail, "✓ Restoran")
        self.assert_results_shown(self.client.get("/"))

    def test_owner_sees_results_without_voting(self):
        self.seed_votes()
        client = Client()
        client.force_login(self.owner)
        self.assert_results_shown(client.get(self.detail_url))
        self.assert_results_shown(client.get("/"))

    def test_everyone_sees_results_once_the_poll_is_closed(self):
        self.seed_votes()
        self.poll.closed_at = timezone.now()
        self.poll.save()
        self.assert_results_shown(self.client.get(self.detail_url))

    def test_everyone_sees_results_once_the_poll_expired(self):
        self.seed_votes()
        self.poll.expires_at = timezone.now() - timedelta(minutes=5)
        self.poll.save()
        detail = self.client.get(self.detail_url)
        self.assert_results_shown(detail)
        self.assertContains(detail, "Bitti")

    def test_other_guest_still_cannot_see_results(self):
        self.vote(self.sinema)  # self.client voted
        self.assert_results_hidden(Client().get(self.detail_url))

    def test_profile_page_follows_the_same_rule(self):
        self.seed_votes()
        self.assert_results_hidden(self.client.get(reverse("polls:profile", args=["sahip"])))
        self.vote(self.sinema)
        self.assert_results_shown(self.client.get(reverse("polls:profile", args=["sahip"])))

    def test_service_rule_function(self):
        user = make_user("uye")
        self.assertFalse(services.can_see_results(self.poll, user=None, voter_key=None))
        self.assertFalse(services.can_see_results(self.poll, user=user, voter_key=f"u:{user.pk}"))
        self.assertTrue(services.can_see_results(self.poll, user=self.owner, voter_key=None))
        services.cast_vote(poll=self.poll, option_id=self.sinema.pk, voter_key=f"u:{user.pk}", user=user)
        self.assertTrue(services.can_see_results(self.poll, user=user, voter_key=f"u:{user.pk}"))

    def test_results_are_not_in_context_for_non_voters(self):
        self.seed_votes()
        response = self.client.get(self.detail_url)
        self.assertIsNone(response.context["poll"].results)


class DetailChangeVoteTests(VotingTestCase):
    def test_voter_sees_change_link_and_can_reopen_the_form(self):
        self.vote(self.sinema)
        detail = self.client.get(self.detail_url)
        self.assertContains(detail, "Oyumu değiştir")
        editing = self.client.get(self.detail_url + "?degistir=1")
        self.assertContains(editing, "data-vote-form")
        self.assertContains(editing, "option--current")
        self.assertNotContains(editing, "result__bar")

    def test_change_param_is_ignored_for_non_voters_owners_and_closed_polls(self):
        self.assertContains(self.client.get(self.detail_url + "?degistir=1"), "data-vote-form")  # normal form anyway
        owner = Client()
        owner.force_login(self.owner)
        self.assertNotContains(owner.get(self.detail_url + "?degistir=1"), "data-vote-form")
        self.vote(self.sinema)
        self.poll.closed_at = timezone.now()
        self.poll.save()
        closed = self.client.get(self.detail_url + "?degistir=1")
        self.assertNotContains(closed, "data-vote-form")
        self.assertContains(closed, "result__bar")


class PercentageTests(TestCase):
    def test_no_votes_is_all_zero_without_error(self):
        self.assertEqual(utils.percentages([0, 0, 0]), [0, 0, 0])
        self.assertEqual(utils.percentages([]), [])

    def test_total_never_exceeds_100(self):
        for counts in ([1, 1, 1], [1, 1, 1, 1, 1, 1, 1], [3, 3, 3, 1], [2, 1], [5], [1, 0], [7, 11, 13, 17, 19]):
            with self.subTest(counts=counts):
                self.assertLessEqual(sum(utils.percentages(counts)), 100)

    def test_known_values(self):
        self.assertEqual(utils.percentages([1, 1, 1]), [34, 33, 33])
        self.assertEqual(utils.percentages([2, 1]), [67, 33])
        self.assertEqual(utils.percentages([1, 1]), [50, 50])
        self.assertEqual(utils.percentages([7, 0, 0]), [100, 0, 0])

    def test_zero_vote_poll_results_render_when_closed(self):
        owner = make_user("sahip")
        poll = make_poll(owner, expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get(reverse("polls:detail", args=[poll.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0% · 0")

    def test_leading_option_is_flagged_and_ties_share_it(self):
        owner = make_user("sahip")
        poll = make_poll(owner, options=("A", "B", "C"))
        a, b, c = list(poll.options.all())
        for option in (a, a, b, b, c):
            services.cast_vote(poll=poll, option_id=option.pk, voter_key=f"a:{uuid.uuid4()}")
        results = services.get_results(poll)
        leading = {item["label"] for item in results["options"] if item["is_leading"]}
        self.assertEqual(leading, {"A", "B"})
        self.assertEqual(results["total"], 5)
