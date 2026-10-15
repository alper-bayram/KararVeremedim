"""Fills the database with demo users, polls and votes.

    python manage.py seed_demo            # asks for confirmation, then seeds
    python manage.py seed_demo --purge    # removes the demo users (and their polls/votes)

The command talks to whatever database `.env` points to (Supabase when DATABASE_URL is set),
so it always shows the target and waits for the operator to type "evet".
Passwords are random, printed once and written to `seed_credentials.txt` (git-ignored).
"""

import random
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from accounts.models import User
from polls import services
from polls.models import Poll, Vote

DEMO_USERNAMES = [
    "demo_ayse", "demo_mehmet", "demo_zeynep", "demo_can", "demo_elif",
    "demo_burak", "demo_selin", "demo_emre", "demo_deniz", "demo_merve",
]
EMAIL_DOMAIN = "example.com"  # reserved domain: these addresses can never receive mail

# (question, category, options, duration key)
POLLS = [
    ("Bu akşam sinemaya mı gitsem, restorana mı?", "entertainment", ["Sinema", "Restoran"], "24h"),
    ("Hafta sonu için hangi dizi maratonuna başlamalıyım?", "entertainment", ["Suç draması", "Komedi", "Bilim kurgu", "Belgesel"], "3d"),
    ("Cumartesi akşamı arkadaşlarla ne yapalım?", "entertainment", ["Bowling", "Oyun gecesi", "Karaoke", "Piknik", "Sinema"], "7d"),
    ("Öğle yemeği için canım ne çekmeli?", "food", ["Lahmacun", "Hamburger", "Salata"], "24h"),
    ("Kahvaltıda hangisi vazgeçilmez olmalı?", "food", ["Menemen", "Simit-peynir", "Pankek", "Omlet"], "24h"),
    ("Tatlı krizi: hangisini sipariş edeyim?", "food", ["Sütlaç", "Baklava"], "3d"),
    ("Akşam yemeği için evde ne pişirsem?", "food", ["Makarna", "Kuru fasulye", "Tavuk sote", "Mantı", "Pilav üstü döner"], "3d"),
    ("Yeni telefon alırken hangisine öncelik vermeliyim?", "technology", ["Kamera", "Batarya", "Fiyat", "Ekran"], "7d"),
    ("Laptop mı tablet mi almalıyım?", "technology", ["Laptop", "Tablet"], "3d"),
    ("Kulaklık seçerken hangisi daha önemli?", "technology", ["Ses kalitesi", "Gürültü engelleme", "Fiyat"], "24h"),
    ("Yeni bir programlama dili öğrenmek istiyorum, hangisi?", "technology", ["Python", "JavaScript", "Go", "Rust", "Kotlin"], "7d"),
    ("Tatilde deniz mi, doğa mı tercih etmeliyim?", "travel", ["Deniz", "Doğa"], "24h"),
    ("Yurt dışı için ilk durak neresi olsun?", "travel", ["Roma", "Prag", "Lizbon", "Budapeşte"], "7d"),
    ("Hafta sonu kaçamağı için hangi şehir?", "travel", ["İzmir", "Bursa", "Eskişehir"], "3d"),
    ("Kamp mı otel mi?", "travel", ["Kamp", "Butik otel", "Pansiyon"], "24h"),
    ("Yüksek lisansa başlasam mı yoksa çalışsam mı?", "career", ["Yüksek lisans", "Çalışmak"], "7d"),
    ("Hangi sertifika kariyerime daha çok katkı sağlar?", "career", ["Proje yönetimi", "Veri analizi", "Bulut", "Siber güvenlik"], "7d"),
    ("Sınav haftasında nasıl çalışmalıyım?", "career", ["Sabah erken", "Gece geç", "Gün içine yay"], "3d"),
    ("Staj için hangi sektör daha mantıklı?", "career", ["Teknoloji", "Finans", "Medya", "Sağlık", "Üretim"], "3d"),
    ("Arkadaşımın doğum günü için hangi hediye?", "relationships", ["Kitap", "Kupa seti", "Deneyim bileti", "Bitki"], "3d"),
    ("Ona ilk adımı atıp mesaj yazsam mı?", "relationships", ["Evet yaz", "Biraz bekle"], "24h"),
    ("Yıldönümü için sürpriz mi sakin bir akşam mı?", "relationships", ["Sürpriz", "Sakin akşam", "Mini tatil"], "7d"),
    ("Aile yemeğine ne götürmeliyim?", "relationships", ["Tatlı", "Meyve tabağı", "Çiçek"], "24h"),
    ("Kış montu alacağım, hangisi?", "shopping", ["Şişme mont", "Parka", "Trençkot"], "3d"),
    ("Spor ayakkabı için hangi marka?", "shopping", ["Nike", "Adidas", "New Balance", "Puma"], "7d"),
    ("İndirimde bu çantayı almalı mıyım?", "shopping", ["Al", "Vazgeç"], "24h"),
    ("Ev için hangi küçük dekor ürünü?", "shopping", ["Bitki", "Halı", "Mum seti", "Duvar posteri", "Lamba"], "3d"),
    ("Haftaya sabah koşusuna başlasam mı?", "other", ["Başla", "Akşam koş", "Yürüyüşle başla"], "3d"),
    ("Evcil hayvan edinmeli miyim?", "other", ["Kedi", "Köpek", "Balık", "Hiçbiri"], "7d"),
    ("Yeni yıl için hangi hedefi seçmeliyim?", "other", ["Spor", "Kitap okuma", "Yeni dil", "Tasarruf", "Seyahat"], "7d"),
]


