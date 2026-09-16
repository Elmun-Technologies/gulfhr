# Gulf HR botini Fly.io'ga deploy qilish — bosqichma-bosqich

Bot Telegram'dan **long-polling** orqali update oladi. Fly proxy uchun ilova
ichida faqat `/health` endpoint tinglaydi; bu endpoint bot API'si emas.
`fly.toml` dagi `auto_stop_machines = 'off'` sozlamasini olib tashlamang —
aks holda Fly idling deb hisoblab, Telegram polling jarayonini to'xtatishi mumkin.

> **Vercel nima uchun ishlamagan edi?** Bu bot — Telegram **long-polling**
> boti: u 24/7 doimiy ishlab turadigan jarayon. Vercel esa **serverless**
> veb-platforma — u `app/main.py`'dan veb-ilova (`app` / `application` /
> `handler`) kutadi va har so'rovdan keyin jarayonni o'chirib yuboradi.
> Shuning uchun *"does not export a top-level app..."* xatosi chiqqan —
> bu env lar bilan emas, arxitektura farqi bilan bog'liq. Doimiy ishlaydigan
> bot uchun Fly.io, Railway, Render yoki VPS kerak.

## 0. Tayyorgarlik (bir marta)

**flyctl** (Fly.io CLI) o'rnatiladi:

```bash
# macOS / Linux
curl -L https://fly.io/install.sh | sh

# macOS (Homebrew)
brew install flyctl

# Windows (PowerShell)
irm https://fly.io/install.ps1 | iex
```

Fly.io'da akkaunt ochasiz va login qilasiz:

```bash
fly auth signup   # yoki mavjud akkaunt bo'lsa: fly auth login
```

> Fly.io kichik "shared-cpu-1x / 256MB" mashinada oyiga bir necha dollar
> turadi (ushbu loyiha uchun aynan shu o'lcham yetarli, `fly.toml`'da
> allaqachon shunday belgilangan).

## 1. App yaratish (deploy qilmasdan)

Loyiha ildizida (bu fayl turgan papkada):

```bash
fly launch --no-deploy
```

- Fly `Dockerfile`'ni avtomatik topadi — **Use existing Dockerfile?** → ha.
- **App name** → `gulf-hr` (band bo'lsa: `fly.toml`'da `app = 'gulf-hr-...'`
  deb o'zgartiring va qaytadan `fly launch --no-deploy`).
- **Set up a Postgresql database?** → **Yo'q** (SQLite + volume yetarli).
- **Set up an Upstash Redis database?** → **Yo'q**.
- **Tweak settings?** → Yo'q — sozlama `fly.toml`'da tayyor.

## 2. Ma'lumotlar uchun volume yaratish (deploy'dan OLDIN)

Arizalar va `/stats` analitikasi SQLite'da (`/app/data/gulf_hr.db`)
saqlanadi. Volume'siz har deploy'da baza **yo'qoladi**:

```bash
fly volumes create gulf_hr_data --region ams --size 1
```

## 3. Maxfiy sozlamalar (secrets)

`.env` fayl Fly.io'ga yuklanmaydi — qiymatlar `fly secrets` orqali
beriladi (siz Vercel'da kiritgan env lar shularga to'g'ri keladi):

```bash
# MAJBURIY — BotFather'dan olingan token
fly secrets set BOT_TOKEN="123456:AAG-...token..."

# Nomzod kartalari yuboriladigan HR guruhi (manfiy son!)
fly secrets set CANDIDATES_CHAT_ID="-1001234567890"
```

Ixtiyoriy (default qiymatlari `app/config.py`'da):

```bash
fly secrets set CANDIDATE_MIN_AGE="18" \
               CANDIDATE_MAX_AGE="30" \
               CANDIDATE_CITY="Toshkent" \
               CANDIDATE_RUSSIAN_REQUIRED="true" \
               MANAGEMENT_CHAT_ID="-1001234567890" \
               LOG_LEVEL="INFO"
```

Tekshirish:

```bash
fly secrets list
```

## 4. Deploy

```bash
fly deploy
```

Birinchi deploy 2–4 daqiqa oladi (Docker image quriladi). Ohirida
`v1 deployed` degan yozuv chiqishi kerak.

## 5. Ishlayotganini tekshirish

```bash
fly status   # status=running bo'lishi kerak
fly logs     # pastdagi yozuvlarni kuzating
```

Loglarda quyidagilarni ko'rasiz:

```
Gulf HR bot ishga tushmoqda...
Baza tayyor: sqlite+aiosqlite
FSM bazasi tayyor: ./data/fsm.db ...
Health server tinglamoqda: 0.0.0.0:8080
```

Fly deploy paytida `The app is not listening on 0.0.0.0:8080` degan warning
chiqsa, lokal `fly.toml` dagi qo'lda kiritilgan eski o'zgarishlar asosiy
faylni bosib ketgan bo'ladi. Ularni tiklang va qayta deploy qiling:

```bash
git restore fly.toml
fly deploy
```

Telegram'da botga `/start` yozib sinang — ariza oqimi boshlanishi kerak.

## Keyingi yangilashlar

Kodni o'zgartirgach (git push qilgandan keyin):

```bash
fly deploy
```

Env qiymatini o'zgartirish (bot avtomatik qayta ishga tushadi):

```bash
fly secrets set CANDIDATE_MAX_AGE="35"
```

## Muammoli holatlar

| Xato / belgi | Yechim |
|---|---|
| `name "gulf-hr" is already taken` | `fly.toml`'da `app = 'gulf-hr-elmun'` kabi noyob nom qo'ying → `fly launch --no-deploy` |
| Deploy'da `no volume found` | 2-bosqich o'tkazib yuborilgan: `fly volumes create gulf_hr_data --region ams --size 1` |
| Logda `BOT_TOKEN sozlanmagan` | `fly secrets set BOT_TOKEN="..."` (deploy qaytarish shart emas — avtomatik restart) |
| Logda `Telegram: Unauthorized` | Token xato/eski — BotFather'dan qayta oling va `fly secrets set` bilan yangilang |
| HR guruhiga karta bormaydi | Botni guruhga **admin** qilib qo'shing; guruh ID `CANDIDATES_CHAT_ID` (yoki `MANAGEMENT_CHAT_ID`) sifatida to'g'ri kiritilganini tekshiring |
| Bot ikkinchi nusxasi bilan 409 conflict | Boshqa joyda (kompyuter/Vercel/esh) shu token bilan bot ishlamasin — bitta token = bitta ishlaydigan nusxa |
| Boshqarish uchun | `fly ssh console` (ichiga kirish), `fly apps restart gulf-hr` (qayta ishga tushirish) |

## Eslatma

- `leadbot/` (eski alohida bot) uchun alohida sozlama bor:
  `fly.leadbot.toml`. Uni deploy qilish shart emas — asosiy bot
  `app/` ichida hammasini qiladi.
- Vercel loyihasini o'chirib tashlash tavsiya etiladi (chalkashlik
  bo'lmasin): Vercel dashboard → Settings → Delete Project.
