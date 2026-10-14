# KararVeremedim — Proje Spesifikasyonu (Prototip)

> Bu dosya Claude Code için projenin tek doğruluk kaynağıdır. Her oturumda önce bu dosyayı oku.
> **Amaç bir prototip çıkarmaktır.** Basit, okunabilir ve az bağımlılıklı çözümleri seç. Burada yazmayan bir konuda karar vermen gerekirse en basit yolu uygula ve "Açık Kararlar" bölümüne bir satır ekle.
> Proje **fazlar** halinde ilerler. Sadece kullanıcının istediği fazı uygula, sonraki fazlara geçme.

---

## 1. Proje Özeti

**KararVeremedim**, kullanıcıların kararsız kaldıkları konularda anket açarak diğer kullanıcılara danıştığı bir web uygulamasıdır.

- Kullanıcı bir soru sorar (ör. *"Bu akşam sinemaya mı gitsem, restorana mı?"*).
- Soruya **en az 2, en fazla 5** seçenek ekler.
- Platformdaki **herkes** anketi görür ve oy verebilir.
- **Takip mekanizması yoktur.** Tek bir ortak akış vardır; her anket herkese görünür.

**Arayüz dili:** Türkçe. **Kod dili** (değişken, fonksiyon, model, commit mesajı): İngilizce.

---

## 2. Teknoloji Yığını

| Katman | Seçim |
|---|---|
| Backend | Python 3.12+, Django (güncel kararlı sürüm) |
| Veritabanı | Supabase (yalnızca **PostgreSQL veritabanı** olarak; Django ORM ile bağlanılır) |
| Frontend | Django şablonları + saf **HTML, CSS, JavaScript** (framework yok, build adımı yok, aynı repo) |
| Kimlik doğrulama | Django'nun yerleşik auth sistemi (Supabase Auth **kullanılmaz**) |
| Deploy | Vercel (Django zero-config desteği) |

**Python bağımlılıkları (minimum):**
- `Django`
- `psycopg[binary]` (PostgreSQL sürücüsü)
- `dj-database-url` (veritabanı bağlantı adresini okumak için)
- `python-dotenv` (yerelde `.env` okumak için)

Başka paket eklemeden önce gerçekten gerekli olup olmadığını düşün. CSS/JS için npm, Tailwind, React vb. **kullanılmaz**.

### 2.1 Supabase Bağlantısı
- Django, Supabase'e `DATABASE_URL` ortam değişkeni üzerinden bağlanır.
- Üretimde (Vercel) Supabase'in **connection pooler** adresi kullanılır (transaction mode, port 6543). Bu durumda ayarlarda:
  - `CONN_MAX_AGE = 0`
  - `DISABLE_SERVER_SIDE_CURSORS = True`
- Yerel geliştirmede `DATABASE_URL` tanımlı değilse SQLite'a düşülebilir. Ama mümkün olduğunca Supabase'deki ayrı bir geliştirme veritabanı kullanılmalı (PostgreSQL farklarından kaynaklı sürprizler olmasın).
- Migration'lar Vercel üzerinde değil, **yerelden** `python manage.py migrate` ile Supabase'e uygulanır.

### 2.2 Supabase Güvenlik Notu (önemli)
Supabase, `public` şemasındaki tabloları kendi REST API'si (Data API) üzerinden dışarıya açar. Biz bu API'yi kullanmıyoruz. Bu yüzden şunlardan biri **mutlaka** yapılmalı:
1. Supabase panelinden Data API kapatılır, **veya**
2. Tüm tablolarda RLS açılır ve hiçbir policy eklenmez. Bunun için bir Django migration'ı içinde `RunSQL` ile `alter table ... enable row level security;` çalıştırılır. Django'nun kullandığı `postgres` rolü RLS'ten etkilenmez.

Tercih: **2. seçenek** (kodda kalıcı ve görünür olduğu için).

### 2.3 Vercel Notları
- Vercel, kök dizindeki `manage.py`'yi bularak Django projesini otomatik tanır. `vercel.json` gerekmez.
- Statik dosyalar Vercel CDN'den sunulur. `STATIC_URL`/`STATIC_ROOT` ayarlarını uygularken Vercel'in güncel Django dokümantasyonunu kontrol et: https://vercel.com/docs/frameworks/full-stack/django
- `ALLOWED_HOSTS` içinde `.vercel.app` ve ileride eklenecek alan adı bulunmalı. `CSRF_TRUSTED_ORIGINS` da buna göre ayarlanmalı.
- Vercel Functions sınırlamaları geçerlidir (kalıcı dosya sistemi yok, istek süresi sınırlı). Bu yüzden kullanıcı dosya yüklemesi prototipte yoktur.

