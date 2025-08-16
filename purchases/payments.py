from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

from purchases.models import Supplier, SupplierAccount
from accounting.models import ChartOfAccounts, JournalEntry, JournalEntryLine
from treasury.models import update_treasury_balance

SUPPLIERS_CONTROL_ACCOUNT_CODE = '2110'
CASH_ACCOUNT_CODE = '1110'


def _get_suppliers_control_account():
    try:
        return ChartOfAccounts.objects.get(account_code=SUPPLIERS_CONTROL_ACCOUNT_CODE)
    except ChartOfAccounts.DoesNotExist:
        raise ValidationError('الرجاء إنشاء حساب مراقبة الموردين (2110) أولاً')


def _get_cash_account():
    try:
        return ChartOfAccounts.objects.get(account_code=CASH_ACCOUNT_CODE)
    except ChartOfAccounts.DoesNotExist:
        raise ValidationError('حساب الخزينة 1110 غير موجود في دليل الحسابات')


@transaction.atomic
def supplier_payment(supplier: Supplier, amount: Decimal, currency: str, user: User, note: str = ''):
    if amount <= 0:
        raise ValidationError('المبلغ يجب أن يكون أكبر من صفر')

    # 1) قيد اليومية: Dr دائنون - موردين، Cr خزينة
    suppliers_acc = _get_suppliers_control_account()
    cash_acc = _get_cash_account()

    je = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        entry_type='adjustment',
        description=f"سداد لمورد {supplier.name}",
        total_debit=amount,
        total_credit=amount,
        created_by=user,
        posted=True,
        reference_type='supplier_payment'
    )

    # مدين: دائنون - موردين (تخفيض الالتزام)
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=suppliers_acc,
        description='سداد لمورد - تخفيض رصيد الدائنين',
        debit=amount,
        credit=0,
        currency=currency,
        exchange_rate=1,
    )

    # دائن: خزينة
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=cash_acc,
        description='سداد نقدي لمورد',
        debit=0,
        credit=amount,
        currency=currency,
        exchange_rate=1,
    )

    # 2) تحديث الخزينة (نقص نقدي)
    update_treasury_balance(currency, amount, transaction_type='expense', description=f'سداد للمورد {supplier.name}', user=user)

    # 3) كشف المورد (debit)
    SupplierAccount.objects.create(
        supplier=supplier,
        transaction_type='payment',
        description=note or 'سداد لمورد',
        debit=amount,
        credit=Decimal('0'),
        balance=Decimal('0'),
        currency=currency,
        created_by=user,
    )

    return je

