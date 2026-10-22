"""Persian UI and model-facing strings (ARCHITECTURE.md §11: not inline)."""

APPROVAL_BAD_SIGNATURE = "این تأیید معتبر نیست. کارت را دوباره باز کنید."
APPROVAL_NOT_PENDING = "این درخواست قبلاً تصمیم گرفته شده یا منقضی شده است."
NO_USER = "هنوز کاربری ساخته نشده است. «make seed» را اجرا کنید."

# Deny messages go back to the model, which relays them; Persian for the user, English for the model.
TOOL_NOT_ALLOWED = "این ابزار برای دستیار مجاز نیست. / This tool is not allowed for the assistant."
DENIED = {
    "rejected": "کاربر این کار را رد کرد. / The user rejected this action.",
    "expired": (
        "مهلت ۱۰ دقیقه‌ای تأیید تمام شد؛ اگر لازم است دوباره پیشنهاد بده. / Approval expired; offer it again if needed."
    ),
    "cancelled": "تأیید در زمان مقرر نرسید و درخواست لغو شد. / No decision arrived in time; the request was cancelled.",
    "invalidated": "ورودی‌ها بعد از تأیید عوض شد؛ باید دوباره تأیید شود. / Arguments changed after approval; ask again.",
}

# human_only tools never run: the model receives the guide and shows it to the user.
GUIDES = {
    "registrar_dns_records": (
        "این کار را فقط خودتان می‌توانید در پنل ثبت‌کننده‌ی دامنه انجام دهید:\n"
        "۱. وارد پنل ثبت‌کننده‌ی دامنه (مثلاً ایرنیک) شوید.\n"
        "۲. رکوردهایی را که لیارا نشان داده دقیقاً همان‌طور اضافه کنید.\n"
        "۳. برگردید و «الان بررسی کن» را بزنید؛ ممکن است تا چند ساعت طول بکشد.\n"
        "/ Human-only: add the DNS records at the registrar, then press «check now»."
    ),
    "top_up_balance": (
        "افزایش اعتبار فقط از پنل لیارا و توسط خودتان ممکن است:\n"
        "۱. وارد console.liara.ir شوید.\n"
        "۲. از بالای صفحه «افزایش اعتبار» را بزنید و پرداخت کنید.\n"
        "۳. برگردید و «الان بررسی کن» را بزنید تا موجودی دوباره خوانده شود.\n"
        "/ Human-only: top up the balance in the Liara console, then press «check now»."
    ),
}
