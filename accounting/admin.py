from django.contrib import admin
from .models import ChartOfAccounts, JournalEntry, JournalEntryLine, DailyRevenue
from .expense_models import Expense
from .forms import ChartOfAccountsForm


@admin.register(ChartOfAccounts)
class ChartOfAccountsAdmin(admin.ModelAdmin):
    form = ChartOfAccountsForm  # استخدم نفس النموذج الذي يعرض قائمة العملات الموحدة
    list_display = ['account_code', 'account_name', 'account_type', 'balance_type', 'current_balance', 'currency', 'active']
    list_filter = ['account_type', 'balance_type', 'currency', 'active', 'level']
    search_fields = ['account_code', 'account_name']
    list_editable = ['active']
    ordering = ['account_code']


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0
    readonly_fields = ['currency']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'entry_date', 'entry_type', 'description', 'total_debit', 'total_credit', 'posted']
    list_filter = ['entry_type', 'posted', 'entry_date', 'zone']
    search_fields = ['entry_number', 'description']
    readonly_fields = ['entry_number', 'total_debit', 'total_credit', 'created_at']
    date_hierarchy = 'entry_date'
    inlines = [JournalEntryLineInline]


@admin.register(DailyRevenue)
class DailyRevenueAdmin(admin.ModelAdmin):
    list_display = ['zone', 'date', 'amount', 'currency', 'payment_method', 'partner_shares_calculated']
    list_filter = ['zone', 'currency', 'payment_method', 'partner_shares_calculated', 'date']
    search_fields = ['zone__name', 'description']
    readonly_fields = ['journal_entry', 'partner_shares_calculated', 'created_at']
    date_hierarchy = 'date'


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['zone', 'date', 'category', 'description', 'amount', 'currency', 'charge_partners']
    list_filter = ['zone', 'category', 'currency', 'charge_partners', 'date']
    search_fields = ['description', 'supplier', 'receipt_number']
    readonly_fields = ['journal_entry', 'partner_shares_calculated', 'created_at']
    date_hierarchy = 'date'

# ExchangeRate admin
try:
    from .exchange_models import ExchangeRate

    @admin.register(ExchangeRate)
    class ExchangeRateAdmin(admin.ModelAdmin):
        list_display = ["currency", "rate_type", "rate_date", "rate", "source"]
        list_filter = ["currency", "rate_type", "rate_date"]
        search_fields = ["currency", "source"]
        date_hierarchy = "rate_date"
except Exception:
    pass

