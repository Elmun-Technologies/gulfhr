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

Nomzod sezadigan kechikish asosan Telegram API chaqiruvlari soniga bog'liq:

- Salomlashuv va birinchi savol **bitta xabarda** yuboriladi (oldingi versiyada
  `/start` 2 ta xabar yuborar edi → 1 ta API chaqiruvi tejaldi).
- Tugma bosilganda "soat" belgisi (`callback.answer`) **eng avval** chaqiriladi —
  oldin u 2 ta so'rovdan keyin yuborilar edi va tugma ~1 s "yuklanmoqda" turardi.
- Baza yozuvi va HR guruhiga xabar **parallel** (`asyncio.gather`) bajariladi.
- SQLite `WAL` + `synchronous=NORMAL` + `busy_timeout` rejimida — yozuvlar
  tezroq va parallel suhbatlarda `database is locked` bo'lmaydi.
- `/stats` endi butun jadvalni Python'ga yuklamaydi: jamlanmalar SQL'da
  hisoblanadi (oldin 1000 satr o'qilar edi).
- `TimingsMiddleware` (`app/bot/middlewares.py`) har bir so'rov vaqtini o'lchaydi;
  0.5 s dan sekinlari logda `⏱ Sekin so'rov` sifatida ko'rinadi.

## Test va lint

```bash
pip install -r requirements-dev.txt
ruff check app leadbot tests
pytest
```

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
