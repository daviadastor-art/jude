"""عملة البوت الموحدة.

منذ اعتماد iChancy لليرة السورية الجديدة، كل المبالغ داخل البوت
وخارجه تستخدم نفس الوحدة: 1 ليرة جديدة = 1 ليرة جديدة.
الدوال ذات الأسماء القديمة موجودة فقط للتوافق مع السجلات والكود القديم،
لكنها لا تجري أي تحويل أو قسمة.
"""
from decimal import Decimal

BOT_CURRENCY = "SYP_NEW"
ICHANCY_CURRENCY = "SYP_NEW"
ICHANCY_RATE = Decimal("1")


def old_to_new(amount, *, rounding=None) -> Decimal:
    """توافق خلفي: لم يعد هناك تحويل، القيمة تعاد كما هي."""
    return Decimal(str(amount))


def new_to_old(amount) -> int:
    """توافق خلفي: iChancy يستخدم الليرة الجديدة 1=1."""
    value = Decimal(str(amount))
    if value < 0:
        raise ValueError("amount cannot be negative")
    if value != value.to_integral_value():
        raise ValueError("amount must be a whole SYP amount")
    return int(value)


def require_new_integer(amount) -> int:
    value = Decimal(str(amount))
    if value != value.to_integral_value() or value <= 0:
        raise ValueError("amount must be a positive whole SYP amount")
    return int(value)


def require_old_multiple_of_rate(amount) -> int:
    """توافق خلفي: أي مبلغ صحيح موجب مقبول في نظام 1=1."""
    value = Decimal(str(amount))
    if value != value.to_integral_value() or value <= 0:
        raise ValueError("amount must be a positive whole SYP amount")
    return int(value)


def format_new(amount) -> str:
    value = Decimal(str(amount))
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def format_old(amount) -> str:
    """توافق خلفي للعرض؛ يعرض نفس الليرة الجديدة."""
    return format_new(amount)
