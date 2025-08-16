from __future__ import annotations
from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


def _to_decimal(val) -> Decimal:
    try:
        if isinstance(val, Decimal):
            return val
        # Keep as string to avoid float precision issues
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


@register.filter(name='money')
def money(value, digits: int = 2):
    """Format numbers as 1,234.56 regardless of locale.
    Usage: {{ value|money }} or {{ value|money:0 }}
    """
    d = _to_decimal(value)
    try:
        prec = max(0, int(digits))
    except Exception:
        prec = 2
    fmt = '{:,.%df}' % prec
    return fmt.format(d)


@register.filter(name='num')
def num(value, digits: int = 0):
    """Generic number format same as money but default 0 decimals."""
    return money(value, digits)

