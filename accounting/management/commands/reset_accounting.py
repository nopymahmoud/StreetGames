from django.core.management.base import BaseCommand
from decimal import Decimal

from accounting.models import ChartOfAccounts, JournalEntry, JournalEntryLine, DailyRevenue
from accounting.expense_models import Expense


class Command(BaseCommand):
    help = "تصغير الأرصدة للافتتاحية وتصفيـر أرصدة الحسابات والخزائن والبنوك وحذف كل الحركات/المعاملات التجريبية (خطير)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes-i-am-sure', action='store_true', dest='confirm',
            help='تأكيد تنفيذ العملية (سوف تصفر الأرصدة وتحذف السجلات)'
        )

    def handle(self, *args, **options):
        if not options.get('confirm'):
            self.stdout.write(self.style.ERROR(
                'هذه العملية ستقوم بتصفير كل الأرصدة وحذف معاملات الخزائن والبنوك وسجلات الشركاء. '
                'أعد التشغيل بهذا الخيار: --yes-i-am-sure'
            ))
            return

        # حذف كل قيود اليومية وخطوطها والإيرادات والمصروفات
        JournalEntryLine.objects.all().delete()
        JournalEntry.objects.all().delete()
        DailyRevenue.objects.all().delete()
        Expense.objects.all().delete()

        # تصفير أرصدة دليل الحسابات
        ChartOfAccounts.objects.all().update(opening_balance=Decimal('0'), current_balance=Decimal('0'))

        # تصفير الخزائن والبنوك وحذف معاملاتــها
        try:
            from treasury.models import Treasury, TreasuryTransaction, BankAccount, BankTransaction
            TreasuryTransaction.objects.all().delete()
            BankTransaction.objects.all().delete()
            Treasury.objects.all().update(balance=Decimal('0'))
            BankAccount.objects.all().update(opening_balance=Decimal('0'), current_balance=Decimal('0'))
        except Exception:
            pass

        # حذف سجلات الشركاء
        try:
            from partnerships.models import PartnerAccount
            PartnerAccount.objects.all().delete()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS('تم تصفير جميع الأرصدة وحذف السجلات.'))