---

## 3. Kullanıcılar ve Yetkiler

| İşlem | Misafir (üye değil) | Üye |
|---|---|---|
| Akışı ve anketleri görmek | ✅ | ✅ |
| Oy vermek | ✅ | ✅ |
| Anket oluşturmak | ❌ (kayıt/giriş sayfasına yönlendirilir) | ✅ |
| Kendi anketini kapatmak / silmek | — | ✅ |

### 3.1 Kayıt
Kayıt formu alanları:
- **E-posta** — zorunlu, benzersiz (büyük/küçük harf duyarsız karşılaştırma, küçük harfe çevrilerek kaydedilir)
- **Kullanıcı adı** — zorunlu, benzersiz, 3–20 karakter, yalnızca `a-z`, `0-9`, `_`; küçük harfe çevrilerek kaydedilir
- **Parola** ve **Parola (tekrar)** — Django'nun yerleşik parola doğrulayıcıları kullanılır

Kayıttan sonra kullanıcı otomatik olarak giriş yapmış olur ve geldiği sayfaya (`next`) veya ana sayfaya yönlendirilir.

### 3.2 Giriş / Çıkış
- Giriş **e-posta + parola** ile yapılır.
- Çıkış `POST` isteği ile yapılır (Django gereksinimi).
- Parola sıfırlama prototipte **yok** (e-posta gönderimi gerektirir; sonraki sürüme bırakıldı).

### 3.3 Gizlilik
- Anketlerde, profil sayfasında ve herhangi bir yerde **yalnızca kullanıcı adı** gösterilir.
- **E-posta adresi hiçbir sayfada, hiçbir JSON yanıtında ve hiçbir HTML kaynağında görünmez.** Şablonlara kullanıcı nesnesi geçilirken buna dikkat edilmeli.

### 3.4 Kullanıcı Modeli
- Projenin **en başında** özel kullanıcı modeli tanımlanır (`accounts.User`, `AbstractUser` tabanlı). Bu, Django'da sonradan değiştirilmesi zor bir karardır; Faz 1'de değil, **Faz 0'da** oluşturulmalı ve ilk migration'da yer almalıdır.
- `email` alanı `unique=True`.
- `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`.
- `AUTH_USER_MODEL = "accounts.User"`.

---

## 4. Anket Kuralları

| Alan | Kural |
|---|---|
| Soru | Zorunlu, 10–200 karakter |
| Açıklama | Opsiyonel, en fazla 500 karakter |
| Kategori | Zorunlu, sabit listeden biri (bkz. 4.3) |
| Seçenekler | **En az 2, en fazla 5**; her biri 1–80 karakter; aynı anket içinde tekrar edemez (boşluklar kırpılıp küçük harfle karşılaştırılır) |
| Süre | 1 saat, 6 saat, 24 saat (varsayılan), 3 gün, 7 gün |

- Anket oluşturulduktan sonra **düzenlenemez**.
- Anket sahibi anketini **erken kapatabilir** veya **silebilir**.
- Süresi dolan anket otomatik olarak kapalı sayılır (`expires_at` geçmişse). Bunun için zamanlanmış görev gerekmez; durum her istekte hesaplanır.
- Bir kullanıcı günde en fazla **10 anket** açabilir.

### 4.1 Oylama
- Her anket için **kişi başı 1 oy** vardır.
- Kişinin kimliği:
  - **Üye ise:** kullanıcı ID'si.
  - **Misafir ise:** tarayıcıya yazılan imzalı bir çerez (`kv_voter`, rastgele UUID, `httponly`, `samesite=Lax`, 1 yıl geçerli). Django'nun `set_signed_cookie` / `get_signed_cookie` fonksiyonları kullanılır.
- Bu kimlik, `Vote` modelindeki `voter_key` alanına yazılır:
  - Üye: `"u:<user_id>"`
  - Misafir: `"a:<uuid>"`
- Veritabanında `unique(poll, voter_key)` kısıtı bulunur.
- Kişi anket açık olduğu sürece **oyunu değiştirebilir** (mevcut oy güncellenir).
- Anket sahibi **kendi anketine oy veremez**.
- Kapalı ankete oy verilemez.
- Oy verilen seçenek mutlaka o ankete ait olmalıdır.

