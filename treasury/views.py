from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Count
from django.http import JsonResponse
from decimal import Decimal

from .models import BankAccount, Treasury, TreasuryTransaction, BankTransaction
from core.decorators import role_required


@role_required(['admin', 'manager', 'accountant', 'cashier'])
def treasury_dashboard(request):
    """لوحة تحكم الخزينة والبنوك"""

    # أرصدة الخزائن حسب العملة
    treasuries = Treasury.objects.all().order_by('currency')

    # أرصدة البنوك حسب العملة
    bank_balances = BankAccount.objects.filter(active=True).values('currency').annotate(
        total_balance=Sum('current_balance'),
        account_count=Count('id')
    ).order_by('currency')

    # آخر المعاملات
    recent_transactions = TreasuryTransaction.objects.select_related(
        'treasury', 'bank_account', 'created_by'
    ).order_by('-transaction_date')[:10]

    context = {
        'treasuries': treasuries,
        'bank_balances': bank_balances,
        'recent_transactions': recent_transactions,
    }

    return render(request, 'treasury/dashboard.html', context)


@role_required(['admin', 'manager', 'accountant', 'cashier'])
def treasury_dashboard_old(request):
    """لوحة تحكم الخزينة"""
    context = {
        'bank_accounts': BankAccount.objects.filter(active=True),
        'treasuries': Treasury.objects.all(),
        'total_transactions': TreasuryTransaction.objects.count(),
        'total_bank_transactions': BankTransaction.objects.count(),
    }
    return render(request, 'treasury/dashboard.html', context)
