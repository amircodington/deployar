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

APPROVAL_MISSING = "این کار تأیید معتبر ندارد و اجرا نشد. / No valid approval for this call; it did not run."
TOOL_CRASHED = (
    "ابزار با خطای داخلی متوقف شد؛ وضعیت را دوباره بررسی کن. / The tool crashed; re-check the state before retrying."
)

UNKNOWN_MODE = "این حالت کاری وجود ندارد."
NOT_FOUND = "پیدا نشد."
UNAUTHORIZED = "اول وارد شوید."
BAD_PASSPHRASE = "رمز ورود درست نیست."
LLM_FAILED = "دستیار نتوانست پاسخ را کامل کند. دوباره امتحان کنید."
RUN_CRASHED = "اجرای کار با خطای داخلی متوقف شد."
RUN_CANCELLED = "کار به درخواست شما متوقف شد."
EMPTY_MESSAGE = "پیام خالی است."

LIARA_UNAUTHORIZED = "توکن لیارا معتبر نیست یا منقضی شده. از تنظیمات، توکن تازه بگذار."
LIARA_UNREACHABLE = "به API لیارا وصل نشدم. کمی بعد دوباره امتحان کن."
LIARA_ERROR = "لیارا درخواست را قبول نکرد."
NO_LIARA_CONNECTION = "هنوز توکن لیارا وصل نشده. از صفحه‌ی اتصال‌ها توکن را اضافه کن."
APP_NOT_CREATED = "این پروژه هنوز روی لیارا ساخته نشده."
APP_NOT_FOUND = "این اپ روی لیارا پیدا نشد."
METRICS_UNAVAILABLE = "API لیارا برای این اپ متریک برنگرداند."
PLANS_FROM_TABLE = "قیمت‌ها از جدول ثابت کنسول لیارا (۳۰ مهر ۱۴۰۵) است، نه از API."

BAD_REPO = "آدرس مخزن را نشناختم؛ به شکل owner/name یا لینک GitHub بفرست."
NO_REPO = "لینک مخزن GitHub را بفرست تا بخوانمش."
GITHUB_NO_ACCESS = "به این مخزن دسترسی ندارم؛ اگر خصوصی است، توکن GitHub را در صفحه‌ی اتصال‌ها اضافه کن."
GITHUB_UNAUTHORIZED = "توکن GitHub معتبر نیست یا منقضی شده."
GITHUB_UNREACHABLE = "به GitHub وصل نشدم. کمی بعد دوباره امتحان کن."
GITHUB_RATE_LIMITED = "سقف درخواست GitHub پر شده؛ با توکن GitHub این محدودیت بیشتر می‌شود."
GITHUB_ERROR = "GitHub درخواست را قبول نکرد."
NO_GITHUB_CONNECTION = "توکن GitHub هنوز اضافه نشده."

WARN_DEV_SERVER = "Dockerfile سرور توسعه را اجرا می‌کند؛ برای لیارا باید gunicorn یا next start باشد."
WARN_DEBUG_ON = "پیش‌فرض DEBUG روشن است؛ روی لیارا DEBUG=0 می‌گذارم."
WARN_NO_LOCKFILE = "فایل lock پیدا نشد؛ نسخه‌ی وابستگی‌ها ثابت نیست."
WARN_NO_APP = "هیچ برنامه‌ی قابل استقراری در مخزن پیدا نشد."
WARN_MONOREPO = "{n} برنامه پیدا شد؛ هر کدام یک اپ جدا روی لیارا می‌شود."
ANALYZE_REPO_DESC = "مخزن GitHub را می‌خواند: پلتفرم، نسخه، دیتابیس، متغیرها و RAM، هر کدام با فایل مدرک."
