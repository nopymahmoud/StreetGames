from django.db import models
from django.contrib.auth.models import User, Group
from decimal import Decimal


class UserProfile(models.Model):
    """ملف المستخدم الموسع"""
    USER_ROLE_CHOICES = [
        ('admin', 'مدير النظام'),
        ('manager', 'مدير عام'),
        ('zone_manager', 'مدير منطقة'),
        ('accountant', 'محاسب'),
        ('cashier', 'أمين صندوق'),
        ('viewer', 'مستعلم'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="المستخدم")
    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default='viewer', verbose_name="الدور")
    phone = models.CharField(max_length=20, blank=True, verbose_name="رقم الهاتف")
    address = models.TextField(blank=True, verbose_name="العنوان")

    # صلاحيات خاصة
    can_access_all_zones = models.BooleanField(default=False, verbose_name="الوصول لجميع المناطق")
    allowed_zones = models.ManyToManyField('GameZone', blank=True, verbose_name="المناطق المسموحة")

    # إعدادات العرض
    preferred_currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة المفضلة")
    dashboard_layout = models.CharField(max_length=20, default='default', verbose_name="تخطيط لوحة التحكم")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"

    def has_zone_access(self, zone):
        """التحقق من صلاحية الوصول لمنطقة معينة"""
        if self.can_access_all_zones or self.role in ['admin', 'manager']:
            return True
        return self.allowed_zones.filter(id=zone.id).exists()

    def get_accessible_zones(self):
        """الحصول على المناطق التي يمكن للمستخدم الوصول إليها"""
        if self.can_access_all_zones or self.role in ['admin', 'manager']:
            return GameZone.objects.filter(active=True)
        return self.allowed_zones.filter(active=True)

    class Meta:
        verbose_name = "ملف مستخدم"
        verbose_name_plural = "ملفات المستخدمين"


# إشارات لإنشاء ملف المستخدم تلقائياً
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()
    else:
        UserProfile.objects.create(user=instance)


class Hotel(models.Model):
    """الفنادق - مجرد تجميع للمناطق"""
    name = models.CharField(max_length=200, verbose_name="اسم الفندق")
    location = models.CharField(max_length=200, verbose_name="الموقع")
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المدير")
    active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "فندق"
        verbose_name_plural = "الفنادق"


class GameZone(models.Model):
    """مناطق الألعاب - مركز التكاليف الأساسي"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, verbose_name="الفندق")
    name = models.CharField(max_length=200, verbose_name="اسم المنطقة")
    code = models.CharField(max_length=20, unique=True, verbose_name="كود المنطقة")  # كود المنطقة للمحاسبة
    area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="المساحة")
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="الإيجار الشهري")  # إيجار المنطقة
    currency = models.CharField(max_length=3, default='EGP', verbose_name="العملة")
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المدير")
    active = models.BooleanField(default=True, verbose_name="نشط")
    opening_date = models.DateField(verbose_name="تاريخ الافتتاح")

    # الحسابات المحاسبية للمنطقة
    revenue_account = models.CharField(max_length=20, blank=True, verbose_name="رقم حساب الإيرادات")  # رقم حساب الإيرادات
    expense_account = models.CharField(max_length=20, blank=True, verbose_name="رقم حساب المصروفات")  # رقم حساب المصروفات

    def __str__(self):
        # عرض اسم المنطقة فقط في جميع القوائم والنماذج
        return self.name

    class Meta:
        verbose_name = "منطقة ألعاب"
        verbose_name_plural = "مناطق الألعاب"


class GameType(models.Model):
    """أنواع الألعاب"""
    CATEGORY_CHOICES = [
        ('electronic', 'ألعاب إلكترونية'),
        ('mechanical', 'ألعاب ميكانيكية'),
        ('inflatable', 'ألعاب هوائية'),
        ('vehicles', 'مركبات'),
        ('arcade', 'ألعاب أركيد'),
        ('vr', 'واقع افتراضي'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="اسم نوع اللعبة")
    code = models.CharField(max_length=20, unique=True, verbose_name="كود نوع اللعبة")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="الفئة")
    active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "نوع لعبة"
        verbose_name_plural = "أنواع الألعاب"


class Warehouse(models.Model):
    """المخازن والمستودعات"""
    WAREHOUSE_TYPE_CHOICES = [
        ('main', 'مخزن رئيسي'),
        ('branch', 'مخزن فرعي'),
        ('maintenance', 'مخزن صيانة'),
        ('spare_parts', 'مخزن قطع غيار'),
    ]

    name = models.CharField(max_length=200, verbose_name="اسم المخزن")
    code = models.CharField(max_length=20, unique=True, verbose_name="كود المخزن")
    location = models.CharField(max_length=300, verbose_name="الموقع")
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPE_CHOICES, verbose_name="نوع المخزن")
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المدير")
    active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = "مخزن"
        verbose_name_plural = "المخازن"
