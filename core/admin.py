from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Hotel, GameZone, GameType, Warehouse, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'ملف المستخدم'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'userprofile__role')

    def get_role(self, obj):
        if hasattr(obj, 'userprofile'):
            return obj.userprofile.get_role_display()
        return '-'
    get_role.short_description = 'الدور'


# إعادة تسجيل User مع الإعدادات الجديدة
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'can_access_all_zones', 'preferred_currency']
    list_filter = ['role', 'can_access_all_zones', 'preferred_currency']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone']
    filter_horizontal = ['allowed_zones']


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'manager', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['name', 'location']
    list_editable = ['active']


@admin.register(GameZone)
class GameZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'hotel', 'code', 'monthly_rent', 'currency', 'manager', 'active']
    list_filter = ['hotel', 'active', 'currency', 'opening_date']
    search_fields = ['name', 'code', 'hotel__name']
    list_editable = ['active']
    readonly_fields = ['created_at'] if hasattr(GameZone, 'created_at') else []


@admin.register(GameType)
class GameTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'active', 'created_at']
    list_filter = ['category', 'active', 'created_at']
    search_fields = ['name', 'code']
    list_editable = ['active']


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'warehouse_type', 'location', 'manager', 'active']
    list_filter = ['warehouse_type', 'active', 'created_at']
    search_fields = ['name', 'code', 'location']
    list_editable = ['active']
