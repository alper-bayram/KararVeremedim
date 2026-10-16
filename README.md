# 🤔 KararVeremedim

**[English](#english)** · **[Türkçe](#türkçe)**

**Live demo / Canlı demo:** https://kararveremedim.vercel.app

---

## English

> *KararVeremedim* is Turkish for "I couldn't decide".

Can't make up your mind? Create a poll and ask everyone.

KararVeremedim is a small web app where people post polls about decisions they are stuck on (*"Should I go to the cinema or a restaurant tonight?"*) with 2–5 options, and everyone can vote. Voting works without an account.

> This is a **prototype / experiment.** It was written to be simple, readable and light on dependencies, and it is not meant for production use. Known limitations are listed below.

**Status:** Complete for its intended scope (all phases of the spec are done), deployed on Vercel, and covered by 213 automated tests.

### Features

- **Accounts:** Sign up with e-mail, username and password. Sign in with your e-mail **or** your username. E-mail addresses are never shown on any page.
- **Create polls:** Question, optional description, one of 8 categories, 2–5 options and a duration (1 hour – 7 days). Up to 10 polls per day.
- **Voting:** Members and guests (via a signed cookie) can vote. You can change your vote while the poll is open. Authors cannot vote on their own poll.
- **Result privacy:** Per-option results are visible only to people who voted, to the poll's author, and to everyone once the poll has ended. This is enforced on the server.
- **Poll management:** Authors can close or delete their polls, and edit them as long as nobody has voted yet. The **Anketlerim** ("My polls") page collects these actions.
- **Feed:** New / Popular tabs, category filter, "show finished polls", and a "load more" button that also works without JavaScript.
- **Sharing:** Copy the link or use the native share sheet.
- **Mobile-first UI:** Works at 360 px, keyboard accessible, respects `prefers-reduced-motion`.
- **"Forgot password" page:** The page exists, but for now it only collects an e-mail address: it sends nothing and stores nothing.

### Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, Django 6.1 |
| Database | Supabase (used only as PostgreSQL, through the Django ORM) |
| Frontend | Django templates + plain HTML/CSS/JavaScript (no framework, no build step) |
| Authentication | Django's built-in auth |
| Hosting | Vercel (Django zero-config) |

Python dependencies: `Django`, `psycopg[binary]`, `dj-database-url`, `python-dotenv`.

### Run locally

```bash
git clone https://github.com/alper-bayram/KararVeremedim.git
cd KararVeremedim

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # ships with DJANGO_DEBUG=True and an empty DATABASE_URL (SQLite)
python manage.py migrate
python manage.py runserver
```

The app is then available at http://localhost:8000. For the admin panel:

```bash
python manage.py createsuperuser   # asks for e-mail, username and password
```

The panel lives at `/admin/` (sign in with the e-mail address).

#### Environment variables

Read from `.env` (not committed); see `.env.example`.

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Required when `DJANGO_DEBUG=False`. Use a long random value in production |
| `DJANGO_DEBUG` | `True` locally, `False` in production (default `False`) |
| `DATABASE_URL` | Supabase PostgreSQL URL. **Falls back to local SQLite when empty** |
| `ALLOWED_HOSTS` | Comma-separated hosts (default `localhost,127.0.0.1,.vercel.app`) |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins (default `https://*.vercel.app`) |
| `PASSWORD_RESET_PAGE_ENABLED` | Shows or hides the "forgot password" page (default off) |

> ⚠️ When `DATABASE_URL` is set, every command uses **that** database. Leave it empty for local experiments to use SQLite.

#### Tests

```bash
DATABASE_URL= python manage.py test
```

The `DATABASE_URL=` prefix keeps the tests on SQLite instead of trying to create a test database on Supabase. To run a single module:

```bash
DATABASE_URL= python manage.py test polls.tests.test_voting
```

#### Demo data

```bash
python manage.py seed_demo           # adds 10 users, 30 polls and their votes
python manage.py seed_demo --purge   # removes the demo users (with their polls and votes)
```

The command prints its target database and waits for you to type `evet` ("yes"). The generated random passwords are written to `seed_credentials.txt` (git-ignored).

### Project layout

```
config/        Django settings, URLs, RLS helper (rls.py)
accounts/      Custom User model, sign-up/sign-in, e-mail-or-username backend
polls/
  models.py    Poll, Option, Vote, Category
  services.py  Business rules: create, edit, vote, result visibility, close/delete
  utils.py     Guest identity (signed cookie), percentages, time formatting
  views.py     Thin views
  management/  seed_demo command
templates/     Django templates (partials/ holds the card, results and header)
static/        One CSS file and one JS file
docs/          Project specification (KararVeremedim.md, in Turkish)
```

Business rules live in `polls/services.py`, not in the views. See [`docs/KararVeremedim.md`](docs/KararVeremedim.md) for the full specification and decisions (in Turkish, especially the "Açık Kararlar" section).

### Deployment

- Every push to `main` is deployed automatically by Vercel.
- Static files are served from the Vercel CDN thanks to `STATIC_ROOT`.
- Production uses Supabase's **transaction pooler** (port 6543), so connections are not persistent (`CONN_MAX_AGE=0`), server-side cursors are disabled and prepared statements are turned off.
- Database migrations are applied **locally** with `python manage.py migrate`, not on Vercel.
- Supabase exposes tables in the `public` schema through its REST API, so **Row Level Security** is enabled on every table (with no policies). Any migration that adds tables has to run it again (`config/rls.py`).

### Known limitations

- Guest votes are tracked with a cookie: someone who clears cookies can vote again, and a guest who signs up does not keep the earlier vote.
- There is no rate limiting for sign-in attempts or voting.
- There is no password reset (the page is only a skeleton), password change or account deletion.
- Tests run locally only; there is no CI.

---

## Türkçe

Kararsız mı kaldın? Anket aç, herkese danış.

KararVeremedim, kullanıcıların *"Bu akşam sinemaya mı gitsem, restorana mı?"* gibi kararsız kaldıkları konularda 2-5 seçenekli anketler açtığı ve herkesin oy verebildiği küçük bir web uygulamasıdır. Üye olmadan da oy verilebilir.

> Bu bir **deneme (prototip) projesidir.** Basit, okunabilir ve az bağımlılıklı olacak şekilde yazıldı; üretim kullanımı için tasarlanmadı. Bilinen sınırlamalar aşağıda.

**Durum:** Hedeflenen kapsam tamamlandı (spesifikasyondaki tüm fazlar bitti), Vercel'de yayında ve 213 otomatik testle kapsanıyor.

### Özellikler

- **Üyelik:** E-posta, kullanıcı adı ve parola ile kayıt. E-posta **veya** kullanıcı adı ile giriş. E-posta adresi hiçbir sayfada görünmez.
- **Anket oluşturma:** Soru, açıklama, kategori (8 kategori), 2-5 seçenek ve süre (1 saat - 7 gün). Günde en fazla 10 anket.
- **Oy verme:** Üyeler ve misafirler oy verebilir (misafirler imzalı çerezle). Anket açıkken oy değiştirilebilir. Sahibi kendi anketine oy veremez.
- **Sonuç gizliliği:** Seçenek bazlı sonuçları yalnızca oy verenler, anketin sahibi ve anket bittikten sonra herkes görür. Bu kural sunucuda uygulanır.
- **Anket yönetimi:** Sahibi anketini bitirebilir, silebilir; henüz oy almamışsa düzenleyebilir. **Anketlerim** sayfası bunun için vardır.
- **Akış:** Yeni / Popüler sekmeleri, kategori filtresi, "Bitenleri de göster", "Daha fazla göster" (JS'siz de çalışır).
- **Paylaşım:** Linki kopyala / sistem paylaşım menüsü.
- **Mobil öncelikli arayüz:** 360px'te çalışır, klavye ve `prefers-reduced-motion` desteği.
- **Parolamı unuttum sayfası:** Sayfa hazır ama şimdilik yalnızca e-postayı alır, e-posta göndermez ve hiçbir şey kaydetmez.

### Teknoloji

| Katman | Seçim |
|---|---|
| Backend | Python 3.12+, Django 6.1 |
| Veritabanı | Supabase (yalnızca PostgreSQL olarak, Django ORM ile) |
| Frontend | Django şablonları + saf HTML/CSS/JavaScript (framework ve derleme adımı yok) |
| Kimlik doğrulama | Django'nun yerleşik auth sistemi |
| Yayın | Vercel (Django zero-config) |

Python bağımlılıkları: `Django`, `psycopg[binary]`, `dj-database-url`, `python-dotenv`.

### Yerelde çalıştırma

```bash
git clone https://github.com/alper-bayram/KararVeremedim.git
cd KararVeremedim

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # DJANGO_DEBUG=True ve boş DATABASE_URL (SQLite) ile gelir
python manage.py migrate
python manage.py runserver
```

Uygulama http://localhost:8000 adresinde açılır. Yönetim paneli için:

```bash
python manage.py createsuperuser   # e-posta, kullanıcı adı, parola sorar
```

Panel `/admin/` adresindedir (e-posta ile giriş yapılır).

#### Ortam değişkenleri

`.env` (repoya eklenmez) dosyası aşağıdaki değişkenleri okur; örnek için `.env.example`'a bak.

| Değişken | Açıklama |
|---|---|
| `DJANGO_SECRET_KEY` | Zorunlu (`DJANGO_DEBUG=False` iken). Üretimde uzun, rastgele bir değer olmalı |
| `DJANGO_DEBUG` | Yerelde `True`, üretimde `False` (varsayılan `False`) |
| `DATABASE_URL` | Supabase PostgreSQL adresi. **Boşsa yerel SQLite'a düşer** |
| `ALLOWED_HOSTS` | Virgülle ayrılmış alan adları (varsayılan `localhost,127.0.0.1,.vercel.app`) |
| `CSRF_TRUSTED_ORIGINS` | Güvenilen kaynaklar (varsayılan `https://*.vercel.app`) |
| `PASSWORD_RESET_PAGE_ENABLED` | "Parolamı unuttum" sayfasını açar/kapatır (varsayılan kapalı) |

> ⚠️ `DATABASE_URL` tanımlıysa komutlar **o veritabanını** kullanır. Yerel denemelerde SQLite için değişkeni boş bırak.

#### Testler

```bash
DATABASE_URL= python manage.py test
```

`DATABASE_URL=` ön eki, testlerin Supabase üzerinde test veritabanı açmaya çalışmasını engeller ve SQLite kullanır. Tek bir modülü çalıştırmak için:

```bash
DATABASE_URL= python manage.py test polls.tests.test_voting
```

#### Demo verisi

```bash
python manage.py seed_demo           # 10 kullanıcı, 30 anket ve oylar ekler
python manage.py seed_demo --purge   # demo kullanıcıları (anket ve oylarıyla) siler
```

Komut hedef veritabanını gösterir ve `evet` yazmadan çalışmaz. Üretilen rastgele parolalar `seed_credentials.txt` dosyasına yazılır (git'e girmez).

### Proje yapısı

```
config/        Django ayarları, URL'ler, RLS yardımcısı (rls.py)
accounts/      Özel User modeli, kayıt/giriş, e-posta-veya-kullanıcı-adı backend'i
polls/
  models.py    Poll, Option, Vote, Category
  services.py  İş kuralları: oluşturma, düzenleme, oy verme, sonuç görünürlüğü, bitir/sil
  utils.py     Misafir kimliği (imzalı çerez), yüzde hesabı, zaman biçimlendirme
  views.py     İnce görünümler
  management/  seed_demo komutu
templates/     Django şablonları (partials/ altında kart, sonuç, başlık parçaları)
static/        Tek CSS ve tek JS dosyası
docs/          Proje spesifikasyonu (KararVeremedim.md)
```

İş kuralları görünümlerde değil `polls/services.py` içindedir. Ayrıntılı kararlar için [`docs/KararVeremedim.md`](docs/KararVeremedim.md) dosyasına bak (özellikle "Açık Kararlar" bölümü).

### Dağıtım

- `main` dalına her push, Vercel tarafından otomatik olarak yayınlanır.
- Statik dosyalar `STATIC_ROOT` sayesinde Vercel CDN'inden sunulur.
- Üretimde Supabase'in **transaction pooler** adresi (port 6543) kullanılır; bu yüzden bağlantılar kalıcı değildir (`CONN_MAX_AGE=0`), sunucu tarafı imleçler kapalıdır ve hazır ifadeler (prepared statements) devre dışıdır.
- Veritabanı değişiklikleri Vercel'de değil, **yerelden** `python manage.py migrate` ile uygulanır.
- Supabase `public` şemasındaki tabloları kendi REST API'siyle dışarı açtığı için, tüm tablolarda **Row Level Security** açıktır (policy yoktur). Tablo ekleyen her migration'ın bunu yeniden çalıştırması gerekir (`config/rls.py`).

### Bilinen sınırlamalar

- Misafir oyları çerezle takip edilir; çerezleri silen biri tekrar oy verebilir. Misafir üye olursa eski oyu taşınmaz.
- Giriş denemelerine ve oy vermeye hız sınırı yoktur.
- Parola sıfırlama (sayfa yalnızca iskelettir), parola değiştirme ve hesap silme yoktur.
- Test altyapısı yereldir; otomatik CI yoktur.
