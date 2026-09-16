# Gulf HR — nomzodlarni saralash boti

Oziq-ovqat ingredientlari yetkazib beruvchi **Gulf** kompaniyasi uchun
Telegram bot: **Sotuv menejeri / B2B menejer** vakansiyasi bo'yicha arizalarni
yig'adi, nomzodni bir nechta savol orqali vakansiya talablari bilan
solishtiradi, natijani nomzodga aytadi va to'liq kartani HR guruhiga yuboradi.

## Qanday ishlaydi

```
Facebook reklama → "Botga yozish" tugmasi → Telegram bot (t.me/BOTUSERNAME)
                                                    │
                     Til tanlash: 🇺🇿 O'zbekcha / 🇷🇺 Русский
                                                    │
                     Savollar: ism, jins, yosh, shahar, rus tili, telefon,
                               staj, rezume
                                                    │
                                          Talablar bilan solishtirish
                                                    │
                              ┌─────────────────────┴─────────────────────┐
                              ▼                                           ▼
                    Nomzodga javob (mos/mos emas)              HR guruhiga to'liq karta
                                                                (🟢 mos / 🔴 mos emas + sabab)
```

## Savollar (suhbat oqimi)

```
0️⃣ Til (🇺🇿 O'zbekcha / 🇷🇺 Русский) →
1️⃣ Ism → 2️⃣ Jins (👨 Erkak / 👩 Ayol tugmalari) → 3️⃣ Yosh →
4️⃣ Shahar (Ha/Yo'q) → 5️⃣ Rus tili (Ha/Yo'q — majburiy) → 6️⃣ Telefon →
7️⃣ Staj (matn yozadi) → 8️⃣ Rezume (fayl PDF/DOC yoki golos — ovozli xabar) → ✅ Natija
```

Ish grafigi bo'yicha savol berilmaydi.

## 🌐 Til tanlash (o'zbek / rus)

`/start` bosilganda bot avval tilni so'raydi va **butun suhbat tanlangan tilda**
davom etadi — savollar, tugmalar, xato xabarlari va yakuniy natija (rad etish
sabablari ham) tarjima qilinadi.

- Tugma bosish shart emas: nomzod `o'zbekcha` / `ruscha` / `русский` deb yozsa ham qabul qilinadi.
- Reklama havolasiga til oldindan yozilishi mumkin: `https://t.me/BOTUSERNAME?start=ru`
  — til tanlash oynasisiz darhol ruscha boshlanadi (rus auditoriyasiga reklamada qulay).
- `/lang` — tilni almashtirish (suhbat boshidan boshlanadi).
- `LANGUAGE_CHOICE=false` — oyna o'chiriladi, bot `DEFAULT_LANGUAGE` (default `uz`) da ishlaydi.
- Nomzod qaysi tilda gapirgani bazada saqlanadi va HR kartasida
  `🌐 Suhbat tili: Rus` qatorida ko'rinadi. HR guruhining o'zi o'zbekcha qoladi.

## 🛡 Suhbat uzilib qolmasligi

