from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from core.models import GameZone
from .models import JournalEntry, JournalEntryLine, ChartOfAccounts


class Expense(models.Model):
    """المصروفات - مربوطة بمنطقة الألعاب"""
    CATEGORY_CHOICES = [
        ('rent', 'إيجارات'),
        ('maintenance', 'صيانة'),
        ('salary', 'رواتب'),
        ('transport', 'مواصلات'),
        ('utilities', 'مرافق'),
        ('marketing', 'دعاية وإعلان'),
        ('supplies', 'مستلزمات'),
        ('insurance', 'تأمين'),
        ('other', 'أخرى'),
    ]
    
    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, verbose_name="منطقة الألعاب")
    date = models.DateField(verbose_name="التاريخ")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name="الفئة")
    description = models.CharField(max_length=300, verbose_name="الوصف")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), verbose_name="المبلغ")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    
    # تحميل المصروف على الشركاء
    charge_partners = models.BooleanField(default=True, verbose_name="تحميل على الشركاء")
    partner_shares_calculated = models.BooleanField(default=False, verbose_name="تم حساب حصص الشركاء")
    
    # المستندات
    receipt_number = models.CharField(max_length=100, blank=True, verbose_name="رقم الإيصال")
    supplier = models.CharField(max_length=200, blank=True, verbose_name="المورد")
    
    # التفاصيل المحاسبية
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="قيد اليومية")
    
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # إنشاء قيد محاسبي تلقائياً
            self.create_journal_entry()
            # توزيع التكلفة على الشركاء إذا مطلوب
            if self.charge_partners:
                self.calculate_partner_expense_shares()
    
    def create_journal_entry(self):
        """إنشاء قيد محاسبي للمصروف + تحديث الخزينة"""
        from treasury.models import update_treasury_balance

        journal_entry = JournalEntry.objects.create(
            entry_date=self.date,
            entry_type='expense',
            description=f"مصروف {self.get_category_display()} - {self.zone.name}",
            zone=self.zone,
            reference_type='expense',
            reference_id=self.id,
            created_by=self.created_by
        )

        # الطرف المدين: المصروفات
        if self.zone and self.zone.expense_account:
            try:
                expense_account = ChartOfAccounts.objects.get(account_code=self.zone.expense_account)
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=expense_account,
                    description=f"مصروف {self.description}",
                    debit=self.amount,
                    currency=self.currency
                )
            except ChartOfAccounts.DoesNotExist:
                pass

        # الطرف الدائن: الخزينة
        try:
            cash_account = ChartOfAccounts.objects.get(account_code='1110')
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                description=f"صرف نقدي - {self.description}",
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

        # تحديث الخزينة (نقص)
        update_treasury_balance(self.currency, self.amount, transaction_type='expense',
                                description=f'مصروف {self.description}',
                                user=self.created_by, reference_id=self.id)

        self.journal_entry = journal_entry
        self.save(update_fields=['journal_entry'])

    def calculate_partner_expense_shares(self):
        """حساب وتوزيع حصص المصروفات على الشركاء"""
        if self.partner_shares_calculated:
            return
        
        from partnerships.models import Partnership, PartnerAccount
        partnerships = Partnership.objects.filter(zone=self.zone, active=True, share_expenses=True)
        
        for partnership in partnerships:
            expense_percentage = partnership.get_expense_percentage()
            share_amount = (self.amount * expense_percentage) / 100
            
            # تسجيل في كشف حساب الشريك
            PartnerAccount.objects.create(
                partnership=partnership,
                transaction_date=self.date,
                transaction_type='expense_share',
                description=f"حصة من مصروف {self.get_category_display()} - {self.description[:50]}",
                credit=share_amount,  # دائن (عليه)
                currency=self.currency,
                expense_id=self.id,
                created_by=self.created_by
            )
        
        self.partner_shares_calculated = True
        self.save(update_fields=['partner_shares_calculated'])
    
    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency}"
    
    class Meta:
        verbose_name = "مصروف"
        verbose_name_plural = "المصروفات"
        ordering = ['-date']
