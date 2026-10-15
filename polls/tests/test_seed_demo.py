import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from django.test import TestCase, override_settings

from accounts.models import User
from polls.management.commands.seed_demo import DEMO_USERNAMES, POLLS
from polls.models import Category, Poll, Vote


class SeedDemoTests(TestCase):
    def run_command(self, *args, base_dir):
        out = StringIO()
        with override_settings(BASE_DIR=Path(base_dir)):
            call_command("seed_demo", *args, stdout=out)
        return out.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def seed(self, *args):
        return self.run_command("--yes", *args, base_dir=self.tmp.name)

    def test_creates_ten_users_thirty_polls_and_votes(self):
        self.seed()
        users = User.objects.filter(username__in=DEMO_USERNAMES)
        polls = Poll.objects.filter(author__in=users)
        self.assertEqual(users.count(), 10)
        self.assertEqual(polls.count(), 30)
        self.assertGreater(Vote.objects.filter(poll__in=polls).count(), 100)

    def test_polls_cover_every_category_and_two_to_five_options(self):
        self.seed()
        polls = Poll.objects.filter(author__username__in=DEMO_USERNAMES)
        self.assertEqual(set(polls.values_list("category", flat=True)), set(Category.values))
        counts = set(polls.annotate(n=Count("options")).values_list("n", flat=True))
        self.assertEqual(counts, {2, 3, 4, 5})
        self.assertTrue(all(poll.is_open for poll in polls))

    def test_every_user_votes_and_nobody_votes_on_their_own_poll(self):
        self.seed()
        votes = Vote.objects.filter(poll__author__username__in=DEMO_USERNAMES)
        self.assertEqual(votes.values("user").distinct().count(), 10)
        self.assertFalse(any(vote.user_id == vote.poll.author_id for vote in votes.select_related("poll")))
        self.assertTrue(all(vote.voter_key == f"u:{vote.user_id}" for vote in votes))

    def test_authors_are_spread_three_polls_each(self):
        self.seed()
        per_author = Poll.objects.values("author").annotate(n=Count("id")).values_list("n", flat=True)
        self.assertEqual(set(per_author), {3})

    def test_every_seeded_question_is_valid(self):
        self.assertEqual(len(POLLS), 30)
        for question, category, options, duration in POLLS:
            with self.subTest(question=question):
                self.assertTrue(10 <= len(question) <= 200)
                self.assertIn(category, Category.values)
                self.assertTrue(2 <= len(options) <= 5)
                self.assertEqual(len({o.lower() for o in options}), len(options))

    def test_emails_use_the_reserved_domain_and_passwords_work(self):
        output = self.seed()
        users = User.objects.filter(username__in=DEMO_USERNAMES)
        self.assertTrue(all(u.email.endswith("@example.com") for u in users))
        ayse = User.objects.get(username="demo_ayse")
        line = next(line for line in output.splitlines() if line.startswith("demo_ayse |"))
        password = line.split(" | ")[2]
        self.assertTrue(ayse.check_password(password))

    def test_credentials_file_is_written_with_owner_only_permissions(self):
        self.seed()
        path = Path(self.tmp.name) / "seed_credentials.txt"
        self.assertTrue(path.exists())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(path.read_text().strip().splitlines()), 11)  # header + 10 users

    def test_second_run_adds_nothing_and_keeps_the_credentials_file(self):
        self.seed()
        path = Path(self.tmp.name) / "seed_credentials.txt"
        original = path.read_text()
        output = self.seed()
        self.assertEqual(Poll.objects.count(), 30)
        self.assertEqual(User.objects.filter(username__in=DEMO_USERNAMES).count(), 10)
        self.assertEqual(path.read_text(), original)
        self.assertIn("dokunulmadı", output)

    def test_is_reproducible_with_the_same_seed(self):
        self.seed("--seed", "7")
        first = sorted(Vote.objects.values_list("poll__question", "option__label", "voter_key"))
        User.objects.filter(username__in=DEMO_USERNAMES).delete()
        # Different users get new ids, so compare labels per poll only.
        self.seed("--seed", "7")
        second = sorted(Vote.objects.values_list("poll__question", "option__label", "voter_key"))
        self.assertEqual([row[:2] for row in first], [row[:2] for row in second])

    def test_purge_removes_users_polls_and_votes_but_not_real_users(self):
        real = User.objects.create_user(username="gercek", email="gercek@example.org", password="x-Kuvvetli-1")
        self.seed()
        self.run_command("--purge", "--yes", base_dir=self.tmp.name)
        self.assertEqual(User.objects.filter(username__in=DEMO_USERNAMES).count(), 0)
        self.assertEqual(Poll.objects.count(), 0)
        self.assertEqual(Vote.objects.count(), 0)
        self.assertTrue(User.objects.filter(pk=real.pk).exists())

    def test_without_yes_it_asks_and_aborts_on_anything_but_evet(self):
        from unittest import mock

        with mock.patch("builtins.input", return_value="hayır"), self.assertRaises(CommandError):
            with override_settings(BASE_DIR=Path(self.tmp.name)):
                call_command("seed_demo", stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)

    def test_confirmation_shows_the_target_database(self):
        output = self.seed()
        self.assertIn("Hedef veritabanı:", output)
