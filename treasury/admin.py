from django.contrib import admin
from .models import BankAccount, Treasury, TreasuryTransaction, BankTransaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_number', 'currency', 'current_balance', 'active']
    list_filter = ['currency', 'active', 'bank_name']
    search_fields = ['bank_name', 'account_number', 'account_name', 'iban']
    list_editable = ['active']
    readonly_fields = ['current_balance', 'created_at']


@admin.register(Treasury)
class TreasuryAdmin(admin.ModelAdmin):
    list_display = ['currency', 'balance', 'last_updated']
    list_filter = ['currency']
    readonly_fields = ['balance', 'last_updated']


@admin.register(TreasuryTransaction)
class TreasuryTransactionAdmin(admin.ModelAdmin):
    list_display = ['account_type', 'transaction_type', 'amount', 'description', 'transaction_date']
    list_filter = ['account_type', 'transaction_type', 'transaction_date']
    search_fields = ['description', 'reference_number']
    readonly_fields = ['transaction_date']
    date_hierarchy = 'transaction_date'


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ['bank_account', 'transaction_date', 'transaction_type', 'amount', 'balance_after']
    list_filter = ['bank_account', 'transaction_type', 'transaction_date']
    search_fields = ['description', 'reference_number', 'beneficiary']
    readonly_fields = ['balance_after', 'created_at']
    date_hierarchy = 'transaction_date'