- **Yozma javoblar ham ishlaydi.** Tugma o'rniga `erkak`, `ha`, `да`, `yo'q` deb
  yozib yuborsalar ham oqim davom etadi.
- **Bot hech qachon jim qolmaydi.** Rasm/stiker yoki mos kelmagan javob kelsa,
  joriy savol qayta yuboriladi (`app/bot/handlers/candidates.py::on_unexpected`).
- **Telegram xatolari oqimni uzmaydi.** Tugma ikki marta bosilsa
  (`message is not modified`), callback eskirgan yoki xabar o'chirilgan bo'lsa —
  keyingi savol baribir yuboriladi.
- **Restart'dan keyin davom etadi.** Suhbat holati `MemoryStorage` o'rniga
  SQLite'ga (`FSM_DB_PATH`) yoziladi: deploy/restart paytida nomzod yozayotgan
  ariza yo'qolmaydi, suhbat to'xtagan joyidan davom etadi.
- **Migratsiya avtomatik.** `init_db()` mavjud bazaga yangi ustunlarni
  (`language`) va indekslarni o'zi qo'shadi — eski baza bilan ham ishlaydi.

## Saralash mezonlari

| Mezon | Tavsif | Sozlash (`.env`) |
|---|---|---|
| Yosh | Default **18-30** | `CANDIDATE_MIN_AGE`, `CANDIDATE_MAX_AGE` |
| Shahar | Nomzod doimiy Toshkentda istiqomat qilishi shart (yotoqxona berilmaydi) | `CANDIDATE_CITY` |
| Rus tili | **Majburiy** — "Yo'q" javobi rad etilishga olib keladi | `CANDIDATE_RUSSIAN_REQUIRED` (default `true`) |

Jins va staj saralash mezoniga kirmaydi — ular shunchaki ma'lumot sifatida
HR guruhiga yuboriladi.

## Bot buyruqlari

- `/start` — ariza boshlash (til tanlashdan boshlanadi; `/start ru` — darhol ruscha)
- `/lang` — tilni almashtirish
- `/cancel` — arizani bekor qilish
- `/help` — yordam
- `/stats` — analitika (faqat HR guruhida, istalgan a'zo yuborishi mumkin)
- `/diag` (`/ping`, `/tezlik`) — diagnostika: Telegram bilan aloqa tezligi, baza
  holati, sekin so'rovlar (HR guruhida; shaxsiy chatda — `ADMIN_USER_IDS` uchun)

## O'rnatish

1. **`.env` faylini tayyorlang**:
   ```bash
   cp .env.example .env
   # BOT_TOKEN va guruh ID larini to'ldiring
   ```

   Asosiy qiymatlar:
   ```
   BOT_TOKEN=...                          # BotFather'dan
   CANDIDATES_CHAT_ID=-1001234567890      # HR guruh ID (karta shu yerga boradi)
   CANDIDATE_MIN_AGE=18
   CANDIDATE_MAX_AGE=30
   CANDIDATE_CITY=Toshkent
   CANDIDATE_RUSSIAN_REQUIRED=true
   ```
   `CANDIDATES_CHAT_ID` bo'sh qoldirilsa `MANAGEMENT_CHAT_ID`, undan keyin
   `LEAD_GROUP_CHAT_ID` (eski sozlama) ishlatiladi.

2. **Ishga tushirish**:

   **Docker bilan** (tavsiya etiladi):
   ```bash
   docker compose up -d --build
   ```

   **Lokal Python bilan:**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.main
   ```

   **Fly.io'da** (batafsil yo'riqoma: **`DEPLOY_FLY.md`** — Vercel
   ishlamaydi, chunki bot long-polling va doimiy jarayon talab qiladi):
   ```bash
   fly launch --no-deploy          # app nomi: gulf-hr
   fly volumes create gulf_hr_data --region ams --size 1
   fly secrets set BOT_TOKEN=... CANDIDATES_CHAT_ID=...
   fly deploy
   ```

3. **HR guruh**: botni guruhga **admin** qilib qo'shing (aks holda
   kartalarni yuborolmaydi) va guruh ID sini oling
   (masalan `-1001234567890`) — uni `.env` ga yozing.

4. **Facebook reklama** (Meta Ads Manager): "Click to Telegram" tugmasi/
   veb-sayt havolasi sifatida `https://t.me/BOTUSERNAME` ni ko'rsating —
   reklamani ko'rgan odam to'g'ridan-to'g'ri botga tushadi va `/start`
   bilan ariza boshlanadi.

## 📊 Analitika (`/stats`)

Har bir topshirilgan ariza asosiy bazaga (`DATABASE_URL`, default:
`./data/gulf_hr.db`) saqlanadi. **HR guruhidagi istalgan a'zo** (admin
bo'lmasa ham) `/stats` buyrug'ini yuborib, umumiy statistikani ko'ra oladi:

```
📊 ANALITIKA

👥 Jami arizalar: 50
✅ Mos kelgan: 30
❌ Mos kelmagan: 20
📅 Bugun: 5

🚫 Rad etish sabablari:
• Yosh chegarasidan tashqari: 12
• Toshkentda yashamaydi: 6
• Rus tilini bilmaydi: 4

🕘 Oxirgi 10 nomzod:
🟢 Aliyev Vali (Erkak) — 22 yosh
🔴 ...
```

Analitika vaqt mintaqasi `TZ` (default: `Asia/Tashkent`) orqali sozlanadi.
Docker/Fly.io'da ma'lumot yo'qolmasligi uchun `/app/data` katalogini
doimiy volume'ga ulash tavsiya etiladi (docker-compose'da ulangan, Fly'da
volume qo'shing).

## Loyiha tuzilishi

```
app/
  bot/          Telegram bot: /start, /lang, /help, fallback, dispatcher, middleware
  candidates/   Ariza oqimi: savollar, matnlar (uz/ru), klaviaturalar, FSM, saralash, HR kartasi
  db/           SQLAlchemy modeli (Application), sessiya, migratsiya va FSM (SQLite) storage
leadbot/        Eski mustaqil lead-bot (noyob; python -m leadbot.main)
tests/          pytest testlari
```