> Bilinen sınırlama: Misafir kullanıcı çerezleri silerek veya gizli sekme açarak tekrar oy verebilir. Prototip için kabul edilmiştir (bkz. Açık Kararlar).

### 4.2 Sonuçların Görünürlüğü
Seçenek bazlı sonuçlar (oy sayısı ve yüzde) yalnızca şu durumlarda gösterilir:
1. Kişi o ankete oy vermişse,
2. Kişi anketin sahibiyse,
3. Anket kapanmışsa.

Diğer durumlarda yalnızca **toplam oy sayısı** gösterilir. Bu kural yalnızca arayüzde değil, sunucu tarafında da uygulanır: sonuçlar şablona veya JSON yanıtına hiç eklenmez.

### 4.3 Kategoriler
| Anahtar | Etiket | Emoji |
|---|---|---|
| `food` | Yemek | 🍕 |
| `entertainment` | Eğlence | 🎬 |
| `shopping` | Alışveriş | 🛍️ |
| `travel` | Seyahat | ✈️ |
| `career` | Okul & Kariyer | 🎓 |
| `relationships` | İlişkiler | 💬 |
| `technology` | Teknoloji | 📱 |
| `other` | Diğer | ✨ |

`TextChoices` ile `polls/models.py` içinde tanımlanır.

---

## 5. Veri Modelleri

```python
# accounts/models.py
class User(AbstractUser):
    email = models.EmailField(unique=True)
    # username: AbstractUser'dan gelir; özel validator ile a-z0-9_, 3–20 karakter
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]


# polls/models.py
class Poll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(max_length=200)
    description = models.TextField(max_length=500, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)  # erken kapatıldıysa

    @property
    def is_open(self) -> bool: ...  # closed_at yoksa ve expires_at gelecekteyse

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]),
                   models.Index(fields=["category", "-created_at"])]


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField()  # 0–4

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["poll", "position"], name="unique_option_position")]


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    voter_key = models.CharField(max_length=64)  # "u:<id>" veya "a:<uuid>"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["poll", "voter_key"], name="one_vote_per_voter")]
```

**Kurallar**
- Oy sayıları prototipte `annotate(Count(...))` ile hesaplanır. Sayaç kolonu eklenmez (gerekirse ileride eklenir).
- İş mantığı view'larda değil, `polls/services.py` içinde toplanır: `create_poll(...)`, `cast_vote(...)`, `close_poll(...)`, `get_results(...)`, `can_see_results(...)`. Bu fonksiyonlar `transaction.atomic` kullanır ve kural ihlalinde anlamlı bir istisna fırlatır (ör. `PollClosedError`, `OwnVoteError`).
- Seçenek sayısı (2–5) hem formda hem `create_poll` servisinde kontrol edilir.

---

## 6. Sayfalar ve URL'ler

| URL | Sayfa | Erişim |
|---|---|---|
| `/` | Ana akış | Herkes |
| `/anket/<uuid>/` | Anket detayı, oy verme, sonuçlar | Herkes |
| `/anket/yeni/` | Anket oluşturma | Üye (`login_required`) |
| `/anket/<uuid>/oy/` | Oy verme (POST, JSON veya yönlendirme döner) | Herkes |
| `/anket/<uuid>/kapat/` | Anketi kapat (POST) | Sahibi |
| `/anket/<uuid>/sil/` | Anketi sil (POST) | Sahibi |
| `/u/<username>/` | Kullanıcının açtığı anketler | Herkes |
| `/kayit/` | Kayıt | Misafir |
| `/giris/` | Giriş | Misafir |
| `/cikis/` | Çıkış (POST) | Üye |
| `/admin/` | Django admin (moderasyon) | Süper kullanıcı |

### 6.1 Ana Akış (`/`)
- Sıralama sekmeleri: **Yeni** (varsayılan) ve **Popüler** (son 24 saatte en çok oy alan açık anketler).
- Kategori filtresi (emojili, yatay kaydırılabilir "chip"ler).
- Varsayılan olarak yalnızca açık anketler görünür; "Bitenleri de göster" seçeneği bulunur.
- Sayfa başına 20 anket, Django `Paginator` ile. Altta **"Daha fazla göster"** butonu bulunur; JS ile bir sonraki sayfanın HTML parçasını çekip listeye ekler. JS yoksa normal sayfa linki olarak çalışır.
- Filtreler URL'de tutulur: `/?sirala=populer&kategori=food`
- Üye olmayan kullanıcıya üstte "Kararsız mısın? Ücretsiz üye ol, sen de sor!" şeklinde kapatılabilir bir davet bandı gösterilir.

