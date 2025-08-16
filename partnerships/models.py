from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from decimal import Decimal
from core.models import GameZone


class Partnership(models.Model):
    """الشراكات في مناطق الألعاب - عدة شركاء لكل منطقة"""
    PARTNER_TYPE_CHOICES = [
        ('individual', 'فرد'),
        ('company', 'شركة'),
        ('investor', 'مستثمر'),
    ]

    zone = models.ForeignKey(GameZone, on_delete=models.CASCADE, related_name='partnerships', verbose_name="منطقة الألعاب")
    partner_name = models.CharField(max_length=200, verbose_name="اسم الشريك")
    partner_type = models.CharField(max_length=20, choices=PARTNER_TYPE_CHOICES, verbose_name="نوع الشريك")
    national_id = models.CharField(max_length=20, blank=True, verbose_name="الرقم القومي")  # للأفراد
    commercial_register = models.CharField(max_length=50, blank=True, verbose_name="السجل التجاري")  # للشركات
    percentage = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="نسبة الشريك %")  # نسبة الشريك

    # تفاصيل الشراكة
    investment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="مبلغ الاستثمار")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    start_date = models.DateField(verbose_name="تاريخ البداية")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاريخ النهاية")

    # الحسابات المحاسبية
    partner_account = models.CharField(max_length=20, blank=True, verbose_name="رقم حساب الشريك")  # رقم حساب الشريك

    # تحميل المصروفات
    share_expenses = models.BooleanField(default=True, verbose_name="يتحمل المصروفات")  # هل يتحمل نسبته من المصروفات؟
    expense_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="نسبة المصروفات %")  # نسبة مختلفة للمصروفات

    active = models.BooleanField(default=True, verbose_name="نشط")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    def __str__(self):
        return f"{self.partner_name} - {self.zone.name} ({self.percentage}%)"

    def get_expense_percentage(self):
        """حساب نسبة تحمل المصروفات"""
        if self.share_expenses:
            return self.expense_percentage or self.percentage
        return Decimal('0')

    def get_balance_by_currency(self, currency='EGP'):
        """الحصول على رصيد الشريك لعملة معينة"""
        accounts = PartnerAccount.objects.filter(
            partnership=self,
            currency=currency
        ).aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        total_debit = accounts['total_debit'] or Decimal('0')
        total_credit = accounts['total_credit'] or Decimal('0')
        return total_debit - total_credit

    def get_all_balances(self):
        """الحصول على أرصدة الشريك لجميع العملات"""
        balances = {}
        currencies = PartnerAccount.objects.filter(
            partnership=self
        ).values_list('currency', flat=True).distinct()

        for currency in currencies:
            balances[currency] = self.get_balance_by_currency(currency)

        return balances

    class Meta:
        unique_together = ['zone', 'partner_name']
        verbose_name = "شراكة"
        verbose_name_plural = "الشراكات"


class PartnerAccount(models.Model):
    """كشف حساب الشركاء - سجل جميع المعاملات"""
    TRANSACTION_TYPE_CHOICES = [
        ('revenue_share', 'حصة من الإيرادات'),
        ('expense_share', 'حصة من المصروفات'),
        ('payment_received', 'مبلغ مستلم'),
        ('payment_made', 'مبلغ مدفوع'),
        ('adjustment', 'تسوية'),
        ('opening_balance', 'رصيد أول المدة'),
    ]

    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, verbose_name="الشراكة")
    transaction_date = models.DateField(verbose_name="تاريخ المعاملة")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="نوع المعاملة")
    description = models.CharField(max_length=300, verbose_name="الوصف")
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="مدين (له)")  # مدين (له)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="دائن (عليه)")  # دائن (عليه)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="الرصيد الجاري")  # الرصيد الجاري
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")

    # ربط بالعمليات الأصلية
    revenue_id = models.IntegerField(null=True, blank=True, verbose_name="رقم الإيراد")
    expense_id = models.IntegerField(null=True, blank=True, verbose_name="رقم المصروف")
    payment_id = models.IntegerField(null=True, blank=True, verbose_name="رقم الدفعة")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def save(self, *args, **kwargs):
        # حساب الرصيد تلقائياً لكل عملة منفصلة
        if self.pk is None:  # سجل جديد
            # الحصول على آخر رصيد لنفس الشراكة ونفس العملة
            last_record = PartnerAccount.objects.filter(
                partnership=self.partnership,
                currency=self.currency
            ).order_by('-created_at').first()

            previous_balance = last_record.balance if last_record else Decimal('0')
            self.balance = previous_balance + (self.debit or Decimal('0')) - (self.credit or Decimal('0'))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partnership.partner_name} - {self.transaction_date} - {self.balance}"

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name = "كشف حساب شريك"
        verbose_name_plural = "كشوف حسابات الشركاء"


class PartnerPayment(models.Model):
    """مدفوعات الشركاء"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقداً'),
        ('bank_transfer', 'تحويل بنكي'),
        ('check', 'شيك'),
        ('credit_card', 'بطاقة ائتمان'),
    ]

    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, verbose_name="الشراكة")
    payment_date = models.DateField(verbose_name="تاريخ الدفع")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="المبلغ")
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name="طريقة الدفع")
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="رقم المرجع")  # رقم التحويل أو الشيك
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    # تأثير على الخزينة
    treasury_updated = models.BooleanField(default=False, verbose_name="تم تحديث الخزينة")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.treasury_updated:
            # تحديث كشف حساب الشريك
            PartnerAccount.objects.create(
                partnership=self.partnership,
                transaction_date=self.payment_date,
                transaction_type='payment_received',
                description=f"مبلغ مستلم - {self.get_payment_method_display()}",
                credit=self.amount,  # دائن (عليه)
                currency=self.currency,
                payment_id=self.id,
                created_by=self.created_by
            )

            # TODO: تحديث الخزينة (سيتم تطبيقه في تطبيق treasury)

            self.treasury_updated = True
            self.save(update_fields=['treasury_updated'])

    def __str__(self):
        return f"دفعة {self.partnership.partner_name} - {self.amount} {self.currency}"

    class Meta:
        verbose_name = "دفعة شريك"
        verbose_name_plural = "دفعات الشركاء"
