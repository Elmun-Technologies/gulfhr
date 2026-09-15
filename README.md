# Gulf HR — nomzodlarni saralash boti

Oziq-ovqat ingredientlari yetkazib beruvchi **Gulf** kompaniyasi uchun
Telegram bot: **Sotuv menejeri / B2B menejer** vakansiyasi bo'yicha arizalarni
yig'adi, nomzodni bir nechta savol orqali vakansiya talablari bilan
solishtiradi, natijani nomzodga aytadi va to'liq kartani HR guruhiga yuboradi.

## Qanday ishlaydi

```
Facebook reklama → "Botga yozish" tugmasi → Telegram bot (t.me/BOTUSERNAME)
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
1️⃣ Ism → 2️⃣ Jins (👨 Erkak / 👩 Ayol tugmalari) → 3️⃣ Yosh →
4️⃣ Shahar (Ha/Yo'q) → 5️⃣ Rus tili (Ha/Yo'q — majburiy) → 6️⃣ Telefon →
7️⃣ Staj (matn yozadi) → 8️⃣ Rezume (fayl PDF/DOC yoki golos — ovozli xabar) → ✅ Natija
```

Ish grafigi bo'yicha savol berilmaydi.

## Saralash mezonlari

| Mezon | Tavsif | Sozlash (`.env`) |
|---|---|---|
| Yosh | Default **18-30** | `CANDIDATE_MIN_AGE`, `CANDIDATE_MAX_AGE` |
| Shahar | Nomzod doimiy Toshkentda istiqomat qilishi shart (yotoqxona berilmaydi) | `CANDIDATE_CITY` |
| Rus tili | **Majburiy** — "Yo'q" javobi rad etilishga olib keladi | `CANDIDATE_RUSSIAN_REQUIRED` (default `true`) |

Jins va staj saralash mezoniga kirmaydi — ular shunchaki ma'lumot sifatida
HR guruhiga yuboriladi.

## Bot buyruqlari

- `/start` — ariza boshlash
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
  bot/          Telegram bot: /start, /help, fallback, dispatcher
  candidates/   Ariza oqimi: savollar, klaviaturalar, FSM, saralash, baza, HR kartasi
  db/           SQLAlchemy modeli (Application) va sessiya
leadbot/        Eski mustaqil lead-bot (noyob; python -m leadbot.main)
tests/          pytest testlari
```

## Test va lint

```bash
pip install -r requirements-dev.txt
ruff check app leadbot tests
pytest
```

## Talab mezonlarini o'zgartirish

Savollar va matnlar `app/candidates/texts.py` da, saralash mantig'i
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
