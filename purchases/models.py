from __future__ import annotations
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import GameZone
from accounting.models import ChartOfAccounts, JournalEntry, JournalEntryLine


class Supplier(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم المورد')
    code = models.CharField(max_length=20, unique=True, verbose_name='كود المورد')
    phone = models.CharField(max_length=50, blank=True, verbose_name='الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد')
    address = models.TextField(blank=True, verbose_name='العنوان')
    currency = models.CharField(max_length=3, default='EGP', verbose_name='العملة')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='أنشأ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = 'مورد'
        verbose_name_plural = 'الموردون'


class SupplierAccount(models.Model):
    TRANSACTION_TYPES = [
        ('bill', 'فاتورة مشتريات'),
        ('return', 'مرتجع مشتريات'),
        ('payment', 'سداد لمورد'),
        ('adjustment', 'تسوية'),
        ('opening', 'رصيد افتتاحي'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name='المورد')
    trans_date = models.DateField(default=timezone.now, verbose_name='التاريخ')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name='النوع')
    description = models.CharField(max_length=200, blank=True, verbose_name='الوصف')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='مدين (لصالح الشركة)')
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='دائن (على الشركة)')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='الرصيد الجاري')
    currency = models.CharField(max_length=3, default='EGP', verbose_name='العملة')
    reference_type = models.CharField(max_length=20, blank=True, verbose_name='نوع المرجع')
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='رقم المرجع')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'كشف حساب مورد'
        verbose_name_plural = 'كشوف حسابات الموردين'
        ordering = ['-trans_date', '-id']


class PurchaseBill(models.Model):
    zone = models.ForeignKey(GameZone, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المنطقة')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name='المورد')
    bill_number = models.CharField(max_length=50, verbose_name='رقم الفاتورة')
    bill_date = models.DateField(default=timezone.now, verbose_name='تاريخ الفاتورة')
    currency = models.CharField(max_length=3, default='EGP', verbose_name='العملة')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='الإجمالي قبل الضرائب')
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='الضرائب')
    other_costs = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='تكاليف أخرى')
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='الإجمالي')
    posted = models.BooleanField(default=False, verbose_name='مرحلة')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def recalc_totals(self):
        s = Decimal('0')
        for ln in self.lines.all():
            s += ln.amount
        self.subtotal = s
        self.total = (self.subtotal or 0) + (self.tax_amount or 0) + (self.other_costs or 0)

    def save(self, *args, **kwargs):
        self.recalc_totals()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'فاتورة مشتريات'
        verbose_name_plural = 'فواتير المشتريات'


