# 🤔 KararVeremedim

Kararsız kaldığın konularda anket aç, herkese danış.

**Canlı demo:** https://kararveremedim.vercel.app

KararVeremedim, kullanıcıların *"Bu akşam sinemaya mı gitsem, restorana mı?"* gibi kararsız kaldıkları konularda 2-5 seçenekli anketler açtığı ve herkesin oy verebildiği küçük bir web uygulamasıdır. Üye olmadan da oy verilebilir.

> Bu bir **deneme (prototip) projesidir.** Basit, okunabilir ve az bağımlılıklı olacak şekilde yazıldı; üretim kullanımı için tasarlanmadı. Bilinen sınırlamalar aşağıda.

---

## Özellikler

- **Üyelik:** E-posta, kullanıcı adı ve parola ile kayıt. E-posta **veya** kullanıcı adı ile giriş. E-posta adresi hiçbir sayfada görünmez.
- **Anket oluşturma:** Soru, açıklama, kategori (8 kategori), 2-5 seçenek ve süre (1 saat - 7 gün). Günde en fazla 10 anket.
- **Oy verme:** Üyeler ve misafirler oy verebilir (misafirler imzalı çerezle). Anket açıkken oy değiştirilebilir. Sahibi kendi anketine oy veremez.
- **Sonuç gizliliği:** Seçenek bazlı sonuçları yalnızca oy verenler, anketin sahibi ve anket bittikten sonra herkes görür. Bu kural sunucuda uygulanır.
- **Anket yönetimi:** Sahibi anketini bitirebilir, silebilir; henüz oy almamışsa düzenleyebilir. **Anketlerim** sayfası bunun için vardır.
- **Akış:** Yeni / Popüler sekmeleri, kategori filtresi, "Bitenleri de göster", "Daha fazla göster" (JS'siz de çalışır).
- **Paylaşım:** Linki kopyala / sistem paylaşım menüsü.
- **Mobil öncelikli arayüz:** 360px'te çalışır, klavye ve `prefers-reduced-motion` desteği.
- **Parolamı unuttum sayfası:** Sayfa hazır ama şimdilik yalnızca e-postayı alır, e-posta göndermez ve hiçbir şey kaydetmez.

## Teknoloji

| Katman | Seçim |
|---|---|
| Backend | Python 3.12+, Django 6.1 |
| Veritabanı | Supabase (yalnızca PostgreSQL olarak, Django ORM ile) |
| Frontend | Django şablonları + saf HTML/CSS/JavaScript (framework ve derleme adımı yok) |
| Kimlik doğrulama | Django'nun yerleşik auth sistemi |
| Yayın | Vercel (Django zero-config) |

Python bağımlılıkları: `Django`, `psycopg[binary]`, `dj-database-url`, `python-dotenv`.

---

## Yerelde çalıştırma

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

Panel `/admin/` adresindedir.

### Ortam değişkenleri

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

### Testler

```bash
DATABASE_URL= python manage.py test
```

`DATABASE_URL=` ön eki, testlerin Supabase üzerinde test veritabanı açmaya çalışmasını engeller ve SQLite kullanır. Tek bir testi çalıştırmak için:

```bash
DATABASE_URL= python manage.py test polls.tests.test_voting
```

### Demo verisi

```bash
python manage.py seed_demo           # 10 kullanıcı, 30 anket ve oylar ekler
python manage.py seed_demo --purge   # demo kullanıcıları (anket ve oylarıyla) siler
```

Komut hedef veritabanını gösterir ve `evet` yazmadan çalışmaz. Üretilen rastgele parolalar `seed_credentials.txt` dosyasına yazılır (git'e girmez).

---

## Proje yapısı

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

## Dağıtım

- `main` dalına her push, Vercel tarafından otomatik olarak yayınlanır.
- Statik dosyalar `STATIC_ROOT` sayesinde Vercel CDN'inden sunulur.
- Üretimde Supabase'in **transaction pooler** adresi (port 6543) kullanılır; bu yüzden bağlantı ayarlarında `CONN_MAX_AGE=0`, sunucu tarafı imleçler kapalı ve hazır ifadeler (prepared statements) devre dışıdır.
- Veritabanı değişiklikleri Vercel'de değil, **yerelden** `python manage.py migrate` ile uygulanır.
- Supabase `public` şemasındaki tabloları kendi REST API'siyle dışarı açtığı için, tüm tablolarda **Row Level Security** açıktır (policy yoktur). Tablo ekleyen her migration'ın bunu yeniden çalıştırması gerekir (`config/rls.py`).

## Bilinen sınırlamalar

- Misafir oyları çerezle takip edilir; çerezleri silen biri tekrar oy verebilir. Misafir üye olursa eski oyu taşınmaz.
- Giriş denemelerine ve oy vermeye hız sınırı yoktur.
- Parola sıfırlama ve hesap silme/parola değiştirme yoktur (sıfırlama sayfası yalnızca iskelettir).
- Test altyapısı yereldir; otomatik CI yoktur.
