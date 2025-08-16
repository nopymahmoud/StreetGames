from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='sum_attr')
def sum_attr(iterable, attr_name):
    total = Decimal('0')
    for obj in iterable or []:
        value = getattr(obj, attr_name, 0) or 0
        try:
            total += Decimal(str(value))
        except Exception:
            try:
                total += Decimal(value)
            except Exception:
                continue
    return total