class PurchaseBillLine(models.Model):
    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT, verbose_name='حساب التكلفة/المخزون')
    description = models.CharField(max_length=300, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


class PurchaseReturn(models.Model):
    zone = models.ForeignKey(GameZone, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المنطقة')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name='المورد')
    bill = models.ForeignKey(PurchaseBill, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة مرتبطة')
    return_number = models.CharField(max_length=50)
    return_date = models.DateField(default=timezone.now)
    currency = models.CharField(max_length=3, default='EGP')
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    posted = models.BooleanField(default=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مرتجع مشتريات'
        verbose_name_plural = 'مرتجعات المشتريات'


class PurchaseReturnLine(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)
    description = models.CharField(max_length=300, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.unit_price or 0)
        super().save(*args, **kwargs)


# Posting services
SUPPLIERS_CONTROL_ACCOUNT_CODE = '2110'  # دائنون


def _get_suppliers_control_account() -> ChartOfAccounts:
    try:
        return ChartOfAccounts.objects.get(account_code=SUPPLIERS_CONTROL_ACCOUNT_CODE)
    except ChartOfAccounts.DoesNotExist:
        raise ValidationError('الرجاء إنشاء حساب مراقبة الموردين (2110) أولاً في دليل الحسابات')


@transaction.atomic
def post_purchase_bill(bill: PurchaseBill, user: User):
    if bill.posted:
        return bill

    suppliers_account = _get_suppliers_control_account()

    je = JournalEntry.objects.create(
        entry_date=bill.bill_date,
        entry_type='expense',
        description=f"فاتورة مشتريات #{bill.bill_number} - {bill.supplier.name}",
        total_debit=bill.total,
        total_credit=bill.total,
        zone=bill.zone,
        reference_type='purchase_bill',
        reference_id=bill.id,
        posted=True,
        created_by=user,
    )

    # Debit: cost/inventory accounts (by lines)
    for ln in bill.lines.all():
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=ln.account,
            description=ln.description or 'مشتريات',
            debit=ln.amount,
            credit=0,
            currency=bill.currency,
            exchange_rate=1,
        )

    # Credit: suppliers control
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=suppliers_account,
        description='دائنون - موردين',
        debit=0,
        credit=bill.total,
        currency=bill.currency,
        exchange_rate=1,
    )

    bill.posted = True
    bill.journal_entry = je
    bill.save(update_fields=['posted', 'journal_entry', 'subtotal', 'total'])

    # Supplier ledger (credit increases payable)
    SupplierAccount.objects.create(
        supplier=bill.supplier,
        trans_date=bill.bill_date,
        transaction_type='bill',
        description=f"فاتورة مشتريات #{bill.bill_number}",
        debit=Decimal('0'),
        credit=bill.total,
        balance=Decimal('0'),  # يمكن لاحقاً حساب الجاري بالتجميع
        currency=bill.currency,
        reference_type='purchase_bill',
        reference_id=bill.id,
        created_by=user,
    )

    return bill


@transaction.atomic
def unpost_purchase_bill(bill: PurchaseBill):
    if not bill.posted:
        return bill
    if bill.journal_entry:
        bill.journal_entry.delete()
    bill.posted = False
    bill.journal_entry = None
    bill.save(update_fields=['posted', 'journal_entry'])
    SupplierAccount.objects.filter(reference_type='purchase_bill', reference_id=bill.id).delete()
    return bill


@transaction.atomic
def post_purchase_return(ret: PurchaseReturn, user: User):
    if ret.posted:
        return ret

    suppliers_account = _get_suppliers_control_account()

    total = sum((ln.amount for ln in ret.lines.all()), Decimal('0'))
    ret.total = total
    ret.save(update_fields=['total'])

    je = JournalEntry.objects.create(
        entry_date=ret.return_date,
        entry_type='adjustment',
        description=f"مرتجع مشتريات #{ret.return_number} - {ret.supplier.name}",
        total_debit=total,
        total_credit=total,
        zone=ret.zone,
        reference_type='purchase_return',
        reference_id=ret.id,
        posted=True,
        created_by=user,
    )

    # Debit: suppliers control (reduce payable)
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=suppliers_account,
        description='دائنون - موردين (مرتجع)',
        debit=total,
        credit=0,
        currency=ret.currency,
        exchange_rate=1,
    )

    # Credit: cost/inventory accounts by lines
    for ln in ret.lines.all():
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=ln.account,
            description=ln.description or 'مرتجع مشتريات',
            debit=0,
            credit=ln.amount,
            currency=ret.currency,
            exchange_rate=1,
        )

    ret.posted = True
    ret.journal_entry = je
    ret.save(update_fields=['posted', 'journal_entry'])

    SupplierAccount.objects.create(
        supplier=ret.supplier,
        trans_date=ret.return_date,
        transaction_type='return',
        description=f"مرتجع مشتريات #{ret.return_number}",
        debit=total,
        credit=Decimal('0'),
        balance=Decimal('0'),
        currency=ret.currency,
        reference_type='purchase_return',
        reference_id=ret.id,
        created_by=user,
    )

    return ret


@transaction.atomic
def unpost_purchase_return(ret: PurchaseReturn):
    if not ret.posted:
        return ret
    if ret.journal_entry:
        ret.journal_entry.delete()
    ret.posted = False
    ret.journal_entry = None
    ret.save(update_fields=['posted', 'journal_entry'])
    SupplierAccount.objects.filter(reference_type='purchase_return', reference_id=ret.id).delete()
    return ret