class Command(BaseCommand):
    help = "Creates demo users, polls and votes (or removes them with --purge)."

    def add_arguments(self, parser):
        parser.add_argument("--purge", action="store_true", help="Delete the demo users together with their polls and votes.")
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt (for local testing).")
        parser.add_argument("--seed", type=int, default=2026, help="Random seed for reproducible votes.")

    # ---- helpers --------------------------------------------------------------

    def _target(self) -> str:
        db = connection.settings_dict
        host = db.get("HOST") or "(dosya)"
        return f"{db['ENGINE'].rsplit('.', 1)[-1]} · {host} · {db['NAME']}"

    def _confirm(self, action: str, assume_yes: bool) -> None:
        self.stdout.write(self.style.WARNING(f"Hedef veritabanı: {self._target()}"))
        self.stdout.write(f"Bu işlem: {action}")
        if assume_yes:
            return
        answer = input('Devam etmek için "evet" yaz: ').strip().lower()
        if answer != "evet":
            raise CommandError("İptal edildi, hiçbir değişiklik yapılmadı.")

    # ---- main -----------------------------------------------------------------

    def handle(self, *args, **options):
        if options["purge"]:
            return self._purge(options["yes"])
        self._seed(options["yes"], random.Random(options["seed"]))

    def _purge(self, assume_yes: bool) -> None:
        users = User.objects.filter(username__in=DEMO_USERNAMES)
        self._confirm(
            f"{users.count()} demo kullanıcı, {Poll.objects.filter(author__in=users).count()} anketi ve oyları silinecek.",
            assume_yes,
        )
        deleted, _ = users.delete()
        self.stdout.write(self.style.SUCCESS(f"Silindi ({deleted} kayıt)."))

    def _seed(self, assume_yes: bool, rng: random.Random) -> None:
        existing = User.objects.filter(username__in=DEMO_USERNAMES).count()
        self._confirm(
            f"{len(DEMO_USERNAMES) - existing} yeni kullanıcı, {len(POLLS)} anket ve bu kullanıcıların oyları eklenecek "
            f"(zaten var olan demo kullanıcılar: {existing}).",
            assume_yes,
        )

        users, credentials = [], []
        for username in DEMO_USERNAMES:
            email = f"{username.replace('_', '.')}@{EMAIL_DOMAIN}"
            user = User.objects.filter(username=username).first()
            if user:
                credentials.append((username, email, "(zaten vardı, parola değiştirilmedi)"))
            else:
                password = secrets.token_urlsafe(12)
                user = User.objects.create_user(username=username, email=email, password=password)
                credentials.append((username, email, password))
            users.append(user)

        if Poll.objects.filter(author__in=users).exists():
            self.stdout.write(self.style.WARNING("Demo kullanıcıların anketleri zaten var; anket ve oy eklenmedi."))
            polls = []
        else:
            polls = self._create_polls(users, rng)
            self._cast_votes(users, polls, rng)

        self._report(credentials, len(polls))

    def _create_polls(self, users, rng) -> list[Poll]:
        polls = []
        now = timezone.now()
        for index, (question, category, options, duration) in enumerate(POLLS):
            author = users[index % len(users)]
            poll = services.create_poll(
                author=author, question=question, category=category, options=options, duration=duration
            )
            # Spread creation times so the feed looks lived-in; polls stay open.
            lifetime = services.DURATIONS[duration][1]
            created = now - lifetime * rng.uniform(0.05, 0.6)
            Poll.objects.filter(pk=poll.pk).update(created_at=created, expires_at=created + lifetime)
            poll.refresh_from_db()
            polls.append(poll)
        return polls

    def _cast_votes(self, users, polls, rng) -> None:
        for poll in polls:
            options = list(poll.options.all())
            # Uneven weights so some options clearly lead.
            weights = [rng.uniform(0.5, 3.0) for _ in options]
            for user in users:
                if user.pk == poll.author_id or rng.random() > 0.8:
                    continue
                option = rng.choices(options, weights=weights)[0]
                vote = services.cast_vote(poll=poll, option_id=option.pk, voter_key=f"u:{user.pk}", user=user)
                moment = poll.created_at + (timezone.now() - poll.created_at) * rng.random()
                Vote.objects.filter(pk=vote.pk).update(created_at=moment, updated_at=moment)

    def _report(self, credentials, poll_count: int) -> None:
        new_accounts = [row for row in credentials if not row[2].startswith("(")]
        lines = ["kullanıcı_adı | e-posta | parola"]
        lines += [f"{username} | {email} | {password}" for username, email, password in credentials]
        text = "\n".join(lines)

        self.stdout.write(self.style.SUCCESS(f"\nTamam: {len(new_accounts)} yeni kullanıcı, {poll_count} anket işlendi.\n"))
        self.stdout.write(text)

        if not new_accounts:
            self.stdout.write(self.style.WARNING("\nYeni parola üretilmedi; mevcut kimlik dosyasına dokunulmadı."))
            return
        # Never overwrite an earlier credentials file: those passwords cannot be recovered.
        base = Path(settings.BASE_DIR)
        path = base / "seed_credentials.txt"
        if path.exists():
            path = base / f"seed_credentials_{timezone.now():%Y%m%d_%H%M%S}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        path.chmod(0o600)
        self.stdout.write(self.style.WARNING(f"\nBilgiler ayrıca şu dosyaya yazıldı (git'e girmez): {path}"))
