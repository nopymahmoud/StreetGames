from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DailyRevenue, JournalEntry
from .expense_models import Expense


@receiver(post_delete, sender=DailyRevenue)
def delete_journal_on_revenue_delete(sender, instance: DailyRevenue, **kwargs):
    """عند حذف إيراد: احذف قيد اليومية المرتبط وأي سجلات شركاء مرتبطة."""
    try:
        if instance.journal_entry_id:
            JournalEntry.objects.filter(id=instance.journal_entry_id).delete()
    except Exception:
        pass
    # حذف قيود الشركاء المرتبطة إن وجدت
    try:
        from partnerships.models import PartnerAccount
        PartnerAccount.objects.filter(revenue_id=instance.id).delete()
    except Exception:
        # في حال عدم توفر تطبيق الشراكات
        pass


@receiver(post_delete, sender=Expense)
def delete_journal_on_expense_delete(sender, instance: Expense, **kwargs):
    """عند حذف مصروف: احذف قيد اليومية المرتبط وأي سجلات شركاء مرتبطة."""
    try:
        if instance.journal_entry_id:
            JournalEntry.objects.filter(id=instance.journal_entry_id).delete()
    except Exception:
        pass
    try:
        from partnerships.models import PartnerAccount
        PartnerAccount.objects.filter(expense_id=instance.id).delete()
    except Exception:
        pass

