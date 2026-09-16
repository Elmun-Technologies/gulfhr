"""Nomzodlarni saralash bo'limi matnlari — o'zbek (uz) va rus (ru) tillarida.

Bot birinchi qadamda tildan birini tanlashni so'raydi (`/start` → 🇺🇿/🇷🇺) va
butun suhbat tanlangan tilda davom etadi. Tanlov FSM ma'lumotida (`lang`)
saqlanadi, shuning uchun har bir handler `get_texts(lang)` orqali o'z tilini
oladi. HR guruhiga ketadigan karta doim o'zbekcha qoladi (`app.candidates.service`).

Modul oxiridagi KATTA HARFLI o'zgaruvchilar — o'zbek matnlarining qisqa
aliaslari (eski importlar va testlar uchun).
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------- #
# Tillar
# ---------------------------------------------------------------------- #

UZ = "uz"
RU = "ru"
SUPPORTED_LANGUAGES: tuple[str, ...] = (UZ, RU)
DEFAULT_LANGUAGE = UZ

# Til tanlash so'rovi tilga bog'liq emas — nomzod hali til tanlamagan,
# shuning uchun ikkala tilda birdaniga ko'rsatiladi.
CHOOSE_LANGUAGE = (
    "🌐 <b>Tilni tanlang</b> — suhbat tanlangan tilda davom etadi:\n\n"
    "🌐 <b>Выберите язык</b> — общение продолжится на выбранном языке:"
)


def normalize_language(value: str | None) -> str | None:
    """Kiritilgan til kodini `uz`/`ru` ga keltiradi, noma'lum bo'lsa `None`."""
    if not value:
        return None
    code = value.strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else None


def get_texts(lang: str | None = None) -> Lang:
    """Til kodi bo'yicha matnlar to'plamini qaytaradi (noma'lum til → o'zbekcha)."""
    code = normalize_language(lang) or DEFAULT_LANGUAGE
    return TEXTS[code]


@dataclass(frozen=True)
class Lang:
    """Bitta til uchun barcha matnlar."""

    code: str
    title: str  # HR kartasida ko'rsatiladigan til nomi

    welcome: str

    ask_full_name: str
    ask_full_name_invalid: str
    ask_gender: str
    ask_age: str
    ask_age_invalid: str
    ask_city: str  # {city} bilan formatlanadi
    ask_russian: str
    ask_phone: str
    ask_phone_invalid: str
    ask_experience: str
    ask_resume: str

    btn_yes: str
    btn_no: str
    btn_male: str
    btn_female: str
    btn_share_contact: str
    btn_skip_resume: str

    gender_labels: dict[str, str]

    result_qualified: str  # {name}
    result_not_qualified: str  # {name}, {reasons}

    cancelled: str
    # Bot noto'g'ri/kutilmagan xabar olganda savolni qayta so'rashdan oldin yozadi
    try_again_hint: str

    # Rad etish sabablari (nomzodga uning tilida ko'rsatiladi)
    reason_age: str  # {min_age}, {max_age}, {age}
    reason_city: str  # {city}
    reason_russian: str

    def localized_reasons(
        self,
        reject_codes: tuple[str, ...],
        *,
        age: int,
        min_age: int,
        max_age: int,
        city: str,
    ) -> list[str]:
        """`qualify` qaytargan kodlarni nomzod tilidagi sabablarga aylantiradi."""
        lines: list[str] = []
        for code in reject_codes:
            if code == "age":
                lines.append(
                    self.reason_age.format(min_age=min_age, max_age=max_age, age=age)
                )
            elif code == "city":
                lines.append(self.reason_city.format(city=city))
            elif code == "russian":
                lines.append(self.reason_russian)
        return lines


# ---------------------------------------------------------------------- #
# O'ZBEKCHA
# ---------------------------------------------------------------------- #

# NOTE: Oylik, manzil yoki boshqa shartlar aniq bo'lsa, quyidagi matnga qo'shing.
UZBEK = Lang(
    code=UZ,
    title="O'zbek",
    welcome=(
        "Assalomu alaykum! 👋\n\n"
        "<b>Gulf</b> — oziq-ovqat ingredientlari yetkazib beruvchi kompaniya. "
        "Sotuv menejeri / B2B menejer vakansiyasiga murojaat qilganingiz uchun rahmat.\n\n"
        "🧑🏻‍💼 Lavozim: Sotuv menejeri / B2B menejer\n"
        "🏢 Yo'nalish: oziq-ovqat ingredientlarini B2B yetkazib berish\n"
        "🗣 Til: rus tili (majburiy)\n"
        "📌 Manzil: Toshkent\n\n"
        "Talablarga mos kelishini bilish uchun bir nechta savol beraman. "
        "Javoblaringiz to'g'ridan-to'g'ri HR bo'limiga yuboriladi."
    ),
    ask_full_name="1️⃣ Ism va familiyangizni to'liq kiriting:",
    ask_full_name_invalid=(
        "Ism va familiya 3 dan 80 belgigacha bo'lishi kerak. Iltimos, qaytadan kiriting:"
    ),
    ask_gender="2️⃣ Jinsingizni tanlang:",
    ask_age="3️⃣ Necha yoshdasiz? (faqat raqamda, masalan: 22)",
    ask_age_invalid="Iltimos, yoshingizni faqat raqamda kiriting (masalan: 22).",
    ask_city="4️⃣ Doimiy {city}da istiqomat qilasizmi? (Yotoqxona berilmaydi)",
    ask_russian="5️⃣ Rus tilini bilasizmi? (bu vakansiya uchun majburiy)",
    ask_phone=(
        "6️⃣ Telefon raqamingizni yuboring — pastdagi tugma orqali yoki qo'lda kiriting "
        "(masalan: +998901234567):"
    ),
    ask_phone_invalid="Telefon raqami noto'g'ri formatda. Masalan: +998901234567",
    ask_experience=(
        "7️⃣ Ish tajribangiz (staj) bormi? Qisqacha yozib bering:\n"
        '(Masalan: "2 yil sotuv menejeri", "1 yil B2B savdo", "tajribam yo\'q")'
    ),
    ask_resume=(
        "8️⃣ Rezume yoki tajribangiz haqida ovozli xabar (golos) yuborishingiz mumkin.\n"
        "Shuningdek, fayl (PDF, DOC) ko'rinishida ham yuborishingiz mumkin.\n\n"
        "Agar yubormoqchi bo'lmasangiz, pastdagi tugmani bosing 👇"
    ),
    btn_yes="✅ Ha",
    btn_no="❌ Yo'q",
    btn_male="👨 Erkak",
    btn_female="👩 Ayol",
    btn_share_contact="📱 Raqamni yuborish",
    btn_skip_resume="⏭ O'tkazib yuborish",
    gender_labels={"male": "Erkak", "female": "Ayol"},
    result_qualified=(
        "✅ Rahmat, {name}!\n\n"
        "Siz vakansiya talablariga javob berasiz. Tez orada HR mutaxassisi siz bilan "
        "bog'lanadi.\n\n"
        "Kuting va telefoningizni yoningizda tuting 📞"
    ),
    result_not_qualified=(
        "Rahmat, {name}, ariza uchun!\n\n"
        "Afsuski, hozircha quyidagi sabab(lar)ga ko'ra ushbu vakansiya talablariga "
        "to'liq mos kelmaysiz:\n{reasons}\n\n"
        "Boshqa mos vakansiyalar bo'lsa, albatta siz bilan bog'lanamiz. E'tiboringiz uchun rahmat!"
    ),
    cancelled="Ariza bekor qilindi. Qaytadan boshlash uchun /start ni bosing.",
    try_again_hint="👇 Iltimos, quyidagi savolga javob bering:",
    reason_age="Yosh chegarasi: {min_age}-{max_age} (siz: {age})",
    reason_city="Doimiy {city}da istiqomat qilish talab etiladi (yotoqxona yo'q)",
    reason_russian="Rus tilini bilish majburiy talab",
)


# ---------------------------------------------------------------------- #
# RUSCHA
# ---------------------------------------------------------------------- #

RUSSIAN = Lang(
    code=RU,
    title="Русский",
    welcome=(
        "Здравствуйте! 👋\n\n"
        "<b>Gulf</b> — компания-поставщик пищевых ингредиентов. Спасибо, что "
        "откликнулись на вакансию менеджера по продажам / B2B менеджера.\n\n"
        "🧑🏻‍💼 Должность: Менеджер по продажам / B2B менеджер\n"
        "🏢 Направление: B2B поставки пищевых ингредиентов\n"
        "🗣 Язык: русский (обязательно)\n"
        "📌 Адрес: Ташкент\n\n"
        "Я задам несколько вопросов, чтобы понять, подходите ли вы. Ваши ответы "
        "будут направлены напрямую в HR-отдел."
    ),
    ask_full_name="1️⃣ Введите ваши имя и фамилию полностью:",
    ask_full_name_invalid=(
        "Имя и фамилия должны содержать от 3 до 80 символов. Пожалуйста, введите ещё раз:"
    ),
    ask_gender="2️⃣ Выберите ваш пол:",
    ask_age="3️⃣ Сколько вам лет? (только число, например: 22)",
    ask_age_invalid="Пожалуйста, введите возраст только числом (например: 22).",
    ask_city="4️⃣ Вы постоянно проживаете в городе {city}? (Общежитие не предоставляется)",
    ask_russian="5️⃣ Вы владеете русским языком? (это обязательное требование вакансии)",
    ask_phone=(
        "6️⃣ Отправьте ваш номер телефона — кнопкой ниже или введите вручную "
        "(например: +998901234567):"
    ),
    ask_phone_invalid="Неверный формат номера телефона. Пример: +998901234567",
    ask_experience=(
        "7️⃣ Есть ли у вас опыт работы (стаж)? Напишите кратко:\n"
        '(Например: «2 года менеджером по продажам», «1 год B2B продажи», «опыта нет»)'
    ),
    ask_resume=(
        "8️⃣ Вы можете отправить резюме или голосовое сообщение о вашем опыте.\n"
        "Также можно отправить файл (PDF, DOC).\n\n"
        "Если отправлять не хотите — нажмите кнопку ниже 👇"
    ),
    btn_yes="✅ Да",
    btn_no="❌ Нет",
    btn_male="👨 Мужской",
    btn_female="👩 Женский",
    btn_share_contact="📱 Отправить номер",
    btn_skip_resume="⏭ Пропустить",
    gender_labels={"male": "Мужской", "female": "Женский"},
    result_qualified=(
        "✅ Спасибо, {name}!\n\n"
        "Вы соответствуете требованиям вакансии. В ближайшее время с вами свяжется "
        "HR-специалист.\n\n"
        "Ожидайте и держите телефон под рукой 📞"
    ),
    result_not_qualified=(
        "{name}, спасибо за заявку!\n\n"
        "К сожалению, пока вы не полностью соответствуете требованиям вакансии "
        "по следующим причинам:\n{reasons}\n\n"
        "Если появятся другие подходящие вакансии, мы обязательно с вами свяжемся. "
        "Спасибо за отклик!"
    ),
    cancelled="Заявка отменена. Чтобы начать заново, нажмите /start.",
    try_again_hint="👇 Пожалуйста, ответьте на вопрос ниже:",
    reason_age="Возрастное ограничение: {min_age}-{max_age} (ваш возраст: {age})",
    reason_city="Требуется постоянное проживание в г. {city} (общежития нет)",
    reason_russian="Знание русского языка — обязательное требование",
)


TEXTS: dict[str, Lang] = {UZ: UZBEK, RU: RUSSIAN}

# HR guruhiga ketadigan kartada til shu o'zbekcha yorliqlar bilan ko'rsatiladi
LANGUAGE_LABELS: dict[str, str] = {UZ: "O'zbek", RU: "Rus"}


# ---------------------------------------------------------------------- #
# Eski importlar uchun aliaslar (standart til — o'zbekcha)
# ---------------------------------------------------------------------- #

WELCOME = UZBEK.welcome
ASK_FULL_NAME = UZBEK.ask_full_name
ASK_FULL_NAME_INVALID = UZBEK.ask_full_name_invalid
ASK_GENDER = UZBEK.ask_gender
ASK_AGE = UZBEK.ask_age
ASK_AGE_INVALID = UZBEK.ask_age_invalid
ASK_CITY = UZBEK.ask_city
ASK_RUSSIAN = UZBEK.ask_russian
ASK_PHONE = UZBEK.ask_phone
ASK_PHONE_INVALID = UZBEK.ask_phone_invalid
ASK_EXPERIENCE = UZBEK.ask_experience
ASK_RESUME = UZBEK.ask_resume

BTN_YES = UZBEK.btn_yes
BTN_NO = UZBEK.btn_no
BTN_MALE = UZBEK.btn_male
BTN_FEMALE = UZBEK.btn_female
BTN_SHARE_CONTACT = UZBEK.btn_share_contact
BTN_SKIP_RESUME = UZBEK.btn_skip_resume

GENDER_LABELS = UZBEK.gender_labels

RESULT_QUALIFIED = UZBEK.result_qualified
RESULT_NOT_QUALIFIED = UZBEK.result_not_qualified

CANCELLED = UZBEK.cancelled

# HR guruhiga oid matnlar — guruh tili o'zbekcha bo'lgani uchun tilga bog'liq emas.
STATS_GROUP_ONLY = (
    "📊 Bu buyruq faqat sozlangan HR guruhida ishlaydi. "
    "Guruhda /stats (yoki /stat), /diag yoki /export deb yozing."
)
STATS_ERROR = (
    "Kechirasiz, analitika hisobotini tuzishda xato yuz berdi. "
    "Iltimos, keyinroq qayta urinib ko'ring."
)

GROUP_HEADER_QUALIFIED = "🟢 <b>YANGI NOMZOD — MOS KELADI</b>"
GROUP_HEADER_NOT_QUALIFIED = "🔴 <b>YANGI NOMZOD — MOS KELMAYDI</b>"
