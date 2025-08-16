from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class BankAccount(models.Model):
    """الحسابات البنكية"""
    bank_name = models.CharField(max_length=200, verbose_name="اسم البنك")
    account_number = models.CharField(max_length=50, verbose_name="رقم الحساب")
    account_name = models.CharField(max_length=200, verbose_name="اسم الحساب")
    iban = models.CharField(max_length=50, blank=True, verbose_name="رقم الآيبان")
    swift_code = models.CharField(max_length=20, blank=True, verbose_name="رمز السويفت")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="الرصيد الافتتاحي")
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="الرصيد الحالي")

    # ربط بدليل الحسابات
    chart_account_code = models.CharField(max_length=20, blank=True, verbose_name="رقم الحساب في دليل الحسابات")

    active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

    class Meta:
        verbose_name = "حساب بنكي"
        verbose_name_plural = "الحسابات البنكية"


class Treasury(models.Model):
    """الخزينة - كل عملة منفصلة"""
    currency = models.CharField(max_length=3, unique=True, verbose_name="العملة")
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="الرصيد")

    # ربط بدليل الحسابات
    chart_account_code = models.CharField(max_length=20, blank=True, verbose_name="رقم الحساب في دليل الحسابات")

    last_updated = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    def __str__(self):
        return f"خزينة {self.currency}: {self.balance}"

    class Meta:
        verbose_name = "خزينة"
        verbose_name_plural = "الخزائن"


class TreasuryTransaction(models.Model):
    """سجل حركات الخزينة والبنوك"""
    TRANSACTION_TYPES = [
        ('revenue', 'إيراد'),
        ('expense', 'مصروف'),
        ('expense_reversal', 'عكس مصروف'),
        ('revenue_reversal', 'عكس إيراد'),
        ('bank_deposit', 'إيداع بنكي'),
        ('bank_withdrawal', 'سحب من البنك'),
        ('exchange_in', 'تحويل داخل'),
        ('exchange_out', 'تحويل خارج'),
        ('partner_payment', 'دفعة شريك'),
        ('opening', 'رصيد أول المدة'),
        ('adjustment', 'تسوية'),
    ]

    ACCOUNT_TYPE_CHOICES = [
        ('treasury', 'خزينة'),
        ('bank', 'بنك'),
    ]

    # نوع الحساب (خزينة أو بنك)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, verbose_name="نوع الحساب")
    treasury = models.ForeignKey(Treasury, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الخزينة")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب البنكي")

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="نوع المعاملة")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")
    description = models.CharField(max_length=300, verbose_name="الوصف")
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="رقم المرجع")  # رقم الشيك أو التحويل

    # ربط بالعمليات الأصلية
    reference_type = models.CharField(max_length=20, blank=True, verbose_name="نوع المرجع")
    reference_id = models.IntegerField(null=True, blank=True, verbose_name="رقم المرجع")

    transaction_date = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ المعاملة")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")

    def __str__(self):
        account_name = self.treasury.currency if self.treasury else self.bank_account.bank_name
        return f"{account_name} - {self.amount} - {self.description}"

    class Meta:
        verbose_name = "معاملة خزينة"
        verbose_name_plural = "معاملات الخزينة"
        ordering = ['-transaction_date']


class BankTransaction(models.Model):
    """معاملات البنوك المفصلة"""
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'إيداع'),
        ('withdrawal', 'سحب'),
        ('transfer_in', 'تحويل وارد'),
        ('transfer_out', 'تحويل صادر'),
        ('fee', 'رسوم'),
        ('interest', 'فوائد'),
    ]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, verbose_name="الحساب البنكي")
    transaction_date = models.DateField(verbose_name="تاريخ المعاملة")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="نوع المعاملة")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")
    description = models.CharField(max_length=300, verbose_name="الوصف")
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="رقم المرجع")

    # معلومات إضافية
    beneficiary = models.CharField(max_length=200, blank=True, verbose_name="المستفيد")  # المستفيد
    purpose = models.CharField(max_length=300, blank=True, verbose_name="الغرض")  # الغرض

    # الرصيد بعد المعاملة
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="الرصيد بعد المعاملة")

    # ربط بقيد محاسبي
    journal_entry_id = models.IntegerField(null=True, blank=True, verbose_name="رقم قيد اليومية")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            # تحديث رصيد البنك
            if self.transaction_type in ['deposit', 'transfer_in', 'interest']:
                self.bank_account.current_balance += self.amount
            else:
                self.bank_account.current_balance -= self.amount

            self.balance_after = self.bank_account.current_balance
            self.bank_account.save()

        super().save(*args, **kwargs)

        if is_new:
            # TODO: إنشاء قيد محاسبي (سيتم تطبيقه لاحقاً)
            pass

    def __str__(self):
        return f"{self.bank_account.bank_name} - {self.transaction_date} - {self.amount}"

    class Meta:
        verbose_name = "معاملة بنكية"
        verbose_name_plural = "المعاملات البنكية"
        ordering = ['-transaction_date']


# دالة مساعدة لتحديث رصيد الخزينة
def update_treasury_balance(currency, amount, transaction_type, description, user, reference_id=None):
    """تحديث رصيد الخزينة"""
    treasury, created = Treasury.objects.get_or_create(currency=currency)

    # تحديث الرصيد
    if transaction_type in ['revenue', 'partner_payment', 'bank_withdrawal', 'exchange_in', 'expense_reversal']:
        treasury.balance += amount
    else:
        treasury.balance -= amount

    treasury.save()

    # تسجيل المعاملة
    TreasuryTransaction.objects.create(
        account_type='treasury',
        treasury=treasury,
        transaction_type=transaction_type,
        amount=amount,
        description=description,
        reference_type=transaction_type,
        reference_id=reference_id,
        created_by=user
    )
