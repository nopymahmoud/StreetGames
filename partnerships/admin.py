from django.contrib import admin
from .models import Partnership, PartnerAccount, PartnerPayment


@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
    list_display = ['partner_name', 'zone', 'percentage', 'partner_type', 'start_date', 'active']
    list_filter = ['zone', 'partner_type', 'active', 'start_date']
    search_fields = ['partner_name', 'zone__name', 'national_id', 'commercial_register']
    list_editable = ['active']
    readonly_fields = ['created_at'] if hasattr(Partnership, 'created_at') else []


@admin.register(PartnerAccount)
class PartnerAccountAdmin(admin.ModelAdmin):
    list_display = ['partnership', 'transaction_date', 'transaction_type', 'debit', 'credit', 'balance', 'currency']
    list_filter = ['transaction_type', 'currency', 'transaction_date']
    search_fields = ['partnership__partner_name', 'description']
    readonly_fields = ['balance', 'created_at']
    date_hierarchy = 'transaction_date'


@admin.register(PartnerPayment)
class PartnerPaymentAdmin(admin.ModelAdmin):
    list_display = ['partnership', 'payment_date', 'amount', 'currency', 'payment_method', 'treasury_updated']
    list_filter = ['payment_method', 'currency', 'treasury_updated', 'payment_date']
    search_fields = ['partnership__partner_name', 'reference_number']
    readonly_fields = ['treasury_updated', 'created_at']
    date_hierarchy = 'payment_date'
