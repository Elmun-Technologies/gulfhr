# Gulf HR — amoCRM jarayon nazorati boti

Sotuv menejerlari uchun Telegram bot: amoCRM'dagi har bir sotuv jarayonini
avtomatik nazorat qiladi, qoidabuzarliklarni (SLA, muddati o'tgan vazifa,
qotib qolgan lid va h.k.) aniqlaydi va tegishli xodimga, kechiksa —
rahbariyatga xabar beradi. Shuningdek sotuvchilarga target (reja) belgilash
va bajarilishini kuzatish imkonini beradi.

Ichida **nomzodlarni saralash** (ariza filtri) bo'limi ham bor: Facebook
(Meta) reklamasi orqali kelgan nomzodlar uchun oziq-ovqat ingredientlari
yetkazib beruvchi kompaniya **Sotuv menejeri / B2B menejer** vakansiyasi
bo'yicha ariza oqimi (quyida batafsil).

## Qanday ishlaydi

```
amoCRM  <──(API v4 / OAuth2)──  Sinxronizatsiya (har N daqiqada + webhook)
                                        │
                                        ▼
                                  Lokal baza (SQLite/PostgreSQL)
                                        │
                                        ▼
                              Qoidalar dvigateli (app/services/rules.py)
                                        │
                         ┌──────────────┴───────────────┐
                         ▼                               ▼
                 Sotuvchiga Telegram xabar      2 soatdan kech javobsiz →
                 (o'z vaqtida)                  rahbariyatga eskalatsiya
```

### Nazorat qilinadigan qoidalar

| Qoida | Tavsif | Sozlash (`.env`) |
|---|---|---|
| Birinchi javob SLA | Yangi lidga belgilangan vaqt ichida hech qanday harakat bo'lmasa | `RULE_FIRST_RESPONSE_MINUTES` |
| Vazifasiz lid | Ochiq lidda keyingi qadam bo'yicha vazifa yo'q | `RULE_LEAD_WITHOUT_TASK_HOURS` |
| Muddati o'tgan vazifa | amoCRM vazifasi muddati o'tib, hali yopilmagan | — |
| Bosqichda qotib qolish | Lid bir bosqichda uzoq turib qolgan | `RULE_STATUS_STUCK_DAYS` (yoki bosqichga xos `max_days`) |
| Harakatsiz lid | Lidda umuman hech qanday yangilanish yo'q | `RULE_NO_ACTIVITY_DAYS` |
| Ortiqcha yuklama | Sotuvchida ochiq lidlar soni limitdan oshgan | `RULE_MAX_OPEN_LEADS` |
| Target sur'atidan orqada qolish | Reja bajarilishi kunlar sur'atiga nisbatan orqada | `RULE_TARGET_LAG_PERCENT` |

Yangi qoida qo'shish uchun `app/services/rules.py` faylidagi pattern
ergashib funksiya yozib, `ALL_RULES` ro'yxatiga qo'shish kifoya.

## Bot funksiyalari

**Sotuvchi uchun:**
- 📊 Shaxsiy natija (bugungi savdo, ochiq lidlar, targetlar progress-bar bilan)
- ⚠️ Shaxsiy ochiq ogohlantirishlar ro'yxati
- 🔔 Bildirishnomalarni yoqish/o'chirish
- ☀️/🌙 Kunlik tong va kechki avtomatik hisobot

**Rahbar / HR uchun:**
- 👥 Jamoa holati (barcha sotuvchilar bo'yicha umumiy ko'rinish)
- ➕ Yangi xodim uchun taklif (invite) yaratish
- 🎯 Target belgilash (savdo summasi / yopilgan bitimlar / yangi lidlar / konversiya — kunlik/haftalik/oylik)
- 🗓 Haftalik avtomatik hisobot

**Administrator uchun:**
- amoCRM ulanishini tekshirish (`/amosetup`)
- Qo'lda sinxronizatsiya (`/sync`)
- Xodimlarni amoCRM foydalanuvchilariga bog'lash (`/linkamo`)

## O'rnatish

1. **amoCRM tomonida integratsiya yarating** (Gulf hisobi): amoCRM
   sozlamalari → Integratsiyalar → Yaratish. `Client ID`, `Client secret`
   va `Redirect URI` oling. Birinchi avtorizatsiyadan `authorization code`
   oling (yoki uzoq muddatli token yarating). `.env` dagi `AMO_SUBDOMAIN`
   Gulf'ingizning amoCRM domeniga mos bo'lsin (masalan `gulf`).

