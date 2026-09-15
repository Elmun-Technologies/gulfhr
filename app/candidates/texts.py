"""Nomzodlarni saralash bo'limi matnlari (o'zbek tilida)."""

from __future__ import annotations

# NOTE: Oylik, manzil yoki boshqa shartlar aniq bo'lsa, quyidagi matnga qo'shing.
WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "<b>Gulf</b> — oziq-ovqat ingredientlari yetkazib beruvchi kompaniya. "
    "Sotuv menejeri / B2B menejer vakansiyasiga murojaat qilganingiz uchun rahmat.\n\n"
    "🧑🏻‍💼 Lavozim: Sotuv menejeri / B2B menejer\n"
    "🏢 Yo'nalish: oziq-ovqat ingredientlarini B2B yetkazib berish\n"
    "🗣 Til: rus tili (majburiy)\n"
    "📌 Manzil: Toshkent\n\n"
    "Talablarga mos kelishini bilish uchun bir nechta savol beraman. "
    "Javoblaringiz to'g'ridan-to'g'ri HR bo'limiga yuboriladi."
)

ASK_FULL_NAME = "1️⃣ Ism va familiyangizni to'liq kiriting:"
ASK_GENDER = "2️⃣ Jinsingizni tanlang:"
ASK_AGE = "3️⃣ Necha yoshdasiz? (faqat raqamda, masalan: 22)"
ASK_AGE_INVALID = "Iltimos, yoshingizni faqat raqamda kiriting (masalan: 22)."
ASK_CITY = "4️⃣ Doimiy {city}da istiqomat qilasizmi? (Yotoqxona berilmaydi)"
ASK_RUSSIAN = "5️⃣ Rus tilini bilasizmi? (bu vakansiya uchun majburiy)"
ASK_PHONE = (
    "6️⃣ Telefon raqamingizni yuboring — pastdagi tugma orqali yoki qo'lda kiriting "
    "(masalan: +998901234567):"
)
ASK_PHONE_INVALID = "Telefon raqami noto'g'ri formatda. Masalan: +998901234567"
ASK_EXPERIENCE = (
    "7️⃣ Ish tajribangiz (staj) bormi? Qisqacha yozib bering:\n"
    "(Masalan: \"2 yil sotuv menejeri\", \"1 yil B2B savdo\", \"tajribam yo'q\")"
)
ASK_RESUME = (
    "8️⃣ Rezume yoki tajribangiz haqida ovozli xabar (golos) yuborishingiz mumkin.\n"
    "Shuningdek, fayl (PDF, DOC) ko'rinishida ham yuborishingiz mumkin.\n\n"
    "Agar yubormoqchi bo'lmasangiz, pastdagi tugmani bosing 👇"
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
STATS_GROUP_ONLY = (
    "📊 Analitikani faqat HR guruhida ko'rish mumkin. Guruhda /stats deb yozing."
)
STATS_ERROR = (
    "Kechirasiz, analitika hisobotini tuzishda xato yuz berdi. "
    "Iltimos, keyinroq qayta urinib ko'ring."
)

GROUP_HEADER_QUALIFIED = "🟢 <b>YANGI NOMZOD — MOS KELADI</b>"
GROUP_HEADER_NOT_QUALIFIED = "🔴 <b>YANGI NOMZOD — MOS KELMAYDI</b>"
