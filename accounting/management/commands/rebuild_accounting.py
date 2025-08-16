from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal

from accounting.models import ChartOfAccounts, JournalEntry, JournalEntryLine, DailyRevenue
from accounting.expense_models import Expense
from partnerships.models import PartnerAccount
from treasury.models import Treasury, TreasuryTransaction, BankAccount, BankTransaction


class Command(BaseCommand):
    help = "تنظيف القيود اليتيمة وإعادة احتساب أرصدة الحسابات والخزائن والبنوك من الحركات الفعلية"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('بدء إعادة بناء الحسابات...'))

        # 1) حذف قيود اليومية اليتيمة المرتبطة بإيرادات/مصروفات محذوفة
        orphan_ids = []
        for je in JournalEntry.objects.filter(reference_type__in=['revenue','expense']):
            if je.reference_type == 'revenue' and not DailyRevenue.objects.filter(id=je.reference_id).exists():
                orphan_ids.append(je.pk)
            if je.reference_type == 'expense' and not Expense.objects.filter(id=je.reference_id).exists():
                orphan_ids.append(je.pk)
        deleted, _ = JournalEntry.objects.filter(id__in=orphan_ids).delete()
        self.stdout.write(self.style.WARNING(f"تم حذف {deleted} قيد يومية يتيم"))

        # 1-b) حذف كشوف الشركاء اليتيمة
        pa_deleted, _ = PartnerAccount.objects.filter(
            revenue_id__isnull=False
        ).exclude(revenue_id__in=DailyRevenue.objects.values_list('id', flat=True)).delete()
        pb_deleted, _ = PartnerAccount.objects.filter(
            expense_id__isnull=False
        ).exclude(expense_id__in=Expense.objects.values_list('id', flat=True)).delete()
        self.stdout.write(self.style.WARNING(f"تم حذف {pa_deleted + pb_deleted} سجل شريك يتيم"))

        # 2) إعادة احتساب current_balance من قيود اليومية
        for acc in ChartOfAccounts.objects.all():
            sums = JournalEntryLine.objects.filter(account=acc, journal_entry__posted=True)\
                .aggregate(d=Sum('debit'), c=Sum('credit'))
            d = sums['d'] or Decimal('0')
            c = sums['c'] or Decimal('0')
            op = acc.opening_balance or Decimal('0')
            if acc.balance_type == 'debit':
                acc.current_balance = op + d - c
            else:
                acc.current_balance = op + c - d
            acc.save(update_fields=['current_balance'])
        self.stdout.write(self.style.SUCCESS('تمت إعادة احتساب أرصدة الحسابات.'))

        # 3) إعادة احتساب أرصدة الخزائن من TreasuryTransaction
        # المعاملات التي تزيد الرصيد تشمل عكس المصروف
        type_increase = {'revenue', 'partner_payment', 'bank_withdrawal', 'exchange_in', 'expense_reversal'}
        for t in Treasury.objects.all():
            balance = Decimal('0')
            for tx in TreasuryTransaction.objects.filter(treasury=t):
                if tx.transaction_type in type_increase:
                    balance += tx.amount
                else:
                    balance -= tx.amount
            t.balance = balance
            t.save(update_fields=['balance'])
        self.stdout.write(self.style.SUCCESS('تمت إعادة احتساب أرصدة الخزائن.'))

        # 4) إعادة احتساب أرصدة البنوك من BankTransaction
        type_in = {'deposit', 'transfer_in', 'interest'}
        for b in BankAccount.objects.all():
            balance = b.opening_balance or Decimal('0')
            for tx in BankTransaction.objects.filter(bank_account=b):
                if tx.transaction_type in type_in:
                    balance += tx.amount
                else:
                    balance -= tx.amount
            b.current_balance = balance
            b.save(update_fields=['current_balance'])
        self.stdout.write(self.style.SUCCESS('تمت إعادة احتساب أرصدة البنوك.'))

        self.stdout.write(self.style.SUCCESS('تم الانتهاء بنجاح.'))

