from __future__ import annotations
from decimal import Decimal
from typing import Optional
from datetime import date

from django.db import models
from core.utils import get_supported_currencies

SUPPORTED_CURRENCIES = get_supported_currencies()  # [(code, label_ar)]


class ExchangeRate(models.Model):
    """سعر صرف بسيط يدعم نوعين: إقفال (closing) ومتوسط (average).
    نفترض أن الحقل `rate` يمثل مقدار عملة العرض (EGP افتراضاً) لكل 1 من العملة الأجنبية.
    يمكن استخدامه لأي عملة، والتحويل بين عملتين يتم بقسمة معدليهما مقابل عملة العرض.
    """

    RATE_TYPE_CHOICES = [
        ("closing", "Closing"),
        ("average", "Average"),
    ]

    currency = models.CharField(max_length=3, choices=SUPPORTED_CURRENCIES, default="EGP")
    rate_date = models.DateField()
    rate_type = models.CharField(max_length=10, choices=RATE_TYPE_CHOICES, default="closing")
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("currency", "rate_date", "rate_type")
        ordering = ["-rate_date"]

    def __str__(self) -> str:  # pragma: no cover - تمثيل نصي فقط
        return f"{self.currency} {self.rate_type} {self.rate_date}: {self.rate}"


# ===== Utilities =====
DEFAULT_PRESENTATION_CURRENCY = "EGP"


def _get_last_rate(currency: str, on_or_before: date, rate_type: str) -> Optional[Decimal]:
    qs = (
        ExchangeRate.objects.filter(currency=currency, rate_type=rate_type, rate_date__lte=on_or_before)
        .order_by("-rate_date")
        .values_list("rate", flat=True)
    )
    return qs.first() if qs.exists() else None


def get_rate(currency: str, on_or_before: date, rate_type: str = "closing",
             fallback_to_other_type: bool = True) -> Optional[Decimal]:
    """أرجع سعر الصرف لعملة مقابل عملة العرض (EGP) في أو قبل التاريخ المحدد.
    يعيد None إذا لا يوجد سعر. يمكن تفعيل fallback لاستخدام النوع الآخر عند عدم التوفر.
    """
    if not currency:
        return None
    if currency.upper() == DEFAULT_PRESENTATION_CURRENCY:
        return Decimal("1")

    rate = _get_last_rate(currency.upper(), on_or_before, rate_type)
    if rate is None and fallback_to_other_type:
        alt = "average" if rate_type == "closing" else "closing"
        rate = _get_last_rate(currency.upper(), on_or_before, alt)
    return rate


def convert_amount(amount: Decimal | float | int, from_currency: str, to_currency: str,
                   on_or_before: date, rate_type: str = "closing") -> Optional[Decimal]:
    """حوّل قيمة بين عملتين باستخدام أسعار مسجلة مقابل عملة العرض.
    المنطق: amt * (rate(from)/rate(to)) حيث rate(*) هو مقابل عملة العرض.
    يعيد None إذا لم تتوفر الأسعار المطلوبة.
    """
    from_currency = (from_currency or "").upper()
    to_currency = (to_currency or "").upper()
    amt = Decimal(str(amount or 0))

    if from_currency == to_currency:
        return amt

    # احصل على أسعار كلتا العملتين مقابل عملة العرض
    from_rate = get_rate(from_currency, on_or_before, rate_type)
    to_rate = get_rate(to_currency, on_or_before, rate_type)

    if from_rate is None or to_rate is None:
        return None

    # amt_in_presentation = amt * from_rate
    # convert to target = amt_in_presentation / to_rate
    return (amt * from_rate) / to_rate

