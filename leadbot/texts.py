"""Bot matnlari (o'zbek tilida)."""

from __future__ import annotations

WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "<b>Gulf</b> — oziq-ovqat ingredientlari yetkazib beruvchi kompaniya. "
    "Sotuv menejeri / B2B menejer vakansiyasiga murojaat qilganingiz uchun rahmat.\n\n"
    "🧑🏻‍💼 Lavozim: Sotuv menejeri / B2B menejer\n"
    "💵 Oylik: 10 000 000 – 15 000 000 so'm\n"
    "⏰ Ish grafigi: 08:00–19:00, oyiga 1 kun dam\n"
    "📌 Manzil: Toshkent, O'rikzor bozori atrofida\n"
    "❗️ <b>Yotoqxona berilmaydi</b> — doimiy Toshkentda yashovchilar uchun\n\n"
    "Talablarga mos kelasizmi — buni bilish uchun bir nechta savol beraman. "
    "Javoblaringiz to'g'ridan-to'g'ri HR bo'limiga yuboriladi."
)

ASK_FULL_NAME = "1️⃣ Ism va familiyangizni to'liq kiriting:"
ASK_FULL_NAME_INVALID = (
    "Ism va familiya 3 dan 80 belgigacha bo'lishi kerak. Iltimos, qaytadan kiriting:"
)
ASK_GENDER = "2️⃣ Jinsingizni tanlang:"
ASK_AGE = "3️⃣ Necha yoshdasiz? (faqat raqamda, masalan: 22)"
ASK_AGE_INVALID = "Iltimos, yoshingizni faqat raqamda kiriting (masalan: 22)."
ASK_CITY = "4️⃣ Doimiy Toshkent shahrida istiqomat qilasizmi? (<b>Yotoqxona berilmaydi</b>)"
ASK_PHONE = (
    "5️⃣ Telefon raqamingizni yuboring — pastdagi tugma orqali yoki qo'lda kiriting "
    "(masalan: +998901234567):"
)
ASK_PHONE_INVALID = "Telefon raqami noto'g'ri formatda. Masalan: +998901234567"
PHONE_RECEIVED = "✅ Telefon qabul qilindi."
ASK_EXPERIENCE = (
    "6️⃣ Oxirgi qadam — ish tajribangiz haqida <b>ovozli xabar</b> yuboring: "
    "necha yil, qayerda va kim bo'lib ishlaganingizni gapirib bering. "
    "HR ovozingizni tinglab xulosa chiqaradi.\n\n"
    "Rezyumeingiz (PDF yoki Word fayl) bo'lsa, o'rniga shuni yuborishingiz mumkin.\n"
    "Ovozli xabar yoki fayl imkoni bo'lmasa, shu yerga qisqacha yozib bering."
)
ASK_EXPERIENCE_INVALID = (
    "Iltimos, ovozli xabar, rezyume fayli yuboring yoki tajribangiz haqida qisqacha yozing (1-500 belgi)."
)

BTN_YES = "✅ Ha"
BTN_NO = "❌ Yo'q"
BTN_MALE = "👨 Erkak"
BTN_FEMALE = "👩 Ayol"
BTN_SHARE_CONTACT = "📱 Raqamni yuborish"
BTN_SKIP_RESUME = "⏭ O'tkazib yuborish"

GENDER_LABELS = {"male": "Erkak", "female": "Ayol"}

RESULT_QUALIFIED = (
    "✅ Rahmat, {name}!\n\n"
    "Siz vakansiya talablariga javob berasiz. Tez orada HR mutaxassisi siz bilan "
    "bog'lanadi.\n\n"
    "Kuting va telefoningizni yoningizda tuting 📞"
)

RESULT_NOT_QUALIFIED = (
    "Rahmat, {name}, ariza uchun!\n\n"
    "Afsuski, hozircha quyidagi sabab(lar)ga ko'ra ushbu vakansiya talablariga "
    "to'liq mos kelmaysiz:\n{reasons}\n\n"
    "Boshqa mos vakansiyalar bo'lsa, albatta siz bilan bog'lanamiz. E'tiboringiz uchun rahmat!"
)

CANCELLED = "Ariza bekor qilindi. Qaytadan boshlash uchun /start ni bosing."
ALREADY_SUBMITTED = (
    "Siz allaqachon ariza topshirgansiz. Qayta topshirish uchun /start ni bosing."
)
NOT_CONFIGURED = (
    "Bot hozircha sozlanmagan (LEADBOT_TOKEN / LEAD_GROUP_CHAT_ID). Administratorga murojaat qiling."
)

GROUP_HEADER_QUALIFIED = "🟢 <b>YANGI NOMZOD — MOS KELADI</b>"
GROUP_HEADER_NOT_QUALIFIED = "🔴 <b>YANGI NOMZOD — MOS KELMAYDI</b>"

STATS_GROUP_ONLY = (
    "📊 Analitikani faqat guruh chatida ko'rish mumkin. "
    "Guruhga /stats deb yozing."
)
STATS_ERROR = "Kechirasiz, analitika hisobotini tuzishda xato yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."

SEARCH_GROUP_ONLY = (
    "🔍 Qidiruvni faqat guruh chatida ishlatish mumkin. "
    "Guruhga /qidir <so'z> deb yozing."
)
SEARCH_USAGE = (
    "Foydalanish: <code>/qidir so'z</code>\n"
    "Masalan: <code>/qidir qurilish</code> yoki <code>/qidir sotuv</code>\n\n"
    "Eslatma: faqat qo'lda (matn) yozilgan staj javoblari orasida qidiriladi — "
    "ovozli xabarlar bu yerga kirmaydi."
)
SEARCH_ERROR = "Kechirasiz, qidiruvda xato yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."