## ⚡ Tezlik

Telegram update'lari long polling orqali olinadi. Fly.io uchun ilova ichida
`/health` liveness endpoint ham `0.0.0.0:8080` da ishlaydi; bu endpoint botning
foydalanuvchi API'si emas. `fly.toml` da `auto_stop_machines = 'off'` qolishi
shart, chunki Telegram polling doimiy jarayon.

**Nomzod sezadigan kechikish = tarmoq RTT × ketma-ket so'rovlar soni.** Shuning
uchun asosiy qoida: bitta bosqichda hamma Telegram so'rovlari **parallel**
ketishi kerak (har biri bitta RTT). `scripts/latency_bench.py` shu raqamni
o'lchaydi, `tests/test_latency_budget.py` esa uni regressiyadan himoya qiladi.

Hozirgi holat (o'lchangan, 80 ms RTT da):

| Qadam | Ketma-ket RTT | Nomzod kutishi |
|---|---|---|
| Har bir tugma bosish (soat + klaviatura + yangi savol) | **1** | ~84 ms |
| Har bir matn javob | **1** | ~84 ms |
| Butun ariza (10 bosqich) | **11** | ~0.9 s |

Nima qilingan:

- **So'rovlar parallel.** Tugma bosilganda `answerCallbackQuery` (soat belgisi),
  `editMessageReplyMarkup` (klaviatura) va yangi savol bir vaqtda yuboriladi
  (`_fast_step`, `app/bot/handlers/candidates.py`). Oldin ular ketma-ket edi:
  3 ta so'rov = 3 RTT (sekin tarmoqda har bir bosqichda bir necha sekund).
- **So'rov timeout qisqartirilgan** (`TG_REQUEST_TIMEOUT`, default 15 s; aiogram
  standarti 60 s edi) — tarmoq uzilsa bot daqiqalab "o'ylanib" qolmaydi.
- **Ulanishlar qayta ishlatiladi** (`keepalive_timeout=45`, `enable_cleanup_closed`)
  — har bir xabar uchun yangi TLS handshake qilinmaydi.