### 6.2 Anket Kartı
- Kategori emojisi + etiketi, soru, `@kullaniciadi`, göreli zaman ("3 saat önce")
- Kalan süre ("5 saat kaldı") veya "Bitti" etiketi
- Toplam oy sayısı
- Seçenekler doğrudan kartta tıklanabilir butonlardır. Oy verildiğinde kart, sayfa yenilenmeden sonuç çubuklarına dönüşür. Kişinin seçtiği seçenek işaretlenir, önde olan seçenek vurgulanır.

### 6.3 Anket Detayı (`/anket/<uuid>/`)
- Kartın tüm içeriği + açıklama
- Oy verme ve oy değiştirme ("Oyumu değiştir" linki)
- Sonuç çubukları (yüzde + oy sayısı)
- "Linki kopyala" butonu (`navigator.share` destekleniyorsa paylaşım menüsü açılır)
- Sahibi için "Anketi bitir" ve "Sil" butonları (JS `confirm` ile onay)

### 6.4 Anket Oluşturma (`/anket/yeni/`)
- Soru alanı + canlı karakter sayacı
- Opsiyonel açıklama
- Kategori seçimi (emojili kartlar veya radio butonlar)
- Başlangıçta **2 seçenek alanı**:
  - "+ Seçenek ekle" ile 5'e kadar artırılır; 5'te buton gizlenir.
  - 3. seçenekten itibaren her alanda "×" silme butonu bulunur; 2'nin altına düşülemez.
  - Bu davranış saf JS ile yapılır. Sunucu tarafında Django `formset` **yerine** basit bir yaklaşım kullanılabilir: `option_1` … `option_5` adlı alanlar okunur, boş olanlar atılır, kalan sayının 2–5 arasında olduğu doğrulanır.
