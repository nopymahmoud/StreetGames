from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from .models import Partnership, PartnerAccount, PartnerPayment
from .forms import (PartnershipForm, PartnerPaymentForm, PartnershipFilterForm,
                   PartnerAccountFilterForm, PartnerPaymentFilterForm)
from core.decorators import role_required, manager_or_admin_required


@login_required
def partnerships_list(request):
    """قائمة الشراكات"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تصفية الشراكات
    partnerships = Partnership.objects.filter(zone__in=accessible_zones).select_related('zone', 'zone__hotel')

    # تطبيق الفلاتر
    filter_form = PartnershipFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('zone'):
            partnerships = partnerships.filter(zone=filter_form.cleaned_data['zone'])
        if filter_form.cleaned_data.get('partner_type'):
            partnerships = partnerships.filter(partner_type=filter_form.cleaned_data['partner_type'])
        if filter_form.cleaned_data.get('active'):
            active_filter = filter_form.cleaned_data['active'] == 'true'
            partnerships = partnerships.filter(active=active_filter)

    # ترتيب وتقسيم الصفحات
    partnerships = partnerships.order_by('zone__name', 'partner_name')
    paginator = Paginator(partnerships, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # حساب الإحصائيات
    total_partnerships = partnerships.count()
    active_partnerships = partnerships.filter(active=True).count()
    total_investment = partnerships.aggregate(total=Sum('investment_amount'))['total'] or 0

    # إضافة أرصدة الشركاء لكل شراكة
    for partnership in page_obj:
        partnership.balances = partnership.get_all_balances()

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_partnerships': total_partnerships,
        'active_partnerships': active_partnerships,
        'total_investment': total_investment,
    }
    return render(request, 'partnerships/partnerships_list.html', context)


@manager_or_admin_required
def partnership_create(request):
    """إضافة شراكة جديدة"""
    if request.method == 'POST':
        form = PartnershipForm(request.POST, user=request.user)
        if form.is_valid():
            partnership = form.save()
            messages.success(request, 'تم حفظ الشراكة بنجاح')
            return redirect('partnerships:partnerships_list')
    else:
        form = PartnershipForm(user=request.user)

    return render(request, 'partnerships/partnership_form.html', {'form': form, 'title': 'إضافة شراكة جديدة'})


@manager_or_admin_required
def partnership_edit(request, pk):
    """تعديل شراكة"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    partnership = get_object_or_404(Partnership, pk=pk, zone__in=accessible_zones)

    if request.method == 'POST':
        form = PartnershipForm(request.POST, instance=partnership, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الشراكة بنجاح')
            return redirect('partnerships:partnerships_list')
    else:
        form = PartnershipForm(instance=partnership, user=request.user)

    return render(request, 'partnerships/partnership_form.html', {'form': form, 'title': 'تعديل شراكة', 'partnership': partnership})


@login_required
def partner_accounts_list(request):
    """كشوف حسابات الشركاء"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تصفية كشوف الحسابات
    accounts = PartnerAccount.objects.filter(
        partnership__zone__in=accessible_zones
    ).select_related('partnership', 'partnership__zone', 'created_by')

    # تطبيق الفلاتر
    filter_form = PartnerAccountFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('partnership'):
            accounts = accounts.filter(partnership=filter_form.cleaned_data['partnership'])
        if filter_form.cleaned_data.get('transaction_type'):
            accounts = accounts.filter(transaction_type=filter_form.cleaned_data['transaction_type'])
        if filter_form.cleaned_data.get('date_from'):
            accounts = accounts.filter(transaction_date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            accounts = accounts.filter(transaction_date__lte=filter_form.cleaned_data['date_to'])

    # ترتيب وتقسيم الصفحات
    accounts = accounts.order_by('-transaction_date', '-created_at')
    paginator = Paginator(accounts, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # حساب الإجماليات حسب العملة
    currency_totals = accounts.values('currency').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
        net_balance=Sum('debit') - Sum('credit')
    ).order_by('currency')

    # الإجماليات العامة
    total_debit = accounts.aggregate(total=Sum('debit'))['total'] or 0
    total_credit = accounts.aggregate(total=Sum('credit'))['total'] or 0

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'currency_totals': currency_totals,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'net_balance': total_debit - total_credit,
        'total_count': accounts.count(),
    }
    return render(request, 'partnerships/partner_accounts_list.html', context)


@role_required(['admin', 'manager', 'accountant', 'cashier'])
def payments_list(request):
    """قائمة دفعات الشركاء"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تصفية المدفوعات
    payments = PartnerPayment.objects.filter(
        partnership__zone__in=accessible_zones
    ).select_related('partnership', 'partnership__zone', 'created_by')

    # تطبيق الفلاتر
    filter_form = PartnerPaymentFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('partnership'):
            payments = payments.filter(partnership=filter_form.cleaned_data['partnership'])
        if filter_form.cleaned_data.get('payment_method'):
            payments = payments.filter(payment_method=filter_form.cleaned_data['payment_method'])
        if filter_form.cleaned_data.get('date_from'):
            payments = payments.filter(payment_date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            payments = payments.filter(payment_date__lte=filter_form.cleaned_data['date_to'])

    # ترتيب وتقسيم الصفحات
    payments = payments.order_by('-payment_date', '-created_at')
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # حساب الإجماليات
    total_amount = payments.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_amount': total_amount,
        'total_count': payments.count(),
    }
    return render(request, 'partnerships/payments_list.html', context)


@role_required(['admin', 'manager', 'accountant', 'cashier'])
def payment_create(request):
    """إضافة دفعة جديدة"""
    if request.method == 'POST':
        form = PartnerPaymentForm(request.POST, user=request.user)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.created_by = request.user
            payment.save()
            messages.success(request, 'تم حفظ الدفعة بنجاح')
            return redirect('partnerships:payments_list')
    else:
        form = PartnerPaymentForm(user=request.user)

    return render(request, 'partnerships/payment_form.html', {'form': form, 'title': 'إضافة دفعة جديدة'})


@role_required(['admin', 'manager', 'accountant', 'cashier'])
def payment_edit(request, pk):
    """تعديل دفعة"""
    # التحقق من صلاحية الوصول للمنطقة
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    payment = get_object_or_404(PartnerPayment, pk=pk, partnership__zone__in=accessible_zones)

    if request.method == 'POST':
        form = PartnerPaymentForm(request.POST, instance=payment, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الدفعة بنجاح')
            return redirect('partnerships:payments_list')
    else:
        form = PartnerPaymentForm(instance=payment, user=request.user)

    return render(request, 'partnerships/payment_form.html', {'form': form, 'title': 'تعديل دفعة', 'payment': payment})