- **`UserLockMiddleware`** — bitta nomzodning update'lari ketma-ket bajariladi
  (aiogram ularni parallel ishlaydi; FSM "o'qi→yoz" poygasi suhbatni
  "keyingi bosqichga o'tmay" qo'yishi mumkin edi). Turli nomzodlar parallel.
- **Xato bo'lsa bot jim qolmaydi** (`app/bot/errors.py`) — nomzodga xabar boradi,
  aks holda xato faqat log'da qolib, nomzod "bot o'ylanib qoldi" deb o'ylardi.
- **Polling backoff tezroq** (0.2-3 s, aiogram standarti 1-5 s) — tarmoq
  uzilishidan keyin bot tezroq tiklanadi.
- **Navbatdagi update'lar saqlanadi** (`DROP_PENDING_UPDATES=false`): bot qayta
  ishga tushganda nomzod bosgan tugma yo'qolmaydi, suhbat FSM bazasidan davom
  etadi. (Avval ular tashlanar edi — nomzod "keyingi etapga o'tmayapti" deb
  ko'rardi.)
- Baza yozuvi va HR guruhiga xabar **parallel** (`asyncio.gather`) bajariladi.
- SQLite `WAL` + `synchronous=NORMAL` + `busy_timeout` rejimida — yozuvlar
  tezroq va parallel suhbatlarda `database is locked` bo'lmaydi.
- `TimingsMiddleware` har bir update vaqtini o'lchaydi; `SLOW_REQUEST_THRESHOLD`
  (default 0.5 s) dan sekinlari logda `⏱ Sekin so'rov` bo'lib chiqadi va `/diag`
  da ko'rinadi.

Kechikishni o'lchash:

```bash
python scripts/latency_bench.py                 # 80 ms RTT bilan
python scripts/latency_bench.py --latency 0.3   # sekin tarmoqni simulyatsiya qilib
```

## 🩺 Diagnostika (`/diag`)

HR guruhida `/diag` (yoki `/ping`, `/tezlik`) yuborilsa bot o'z holatini
ko'rsatadi — "sekin" shikoyatida aybdor kodmi yoki tarmoqmi, shu darhol
ma'lum bo'ladi:

```
🩺 BOT DIAGNOSTIKASI

🤖 Bot: @gulf_hr_bot (id: 123456)
🕒 Ish vaqti: 3 soat 12 daqiqa

Telegram bilan aloqa
⏱ API javob vaqti: 88 ms (eng yaxshi: 84 ms) — ✅ normal
📨 Xabar yuborish: 95 ms
📡 Webhook: yo'q (long polling) ✅

So'rovlar
🔄 Qayta ishlangan update: 412
🐌 Sekin (>0.5s): 3
❗️ Xatolar: 0

Bazalar
🗄 Suhbat holati (FSM): 12 ta yozuv, 0.05 MB
📋 Arizalar bazasi: 57 ta
```

- **API javob vaqti > 800 ms** bo'lsa — aybdor server hududi/tarmoq: nomzodlar
  har bosqichda shu vaqtni kutadi (`fly.toml` dagi `primary_region` ni
  o'zgartiring — `DEPLOY_FLY.md`).
- **Webhook o'rnatilgan** bo'lsa — eski deploy (Vercel/Railway) ham shu botni
  ushlab turgan bo'lishi mumkin, u long polling bilan konflikt beradi.
- Shaxsiy chatda `/diag` faqat `ADMIN_USER_IDS` (vergul bilan: `123456, 789012`)
  dagi foydalanuvchilar uchun ishlaydi — nomzodlar texnik ma'lumot ko'rmaydi.

## 🐢 "Bot sekin ishlayapti / keyingi bosqichga o'tmayapti" — tekshirish tartibi

1. **HR guruhida `/diag`** yuboring: API RTT qancha? >800 ms bo'lsa — tarmoq/server.
2. **Loglarni ko'ring** (`fly logs`):
   - `⚠️ Telegram 409 Conflict` — shu token bilan **ikkinchi jarayon** ham
     ishlayapti (Telegram update'larni ular o'rtasida bo'lib tashlaydi):
     ikkita machine bo'lmasin (`fly scale count 1`), eski deploy to'liq
     o'chirilgan bo'lsin, lokal kompyuterda `python -m app.main` ishlamasin.
   - `⏱ Sekin so'rov: ...` — qaysi bosqich sekin ekanini aniq ko'rsatadi.
   - `⏳ user=... oldingi javob tugashini kutdi` — bitta nomzod ketma-ket yozgan.
   - `⚠️ Telegram aloqasi: 1200 ms` — ishga tushishda o'lchangan tarmoq kechikishi.
3. **Xato bo'lsa** nomzod endi jimgina qolmaydi: bot `⚠️ Kechirasiz, texnik
   xatolik...` deb javob beradi va xato `❗️ Update qayta ishlanmadi` bo'lib
   logga tushadi (oldin faqat log bo'lardi).

## Test va lint

```bash
pip install -r requirements-dev.txt
ruff check app leadbot tests scripts
pytest
```

Testlar orasida tezlikni nazorat qiladiganlari ham bor:

- `tests/test_latency_budget.py` — har bir bosqich 1 ta tarmoq kutishi (RTT)
  ichida bajarilishi va butun ariza 12 RTT dan oshmasligi;
- `tests/test_flow_speed.py` — bir arizadagi Telegram API chaqiruvlari soni;
- `tests/test_robustness.py` — navbat (bitta nomzod ketma-ket ishlanadi) va
  xato bo'lganda nomzodga javob borishi.

## Talab mezonlarini o'zgartirish

Savollar va matnlar `app/candidates/texts.py` da (ikkala til: `UZBEK` va
`RUSSIAN` — yangi matn qo'shsangiz **ikkalasiga ham** qo'shing), saralash mantig'i
`app/candidates/qualify.py` da — yosh chegarasi, shahar talabi va rus
tili sharti `.env` orqali (`CANDIDATE_MIN_AGE`, `CANDIDATE_MAX_AGE`,
`CANDIDATE_CITY`, `CANDIDATE_RUSSIAN_REQUIRED`) sozlanadi. Boshqa
vakansiya uchun savol qo'shish kerak bo'lsa, `app/candidates/states.py` ga
yangi holat, `app/bot/handlers/candidates.py` ga tegishli handler
qo'shiladi.

Nomzodga salomlashuv matni (lavozim, yo'nalish, manzil) —
`app/candidates/texts.py` dagi `WELCOME` o'zgaruvchisi; kerak bo'lsa
oylik va aniq manzilni o'sha matnga qo'shing.

## Eski mustaqil lead-bot (noyob)

`leadbot/` moduli (Facebook nomzodlar uchun alohida bot) endi tavsiya
etilmaydi — hamma narsa asosiy Gulf HR boti ichida ishlaydi. Modul kod
sifatida saqlan qolgan: `python -m leadbot.main` bilan qo'lda ishga
tushirish mumkin. Fly sozlamasi uchun `fly.leadbot.toml` (app nomi:
`gulf-leadbot`) mavjud.