- Süre seçimi (segmentli buton görünümünde radio'lar)
- Hatalar alanların altında Türkçe olarak gösterilir.
- Başarılı oluşturmadan sonra detay sayfasına yönlendirilir ve "Anketin yayında! 🎉" mesajı gösterilir (Django `messages` framework).

---

## 7. Oy Verme Akışı (JS + Sunucu)

1. Kullanıcı seçeneğe tıklar.
2. JS, `fetch` ile `/anket/<uuid>/oy/` adresine `POST` atar (`option_id` gönderir, `X-CSRFToken` başlığı eklenir).
3. Sunucu:
   - `voter_key`'i belirler. Misafirse ve çerez yoksa yeni UUID üretip çerezi yanıta ekler.
   - `cast_vote` servisini çağırır.
   - Başarılıysa: `{ "ok": true, "total": 42, "my_option_id": 7, "results": [{ "id": 7, "label": "Sinema", "votes": 25, "percent": 60 }, ...] }`
   - Hata varsa: `{ "ok": false, "error": "Bu anket sona ermiş." }` ve uygun HTTP kodu.
4. JS sonuç çubuklarını çizer; çubuk genişlikleri CSS `transition` ile animasyonla dolar.
5. **JS kapalıysa** aynı form normal `POST` ile çalışır ve sunucu detay sayfasına yönlendirir (progressive enhancement).

Yüzdeler tam sayıya yuvarlanır. Toplam 0 ise bölme hatası olmamalı. Yuvarlama sonrası toplam 100'ü geçmemeli.

---

## 8. Arayüz Tasarımı

**Hedef his:** Genç, enerjik, eğlenceli ama temiz ve sade. Açık arka plan üzerinde canlı renkler ve bu renklerin yumuşak tonları (tint) kullanılır.

### 8.1 Renk Paleti (CSS değişkenleri, `static/css/main.css` başında)
```css
:root {
  /* zemin ve metin */
  --bg: #FBF9FF;          /* çok açık lila-beyaz zemin */
  --surface: #FFFFFF;     /* kart zemini */
  --text: #1F1B2E;        /* koyu mürdüm-siyah */
  --muted: #6E6A80;
  --border: #ECE8F5;

  /* canlı vurgu renkleri */
  --violet: #7B2FF7;      /* ana renk (butonlar, linkler) */
  --pink:   #FF3D81;
  --orange: #FF8A1F;
  --yellow: #FFC233;
  --mint:   #12C99B;
  --sky:    #2D8CFF;

  /* tonlar: canlı rengin açık yıkanmış hali */
  --violet-tint: color-mix(in srgb, var(--violet) 12%, white);
  --pink-tint:   color-mix(in srgb, var(--pink) 12%, white);
  --orange-tint: color-mix(in srgb, var(--orange) 14%, white);
  --yellow-tint: color-mix(in srgb, var(--yellow) 18%, white);
  --mint-tint:   color-mix(in srgb, var(--mint) 14%, white);
  --sky-tint:    color-mix(in srgb, var(--sky) 12%, white);

  --radius: 18px;
  --radius-sm: 12px;
  --shadow: 0 6px 24px rgba(123, 47, 247, 0.08);
}
```

### 8.2 Kullanım Kuralları
- **Seçenek renkleri:** Her anketin seçenekleri sırayla `violet`, `pink`, `orange`, `mint`, `sky` renklerini alır. Seçenek butonunun zemini ilgili **tint**, kenarı/ikonu ve sonuç çubuğu ise ilgili **canlı renk**tir.
- **Kategori chip'leri:** Her kategori sabit bir tint zemine sahiptir; seçili olan canlı renkle dolar ve beyaz yazılı olur.
- **Ana buton** ("Anket oluştur"): `violet`'ten `pink`'e hafif bir gradyan, beyaz yazı, tam yuvarlak köşeler (pill). Hover'da hafif yükselme (`translateY(-2px)`) ve gölge artışı.
- **Kartlar:** beyaz zemin, `--radius`, ince `--border`, yumuşak `--shadow`. Kartlar arasında bol boşluk bulunur.
- **Logo:** "Karar**Veremedim**" yazısı; ikinci kelime violet→pink gradyan metin. Yanında 🤔 emojisi.
- **Tipografi:** Google Fonts'tan **"Plus Jakarta Sans"** (400/600/800); fallback `system-ui, sans-serif`. Türkçe karakterlerin (ğ, ü, ş, ı, İ, ö, ç) doğru göründüğü kontrol edilmeli. Başlıklar kalın (800), gövde 16px.
- **Boş durumlar:** emoji + dostane bir metin (ör. "Burası çok sessiz 🦗 İlk kararsızlığı sen paylaş!").
- **Mikro etkileşimler:** oy çubuklarının dolma animasyonu, buton hover efektleri, oy verilince seçilen seçenekte küçük bir "pop" (`transform: scale`) animasyonu. Abartılmamalı. `prefers-reduced-motion` durumunda animasyonlar kapatılmalı.
- **Koyu tema:** prototipte **yok**.

### 8.3 Düzen
- **Mobil öncelikli.** 360px genişlikte sorunsuz çalışmalı. Masaüstünde içerik ortalanır, en fazla ~680px genişliğinde tek sütun akış kullanılır.
- **Üst bar:** logo (solda). Sağda misafir için "Giriş" + "Üye ol", üye için "@kullaniciadi" + "Çıkış". Masaüstünde ayrıca "+ Anket oluştur" butonu bulunur.
- **Mobilde** sağ altta sabit, yuvarlak, gradyanlı **"+"** butonu (FAB) bulunur. Misafir tıklarsa kayıt sayfasına yönlendirilir (`next` parametresiyle).
- **Erişilebilirlik:** tüm butonlar klavyeyle kullanılabilir, `:focus-visible` stilleri belirgin, metin kontrastı yeterli (tint zemin üzerinde koyu metin kullanılır, canlı renk üzerinde yalnızca beyaz kalın metin).

### 8.4 Frontend Dosyaları
- `static/css/main.css` — tek CSS dosyası (gerekirse bölümlere yorumla ayrılır).
- `static/js/main.js` — tek JS dosyası. ES modülleri veya saf fonksiyonlar kullanılır. `defer` ile yüklenir.
- jQuery veya başka bir kütüphane **kullanılmaz**.
- Göreli zaman ve kalan süre metinleri sunucuda Türkçe olarak üretilir. Gerekirse JS ile `Intl.RelativeTimeFormat('tr')` kullanılır.

---

## 9. Klasör Yapısı

```
.
├── CLAUDE.md
├── manage.py
├── requirements.txt
├── pyproject.toml          # (Vercel Python sürümü/entrypoint gerekirse)
├── .env.example
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/
│   ├── models.py  forms.py  views.py  urls.py  admin.py
│   └── tests.py
├── polls/
│   ├── models.py  forms.py  views.py  urls.py  admin.py
│   ├── services.py         # iş kuralları
│   ├── utils.py            # voter_key, zaman biçimlendirme, yüzde hesaplama
│   ├── migrations/
│   └── tests/
├── templates/
│   ├── base.html
│   ├── partials/           # _poll_card.html, _results.html, _messages.html, _header.html
│   ├── accounts/           # register.html, login.html
│   └── polls/              # feed.html, detail.html, create.html, profile.html
└── static/
    ├── css/main.css
    ├── js/main.js
    └── img/                # favicon vb.
```

---

## 10. Ortam Değişkenleri

`.env` (repoya eklenmez) ve `.env.example` (repoya eklenir):

```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=True
DATABASE_URL=postgresql://...      # Supabase bağlantı adresi
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
```

Üretimde `DJANGO_DEBUG=False` olmalı. Ayrıca `SESSION_COOKIE_SECURE` ve `CSRF_COOKIE_SECURE` açık olmalı.

---

## 11. Test Gereksinimleri

Django'nun yerleşik `TestCase` sınıfı kullanılır (`python manage.py test`). Prototip için şu testler yeterlidir:

**Üyelik**
- Aynı e-posta ile ikinci kayıt reddedilir (büyük/küçük harf farkı olsa bile).
- Aynı kullanıcı adı ile ikinci kayıt reddedilir.
- Geçersiz kullanıcı adı (ör. `ab`, `Ali Veli`, `çağrı`) reddedilir.
- Herkese açık sayfaların HTML çıktısında e-posta adresi geçmez.

**Anket**
- Misafir `/anket/yeni/` adresine girince giriş sayfasına yönlendirilir.
- 1 seçenekli ve 6 seçenekli anket oluşturulamaz; 2 ve 5 seçenekli oluşturulabilir.
- Tekrar eden seçenek reddedilir.
- Günlük 10 anket limiti çalışır.

**Oylama**
- Misafir oy verebilir; aynı çerezle ikinci oy, mevcut oyu günceller (yeni kayıt oluşmaz).
- Üye aynı ankete iki kez oy kaydı oluşturamaz.
- Sahip kendi anketine oy veremez.
- Kapalı/süresi dolmuş ankete oy verilemez.
- Başka ankete ait seçenekle oy verilemez.
- Oy vermemiş kişi sonuçları göremez; oy verince görür; anket kapanınca herkes görür.
- Yüzde hesaplama: 0 oyda hata yok, toplam 100'ü geçmiyor.

---

## 12. Claude Code Çalışma Kuralları

1. **Sadece istenen fazı uygula.** Faz bitince dur, yapılanları özetle ve kullanıcının test etmesi için çalıştırma adımlarını yaz.
2. Her fazdan önce kısa bir plan yaz, sonra uygula.
3. Her faz sonunda `python manage.py check` ve `python manage.py test` hatasız geçmeli.
4. Veritabanı değişikliği her zaman Django migration'ı ile yapılır. Uygulanmış migration'lar düzenlenmez.
5. Gizli bilgiler (secret key, veritabanı parolası) asla koda veya commit'e eklenmez.
6. Arayüz metinleri Türkçe, kod İngilizce yazılır.
7. Her formda `{% csrf_token %}` bulunur. JS `fetch` isteklerinde CSRF başlığı gönderilir.
8. Kullanıcı girdisi şablonlarda her zaman Django'nun otomatik escape'i ile basılır. `|safe` kullanılmaz.
9. İş kuralları `services.py` içinde tutulur. View'lar ince kalır.
10. Gereksiz soyutlama yapılmaz. Prototip için okunabilir ve düz kod tercih edilir.
11. Commit mesajları İngilizce, Conventional Commits formatında yazılır (`feat:`, `fix:`, `chore:` ...).
12. Belirsiz durumda en basit çözüm uygulanır ve "Açık Kararlar" bölümüne not eklenir.

---

## 13. Fazlar

Her faz tek başına çalışan, test edilebilir bir sonuç üretir. Tamamlanan faz kutucuğu işaretlenir.

### Faz 0 — İskelet ve Tasarım Temeli
- [x] Django projesi (`config`) ve `accounts`, `polls` uygulamaları
- [x] **Özel `User` modeli** (bölüm 3.4) ve ilk migration
- [ ] `.env` okuma, `DATABASE_URL` ile Supabase bağlantısı (bölüm 2.1) — kod hazır, Supabase projesi açılınca `DATABASE_URL` ile doğrulanacak
- [ ] Supabase güvenliği için RLS migration'ı (bölüm 2.2) — `accounts/0002` yazıldı, PostgreSQL'de henüz çalıştırılmadı (SQLite'ta atlanır)
- [x] `requirements.txt`, `.env.example`, `.gitignore`
- [x] `base.html`: üst bar, mesaj alanı, Google Font, `main.css` ve `main.js` bağlantıları
- [x] `main.css`: renk değişkenleri, tipografi, buton/kart/chip temel stilleri (bölüm 8)
- [x] Geçici bir ana sayfa (tasarım öğelerini gösteren örnek kart ve butonlar)
- **Bitti sayılır:** `runserver` ile açılan sayfa tasarım diline uygun görünüyor, `migrate` Supabase'de çalışıyor.

### Faz 1 — Üyelik
- [ ] Kayıt formu (e-posta, kullanıcı adı, parola ×2) ve doğrulamaları
- [ ] Giriş (e-posta + parola) ve çıkış
- [ ] `next` parametresiyle geri yönlendirme
- [ ] Üst barda giriş durumuna göre linkler
- [ ] Django admin'de `User` kaydı (e-posta yalnızca admin'de görünür)
- [ ] Bölüm 11'deki üyelik testleri

### Faz 2 — Anket Oluşturma ve Görüntüleme
- [ ] `Poll`, `Option`, `Vote` modelleri ve migration
- [ ] `services.create_poll` + form + `/anket/yeni/` sayfası (dinamik 2–5 seçenek JS'i)
- [ ] Ana akış: kart listesi, kategori filtresi, Yeni/Popüler sıralama, sayfalama + "Daha fazla göster"
- [ ] Anket detay sayfası (oy verme henüz yok, yalnızca seçenekler ve toplam oy sayısı)
- [ ] Kullanıcı profil sayfası `/u/<username>/`
- [ ] Misafir için davet bandı ve FAB yönlendirmesi
- [ ] Django admin'de anket listesi/silme (moderasyon)
- [ ] Bölüm 11'deki anket testleri

### Faz 3 — Oylama ve Sonuçlar
- [ ] `voter_key` mantığı (üye ID / imzalı misafir çerezi)
- [ ] `services.cast_vote` + `/anket/<uuid>/oy/` endpoint'i (JSON + JS'siz form desteği)
- [ ] Kartta ve detayda oy verme, oy değiştirme
- [ ] Sonuç görünürlük kuralları (bölüm 4.2)
- [ ] Animasyonlu sonuç çubukları, seçilen ve önde olan seçeneğin vurgulanması
- [ ] Bölüm 11'deki oylama testleri

### Faz 4 — Anket Yönetimi ve Cilalama
- [ ] Anketi erken bitirme ve silme (yalnızca sahibi)
- [ ] Kalan süre / "Bitti" etiketleri, "Bitenleri de göster" filtresi
- [ ] Linki kopyala / paylaş butonu
- [ ] Boş durumlar, 404 ve 500 sayfaları (tasarıma uygun)
- [ ] Mobil görünüm ve erişilebilirlik kontrolü
- [ ] Sayfa başlıkları ve temel meta etiketleri (anket sorusu `<title>`'da)

### Faz 5 — Yayın (Vercel)
- [ ] Üretim ayarları (`DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, güvenli çerezler)
- [ ] Statik dosyaların Vercel'de sunulması (güncel Vercel Django dokümanına göre)
- [ ] Supabase pooler bağlantısı (bölüm 2.1)
- [ ] Vercel ortam değişkenleri
- [ ] Migration'ların üretim veritabanına uygulanması, süper kullanıcı oluşturulması
- [ ] Canlı ortamda uçtan uca elle test: kayıt → anket oluştur → başka tarayıcıdan misafir olarak oy ver

> Not: İstenirse Faz 5, Faz 1'den hemen sonra da yapılabilir. Erken deploy, Vercel'e özgü sorunları erkenden yakalar.

### Sonraki Sürümler İçin Fikirler (prototip dışı)
- Parola sıfırlama (e-posta gönderimi)
- Misafir oylarında kötüye kullanımı azaltmak için IP bazlı hız sınırı
- Anketlere yorum
- "Kararımı verdim: X'i seçtim 🎯" güncellemesi
- Anket raporlama
- Koyu tema
- Paylaşım için dinamik önizleme görseli

---

## 14. Faz Promptları (Claude Code'a yapıştırmak için)

**Faz 0**
> CLAUDE.md dosyasını baştan sona oku. Ardından yalnızca "Faz 0 — İskelet ve Tasarım Temeli" bölümünü uygula. Özel User modelini ilk migration'dan önce oluşturmayı unutma. Başlamadan önce kısa bir plan yaz. Bitince `manage.py check` çalıştır, yaptıklarını özetle ve projeyi yerelde nasıl çalıştıracağımı adım adım yaz. Faz 1'e geçme.

**Faz 1**
> CLAUDE.md'ye göre "Faz 1 — Üyelik" bölümünü uygula. E-postanın hiçbir herkese açık sayfada görünmediğinden emin ol. Bölüm 11'deki üyelik testlerini yaz ve çalıştır. Bitince CLAUDE.md'deki Faz 1 kutucuklarını işaretle, özet ver ve dur.

**Faz 2**
> CLAUDE.md'ye göre "Faz 2 — Anket Oluşturma ve Görüntüleme" bölümünü uygula. 2–5 seçenek kuralını hem formda hem services.py'de uygula. Arayüz bölüm 8'deki tasarım diline uymalı. Testleri yaz ve çalıştır. Bitince kutucukları işaretle, özet ver ve dur.

**Faz 3**
> CLAUDE.md'ye göre "Faz 3 — Oylama ve Sonuçlar" bölümünü uygula. Misafir oyları için imzalı çerez kullan (bölüm 4.1), sonuç görünürlük kuralını sunucu tarafında uygula (bölüm 4.2), oy akışını bölüm 7'deki gibi kur. Testleri yaz ve çalıştır. Bitince kutucukları işaretle, özet ver ve dur.

**Faz 4**
> CLAUDE.md'ye göre "Faz 4 — Anket Yönetimi ve Cilalama" bölümünü uygula. Özellikle 360px mobil görünümü kontrol et. Bitince kutucukları işaretle, özet ver ve dur.

**Faz 5**
> CLAUDE.md'ye göre "Faz 5 — Yayın (Vercel)" bölümünü uygula. Önce Vercel'in güncel Django dokümanını kontrol et. Benim elle yapmam gereken adımları (Supabase panelinde, Vercel panelinde) ayrı bir liste olarak yaz.

---

## 15. Açık Kararlar

- Kimlik doğrulama Django auth ile yapılır. Supabase yalnızca PostgreSQL veritabanı olarak kullanılır.
- Misafirler oy verebilir. Tekrar oyu yalnızca imzalı çerezle engellenir. Çerez silinirse tekrar oy verilebilir (prototip için kabul edildi).
- Anket sahibi kendi anketine oy veremez.
- Sonuçlar oy vermeden görünmez (sahibi ve biten anketler hariç).
- Oy, anket açık olduğu sürece değiştirilebilir.
- Silinen kullanıcının anketleri de silinir. Verdiği oylar ise anonim olarak kalır (`SET_NULL`).
- Parola sıfırlama prototipte yok.
- Python sürümü: `.venv` Python 3.14 ile kuruldu. Vercel 3.12 (varsayılan), 3.13 ve 3.14'ü destekliyor (doğrulandı, Ekim 2026).
- Supabase projesi henüz yok: `DATABASE_URL` boşsa SQLite'a düşülür. Proje açılınca `.env`'ye session pooler adresi (port 5432) yazılıp yerelden `migrate` çalıştırılacak.
- RLS migration'ı `public` şemasındaki tüm tablolara RLS açar (Django'nun kendi tabloları dahil). Yeni tablo ekleyen her fazın migration'ına aynı `config.rls.enable_rls_on_public_tables` eklenir.
- `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`.
- "Popüler" sıralaması: son 24 saatte verilen oy sayısına göre; eşitlikte yeni olan öne çıkar.
- Misafir sonradan üye olursa `voter_key` değiştiği için eski misafir oyları taşınmaz ve yeniden oy verebilir (prototip için kabul edildi).
