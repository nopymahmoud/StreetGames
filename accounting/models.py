from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from core.models import GameZone


class ChartOfAccounts(models.Model):
    """دليل الحسابات - الشجرة المحاسبية الكاملة"""
    ACCOUNT_TYPE_CHOICES = [
        ('asset', 'أصول'),
        ('liability', 'خصوم'),
        ('equity', 'حقوق ملكية'),
        ('revenue', 'إيرادات'),
        ('expense', 'مصروفات'),
        ('cost', 'تكلفة'),
    ]

    BALANCE_TYPE_CHOICES = [
        ('debit', 'مدين'),
        ('credit', 'دائن'),
    ]

    account_code = models.CharField(max_length=20, unique=True, verbose_name="رقم الحساب")
    account_name = models.CharField(max_length=200, verbose_name="اسم الحساب")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name="نوع الحساب")
    parent_account = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name="الحساب الأب")
    level = models.IntegerField(default=1, verbose_name="المستوى")  # مستوى الحساب في الشجرة
    is_main_account = models.BooleanField(default=False, verbose_name="حساب رئيسي")  # حساب رئيسي أم فرعي
    balance_type = models.CharField(max_length=10, choices=BALANCE_TYPE_CHOICES, verbose_name="طبيعة الرصيد")
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="الرصيد الافتتاحي")
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="الرصيد الحالي")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    active = models.BooleanField(default=True, verbose_name="نشط")

    def __str__(self):
        return f"{self.account_code} - {self.account_name}"

    class Meta:
        ordering = ['account_code']
        verbose_name = "حساب"
        verbose_name_plural = "دليل الحسابات"


class JournalEntry(models.Model):
    """قيود اليومية - نظام القيد المزدوج"""
    ENTRY_TYPE_CHOICES = [
        ('revenue', 'إيراد'),
        ('expense', 'مصروف'),
        ('transfer', 'تحويل'),
        ('adjustment', 'تسوية'),
        ('opening', 'رصيد أول المدة'),
        ('closing', 'قفل حسابات'),
    ]

    entry_number = models.CharField(max_length=20, unique=True, verbose_name="رقم القيد")
    entry_date = models.DateField(verbose_name="تاريخ القيد")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, verbose_name="نوع القيد")
    description = models.CharField(max_length=300, verbose_name="الوصف")
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="إجمالي المدين")
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="إجمالي الدائن")

    # ربط بالعمليات الأصلية
    zone = models.ForeignKey(GameZone, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="منطقة الألعاب")
    reference_type = models.CharField(max_length=20, blank=True, verbose_name="نوع المرجع")  # نوع المرجع
    reference_id = models.IntegerField(null=True, blank=True, verbose_name="رقم المرجع")  # رقم المرجع

    posted = models.BooleanField(default=False, verbose_name="تم الترحيل")  # هل تم ترحيل القيد؟
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def save(self, *args, **kwargs):
        if not self.entry_number:
            # ترقيم تلقائي للقيود
            last_entry = JournalEntry.objects.order_by('-entry_number').first()
            if last_entry and last_entry.entry_number.startswith('JE-'):
                try:
                    last_number = int(last_entry.entry_number.split('-')[-1])
                    self.entry_number = f"JE-{str(last_number + 1).zfill(6)}"
                except (ValueError, IndexError):
                    self.entry_number = "JE-000001"
            else:
                self.entry_number = "JE-000001"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_number} - {self.description}"

    class Meta:
        verbose_name = "قيد يومية"
        verbose_name_plural = "قيود اليومية"
        ordering = ['-entry_date', '-created_at']


class JournalEntryLine(models.Model):
    """تفاصيل قيود اليومية"""
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines', verbose_name="قيد اليومية")
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.CASCADE, verbose_name="الحساب")
    description = models.CharField(max_length=200, verbose_name="الوصف")
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="مدين")
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name="دائن")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1'), verbose_name="سعر الصرف")

    def __str__(self):
        return f"{self.journal_entry.entry_number} - {self.account.account_name}"

    class Meta:
        verbose_name = "تفصيل قيد يومية"
        verbose_name_plural = "تفاصيل قيود اليومية"


