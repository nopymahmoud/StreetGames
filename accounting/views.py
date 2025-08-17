from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from django.core.management import call_command
from datetime import datetime, timedelta

from .models import ChartOfAccounts, JournalEntry, DailyRevenue
from .expense_models import Expense
from .forms import DailyRevenueForm, ExpenseForm, ChartOfAccountsForm, RevenueFilterForm, ExpenseFilterForm
from django.contrib.admin.views.decorators import staff_member_required
from core.decorators import accounting_access_required


@user_passes_test(lambda u: u.is_staff)
def rebuild_accounting_view(request):
    """زر سريع لتشغيل أمر إعادة بناء المحاسبة من الواجهة. للموظفين فقط."""
    if request.method != 'POST':
        return HttpResponseForbidden('طريقة غير مسموحة')
    call_command('rebuild_accounting')
    messages.success(request, 'تم تشغيل إعادة بناء المحاسبة بنجاح')
    return redirect('core:dashboard')


@accounting_access_required
def accounting_dashboard(request):
    """لوحة تحكم المحاسبة"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # إحصائيات الشهر الحالي (من القيود اليومية)
    current_month = timezone.now().replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)

    from accounting.models import JournalEntryLine

    rev_accounts = ChartOfAccounts.objects.filter(account_type='revenue', active=True)
    exp_accounts = ChartOfAccounts.objects.filter(account_type='expense', active=True)

    rev_qs = JournalEntryLine.objects.filter(
        account__in=rev_accounts,
        journal_entry__posted=True,
        journal_entry__entry_date__gte=current_month,
        journal_entry__entry_date__lt=next_month,
    )
    exp_qs = JournalEntryLine.objects.filter(
        account__in=exp_accounts,
        journal_entry__posted=True,
        journal_entry__entry_date__gte=current_month,
        journal_entry__entry_date__lt=next_month,
    )

    # الإيراد = صافي (الدائن - المدين) لحسابات الإيراد
    rev_agg = rev_qs.aggregate(d=Sum('debit'), c=Sum('credit'))
    monthly_revenue = (rev_agg['c'] or 0) - (rev_agg['d'] or 0)

    # المصروف = صافي (المدين - الدائن) لحسابات المصروف
    exp_agg = exp_qs.aggregate(d=Sum('debit'), c=Sum('credit'))
    monthly_expenses = (exp_agg['d'] or 0) - (exp_agg['c'] or 0)

    context = {
        'total_accounts': ChartOfAccounts.objects.filter(active=True).count(),
        'total_journal_entries': JournalEntry.objects.count(),
        'total_revenues': DailyRevenue.objects.filter(zone__in=accessible_zones).count(),
        'total_expenses': Expense.objects.filter(zone__in=accessible_zones).count(),
        'monthly_revenue': monthly_revenue,
        'monthly_expenses': monthly_expenses,
        'monthly_profit': monthly_revenue - monthly_expenses,
        'accessible_zones': accessible_zones,
    }
    return render(request, 'accounting/dashboard.html', context)


@accounting_access_required
def revenues_list(request):
    """قائمة الإيرادات"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تصفية الإيرادات
    revenues = DailyRevenue.objects.filter(zone__in=accessible_zones).select_related('zone', 'created_by')

    # تطبيق الفلاتر
    filter_form = RevenueFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('zone'):
            revenues = revenues.filter(zone=filter_form.cleaned_data['zone'])
        if filter_form.cleaned_data.get('date_from'):
            revenues = revenues.filter(date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            revenues = revenues.filter(date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('currency'):
            revenues = revenues.filter(currency=filter_form.cleaned_data['currency'])

    # ترتيب وتقسيم الصفحات
    revenues = revenues.order_by('-date', '-created_at')
    paginator = Paginator(revenues, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # حساب الإجماليات
    total_amount = revenues.aggregate(total=Sum('amount'))['total'] or 0

    # إجماليات حسب العملة (بعد تطبيق الفلاتر)
    currency_totals = list(
        revenues.values('currency').annotate(total_amount=Sum('amount')).order_by('currency')
    )

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_amount': total_amount,
        'total_count': revenues.count(),
        'currency_totals': currency_totals,
    }
    return render(request, 'accounting/revenues_list.html', context)


@accounting_access_required
def revenue_create(request):
    """إضافة إيراد جديد"""
    if request.method == 'POST':
        form = DailyRevenueForm(request.POST, user=request.user)
        if form.is_valid():
            revenue = form.save(commit=False)
            revenue.created_by = request.user
            revenue.save()
            messages.success(request, 'تم حفظ الإيراد بنجاح')
            return redirect('accounting:revenues_list')
    else:
        form = DailyRevenueForm(user=request.user)

    return render(request, 'accounting/revenue_form.html', {'form': form, 'title': 'إضافة إيراد جديد'})


@accounting_access_required
def revenue_edit(request, pk):
    """تعديل إيراد"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    revenue = get_object_or_404(DailyRevenue, pk=pk, zone__in=accessible_zones)

    if request.method == 'POST':
        form = DailyRevenueForm(request.POST, instance=revenue, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الإيراد بنجاح')
            return redirect('accounting:revenues_list')
    else:
        form = DailyRevenueForm(instance=revenue, user=request.user)

    return render(request, 'accounting/revenue_form.html', {'form': form, 'title': 'تعديل إيراد', 'revenue': revenue})


@accounting_access_required
def expenses_list(request):
    """قائمة المصروفات"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تصفية المصروفات
    expenses = Expense.objects.filter(zone__in=accessible_zones).select_related('zone', 'created_by')

    # تطبيق الفلاتر
    filter_form = ExpenseFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('zone'):
            expenses = expenses.filter(zone=filter_form.cleaned_data['zone'])
        if filter_form.cleaned_data.get('category'):
            expenses = expenses.filter(category=filter_form.cleaned_data['category'])
        if filter_form.cleaned_data.get('date_from'):
            expenses = expenses.filter(date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            expenses = expenses.filter(date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('currency'):
            expenses = expenses.filter(currency=filter_form.cleaned_data['currency'])

    # ترتيب وتقسيم الصفحات
    expenses = expenses.order_by('-date', '-created_at')
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # حساب الإجماليات
    total_amount = expenses.aggregate(total=Sum('amount'))['total'] or 0

    # إجماليات حسب العملة (بعد تطبيق الفلاتر)
    currency_totals = list(
        expenses.values('currency').annotate(total_amount=Sum('amount')).order_by('currency')
    )

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_amount': total_amount,
        'total_count': expenses.count(),
        'currency_totals': currency_totals,
    }
    return render(request, 'accounting/expenses_list.html', context)

@staff_member_required
def accounts_list(request):
    accounts = ChartOfAccounts.objects.all().order_by('account_code')
    return render(request, 'accounting/accounts_list.html', {'accounts': accounts, 'title': 'دليل الحسابات'})

@staff_member_required
def account_create(request):
    if request.method == 'POST':
        form = ChartOfAccountsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الحساب بنجاح')
            return redirect('accounting:accounts_list')
    else:
        form = ChartOfAccountsForm()
    return render(request, 'accounting/account_form.html', {'form': form, 'title': 'إضافة حساب جديد'})

@staff_member_required
def account_edit(request, pk):
    account = get_object_or_404(ChartOfAccounts, pk=pk)
    if request.method == 'POST':
        form = ChartOfAccountsForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الحساب بنجاح')
            return redirect('accounting:accounts_list')
    else:
        form = ChartOfAccountsForm(instance=account)
    return render(request, 'accounting/account_form.html', {'form': form, 'title': 'تعديل حساب', 'account': account})



@accounting_access_required
def expense_create(request):
    """إضافة مصروف جديد"""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            messages.success(request, 'تم حفظ المصروف بنجاح')
            return redirect('accounting:expenses_list')
    else:
        form = ExpenseForm(user=request.user)

    return render(request, 'accounting/expense_form.html', {'form': form, 'title': 'إضافة مصروف جديد'})


@accounting_access_required
def expense_edit(request, pk):
    """تعديل مصروف"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    expense = get_object_or_404(Expense, pk=pk, zone__in=accessible_zones)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث المصروف بنجاح')
            return redirect('accounting:expenses_list')
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    return render(request, 'accounting/expense_form.html', {'form': form, 'title': 'تعديل مصروف', 'expense': expense})



@accounting_access_required
def revenue_delete(request, pk):
    """حذف إيراد"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    revenue = get_object_or_404(DailyRevenue, pk=pk, zone__in=accessible_zones)

    if request.method == 'POST':
        # عكس أثر الإيراد على الخزينة قبل الحذف
        from treasury.models import update_treasury_balance
        update_treasury_balance(revenue.currency, revenue.amount, transaction_type='revenue_reversal',
                                description=f'عكس إيراد عند الحذف - {revenue.zone.name if revenue.zone else ""}',
                                user=request.user, reference_id=revenue.id)
        revenue.delete()
        messages.success(request, 'تم حذف الإيراد بنجاح وعكس أثره في الخزينة')
        return redirect('accounting:revenues_list')
    return HttpResponseForbidden('Invalid request')


@accounting_access_required
def expense_delete(request, pk):
    """حذف مصروف"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    expense = get_object_or_404(Expense, pk=pk, zone__in=accessible_zones)

    if request.method == 'POST':
        # عكس أثر المصروف على الخزينة قبل الحذف
        from treasury.models import update_treasury_balance
        update_treasury_balance(expense.currency, expense.amount, transaction_type='expense_reversal',
                                description=f'عكس مصروف عند الحذف - {expense.description}',
                                user=request.user, reference_id=expense.id)
        expense.delete()
        messages.success(request, 'تم حذف المصروف بنجاح وعكس أثره في الخزينة')
        return redirect('accounting:expenses_list')
    return HttpResponseForbidden('Invalid request')