2. **`.env` faylini tayyorlang**:
   ```bash
   cp .env.example .env
   # BOT_TOKEN, ADMIN_TELEGRAM_IDS, AMO_* qiymatlarini to'ldiring
   ```

3. **Docker bilan ishga tushirish** (tavsiya etiladi):
   ```bash
   docker compose up -d --build
   ```

   **Yoki lokal Python bilan:**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.main
   ```

   **Yoki Fly.io'da:**
   ```bash
   fly launch -c fly.toml   # app nomi: gulf-hr
   fly secrets set          # BOT_TOKEN va qolgan .env qiymatlari
   fly deploy
   ```

4. **Birinchi admin**: `ADMIN_TELEGRAM_IDS` ichidagi Telegram ID egasi botga
   `/start` yuborishi bilan avtomatik administrator bo'ladi. Keyin
   `/amosetup` bilan amoCRM ulanishini tekshiring, `/addemployee` bilan
   sotuvchilarni qo'shing va ularga chiqqan `/start <kod>` ni yuboring,
   so'ng `/linkamo` orqali har birini amoCRM akkountiga bog'lang.

5. **amoCRM webhook (ixtiyoriy, real vaqtga yaqinroq nazorat uchun)**:
   amoCRM sozlamalari → Webhooklar → qo'shish:
   `https://SIZNING_DOMEN/amocrm/webhook?secret=WEBHOOK_SECRET`
   (`.env` dagi `WEBHOOK_SECRET` bilan bir xil bo'lsin). Webhook bo'lmasa
   ham bot `SYNC_INTERVAL_MINUTES` bo'yicha muntazam o'zi sinxronlanadi —
   webhook faqat kutish vaqtini qisqartiradi.

## Loyiha tuzilishi

```
app/
  amocrm/       amoCRM OAuth, API mijozi, sinxronizatsiya
  bot/          Telegram bot: handlerlar, klaviaturalar, FSM
  candidates/   Nomzodlarni vakansiya talablari bo'yicha saralash (quyida)
  services/     Biznes mantiq: qoidalar, targetlar, hisobotlar
  scheduler/    Davriy vazifalar (APScheduler)
  web/          amoCRM webhook qabul qiluvchi (FastAPI)
  db/           SQLAlchemy modellari va sessiya
leadbot/        Eski mustaqil lead-bot (noyob; compat: LEADBOT_TOKEN)
tests/          pytest testlari
```

## Test va lint

```bash
pip install -r requirements-dev.txt
ruff check app leadbot tests
pytest
```

---

## Nomzodlarni saralash (vakansiya filteri)

Gulf HR botining o'z ichidagi bo'lim: Facebook (Meta) reklamasi orqali
kelgan nomzod Telegram botga `/start` yuboradi, bot bir nechta savol beradi,
javoblarni vakansiya talablari bilan solishtiradi va natijani (mos yoki
mos emasligi, sabablari bilan) nomzodga aytadi, to'liq kartani esa HR
guruhiga yuboradi. amoCRM yoki xodim rollari shu oqim uchun kerak emas.

**Vakansiya**: oziq-ovqat ingredientlari yetkazib beruvchi kompaniya uchun
**Sotuv menejeri / B2B menejer**.

```
Facebook reklama → "Botga yozish" tugmasi → Telegram bot (t.me/BOTUSERNAME)
                                                    │
                     Savollar: ism, jins, yosh, shahar, telefon, staj, rezume
                                                    │
                                          Talablar bilan solishtirish
                                                    │
                              ┌─────────────────────┴─────────────────────┐
                              ▼                                           ▼
                    Nomzodga javob (mos/mos emas)              HR guruhiga to'liq karta
                                                                (🟢 mos / 🔴 mos emas + sabab)
```

### Filter (suhbat oqimi)

```
1️⃣ Ism → 2️⃣ Jins (👨 Erkak / 👩 Ayol tugmalari) → 3️⃣ Yosh →
4️⃣ Shahar (Ha/Yo'q) → 5️⃣ Telefon → 6️⃣ Staj (matn yozadi) →
7️⃣ Rezume (fayl PDF/DOC yoki golos — ovozli xabar) → ✅ Natija
```

Ish grafigi bo'yicha savol berilmaydi. Yosh chegarasi **18-30**
(`CANDIDATE_MIN_AGE` / `CANDIDATE_MAX_AGE`), shahar talabi
`CANDIDATE_CITY` (default: Toshkent) — ikkalasi ham `.env` orqali
o'zgartiriladi.

### Ishga tushirish

1. Bot tokeni: asosiy `BOT_TOKEN` (eski `LEADBOT_TOKEN` sozlangan bo'lsa,
   `BOT_TOKEN` to'ldirilmaganda avtomatik u ishlatiladi — eski Fly
   sozlamalari o'zgarmasdan ishlaydi).
2. Nomzod kartalari yuboriladigan HR guruh: botni guruhga admin qilib
   qo'shing va guruh ID sini oling (masalan `-1001234567890`), keyin
   `.env` fayliga:
   ```
   BOT_TOKEN=...
   CANDIDATES_CHAT_ID=-100...
   CANDIDATE_MIN_AGE=18
   CANDIDATE_MAX_AGE=30
   CANDIDATE_CITY=Toshkent
   ```
   `CANDIDATES_CHAT_ID` bo'sh qoldirilsa `MANAGEMENT_CHAT_ID`, undan keyin
   `LEAD_GROUP_CHAT_ID` (eski sozlama) ishlatiladi.
3. Ishga tushiring:
   ```bash
   python -m app.main
   ```
   Docker/Fly: `Dockerfile` asosan `python -m app.main` ni ishga tushiradi.
4. Facebook reklama sozlamalarida (Meta Ads Manager) "Click to Telegram"
   tugmasi/veb-sayt havolasi sifatida `https://t.me/BOTUSERNAME` ni
   ko'rsating — reklamani ko'rgan odam to'g'ridan-to'g'ri botga tushadi va
   `/start` bilan ariza boshlanadi.

Nomzodga salomlashuv matni (lavozim, yo'nalish, manzil) —
`app/candidates/texts.py` dagi `WELCOME` o'zgaruvchisi; kerak bo'lsa
oylik va aniq manzilni o'sha matnga qo'shing.

Xodimlar uchun taklif kodi oqimi o'zgarishsiz qoladi: `/start <kod>`
yuborgan xodim nomzod arizasiga emas, o'z menyusiga tushadi.

### 📊 Analitika

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

🕘 Oxirgi 10 nomzod:
🟢 Aliyev Vali (Erkak) — 22 yosh
🔴 ...
```

`/stats` faqat HR guruhida ishlaydi. Analitika vaqt mintaqasi `TZ`
(default: `Asia/Tashkent`) orqali sozlanadi. Docker/Fly.io'da ma'lumot
yo'qolmasligi uchun `/app/data` katalogini doimiy volume'ga ulash tavsiya
etiladi.

### Talab mezonlarini o'zgartirish

Savollar va matnlar `app/candidates/texts.py` da, saralash mantig'i
`app/candidates/qualify.py` da — yosh chegarasi va shahar talabi `.env`
orqali (`CANDIDATE_MIN_AGE`, `CANDIDATE_MAX_AGE`, `CANDIDATE_CITY`)
sozlanadi. Boshqa vakansiya uchun savol qo'shish kerak bo'lsa,
`app/candidates/states.py` ga yangi holat, `app/bot/handlers/candidates.py`
ga tegishli handler qo'shiladi.

### Eski mustaqil lead-bot (noyob)

`leadbot/` moduli (Facebook nomzodlar uchun alohida bot) endi tavsiya
etilmaydi — hamma narsa asosiy Gulf HR boti ichida ishlaydi. Modul kod
sifatida saqlan qolgan: `python -m leadbot.main` bilan qo'lda ishga
tushirish mumkin. Fly sozlamalari uchun `fly.leadbot.toml` (app nomi:
`gulf-leadbot`) mavjud. Eski `LEADBOT_TOKEN` / `LEAD_GROUP_CHAT_ID`
o'zgaruvchilari iloji sifatida avtomatik tan olinadi, shuning uchun
deploy'dan oldin `.env` ni o'zgartirish shart emas.