class DailyRevenue(models.Model):
    """الإيرادات اليومية - مربوطة بمنطقة الألعاب"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقداً'),
        ('card', 'بطاقة'),
        ('mixed', 'مختلط'),
    ]

    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, verbose_name="منطقة الألعاب")
    date = models.DateField(verbose_name="التاريخ")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash', verbose_name="طريقة الدفع")

    # التفاصيل المحاسبية
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="قيد اليومية")
    partner_shares_calculated = models.BooleanField(default=False, verbose_name="تم حساب حصص الشركاء")

    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            # إنشاء قيد محاسبي تلقائياً
            self.create_journal_entry()
            # توزيع الحصص على الشركاء
            self.calculate_partner_shares()

    def create_journal_entry(self):
        """إنشاء قيد محاسبي للإيراد + تحديث الخزينة"""
        from treasury.models import update_treasury_balance

        journal_entry = JournalEntry.objects.create(
            entry_date=self.date,
            entry_type='revenue',
            description=f"إيراد منطقة {self.zone.name} - {self.date}",
            zone=self.zone,
            reference_type='revenue',
            reference_id=self.id,
            created_by=self.created_by
        )

        # الطرف المدين: الخزينة أو البنك حسب طريقة الدفع
        try:
            if self.payment_method == 'card':
                debit_acc = ChartOfAccounts.objects.get(account_code='1120')  # بنك/بطاقات
                debit_desc = f"إيراد عبر بطاقة - {self.zone.name}"
            else:
                debit_acc = ChartOfAccounts.objects.get(account_code='1110')  # الخزينة
                debit_desc = f"إيراد نقدي - {self.zone.name}"

            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=debit_acc,
                description=debit_desc,
                debit=self.amount,
                currency=self.currency
            )
        except ChartOfAccounts.DoesNotExist:
            pass  # سيتم إنشاء دليل الحسابات لاحقاً

        # الطرف الدائن: الإيرادات
        if self.zone and self.zone.revenue_account:
            try:
                revenue_account = ChartOfAccounts.objects.get(account_code=self.zone.revenue_account)
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=revenue_account,
                    description=f"إيراد منطقة {self.zone.name}",
                    credit=self.amount,
                    currency=self.currency
                )
            except ChartOfAccounts.DoesNotExist:
                pass

        # تحديث إجماليات القيد
        journal_entry.total_debit = self.amount
        journal_entry.total_credit = self.amount
        journal_entry.posted = True
        journal_entry.save()

        # تحديث الخزينة
        update_treasury_balance(self.currency, self.amount, transaction_type='revenue',
                                description=f'إيراد {self.zone.name if self.zone else ""}',
                                user=self.created_by, reference_id=self.id)

        self.journal_entry = journal_entry
        self.save(update_fields=['journal_entry'])

    def calculate_partner_shares(self):
        """حساب وتوزيع حصص الشركاء"""
        if self.partner_shares_calculated:
            return

        from partnerships.models import Partnership, PartnerAccount
        partnerships = Partnership.objects.filter(zone=self.zone, active=True)

        for partnership in partnerships:
            share_amount = (self.amount * partnership.percentage) / 100

            # تسجيل في كشف حساب الشريك
            PartnerAccount.objects.create(
                partnership=partnership,
                transaction_date=self.date,
                transaction_type='revenue_share',
                description=f"حصة من إيراد {self.date}",
                debit=share_amount,  # مدين (له)
                currency=self.currency,
                revenue_id=self.id,
                created_by=self.created_by
            )

        self.partner_shares_calculated = True
        self.save(update_fields=['partner_shares_calculated'])

    def __str__(self):
        return f"إيراد {self.zone.name} - {self.date} - {self.amount} {self.currency}"

    class Meta:
        unique_together = ['zone', 'date', 'currency']
        verbose_name = "إيراد يومي"
        verbose_name_plural = "الإيرادات اليومية"
        ordering = ['-date']


# Import Expense model from separate file
from .expense_models import Expense
