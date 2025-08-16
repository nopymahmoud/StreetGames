from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import csv

# Optional PDF engines
try:
    from weasyprint import HTML  # type: ignore
except Exception:
    HTML = None  # type: ignore
try:
    from xhtml2pdf import pisa  # type: ignore
except Exception:
    pisa = None  # type: ignore

from .models import ChartOfAccounts, JournalEntry, JournalEntryLine, DailyRevenue
from .expense_models import Expense
from partnerships.models import Partnership, PartnerAccount
from core.decorators import accounting_access_required


def _account_balance_as_of(account, as_of_date=None, currency: str | None = None):
    """حساب رصيد الحساب حتى تاريخ معين اعتماداً على قيود اليومية + الرصيد الافتتاحي.
    - إذا تم تحديد العملة: يتم جمع قيود اليومية بتلك العملة فقط،
      كما لا يُحتسب الرصيد الافتتاحي إلا إذا كانت عملة الحساب تطابق العملة المحددة.
    - النتيجة تكون باتجاه طبيعة الحساب (debit/credit) كقيمة موجبة.
    """
    qs = JournalEntryLine.objects.filter(account=account, journal_entry__posted=True)
    if as_of_date:
        qs = qs.filter(journal_entry__entry_date__lte=as_of_date)
    if currency:
        qs = qs.filter(currency=currency)
    sums = qs.aggregate(total_debit=Sum('debit'), total_credit=Sum('credit'))
    total_debit = sums['total_debit'] or Decimal('0')
    total_credit = sums['total_credit'] or Decimal('0')

    opening = account.opening_balance or Decimal('0')
    if currency and account.currency != currency:
        opening = Decimal('0')

    if account.balance_type == 'debit':
        balance = opening + total_debit - total_credit
    else:
        balance = opening + total_credit - total_debit
    return balance


# تحويل الرصيد إلى عملة تقديم باستخدام أسعار الصرف
try:
    from .exchange_models import convert_amount, DEFAULT_PRESENTATION_CURRENCY
except Exception:
    convert_amount = None
    DEFAULT_PRESENTATION_CURRENCY = "EGP"


def _account_balance_in_presentation(account, as_of_date, presentation_currency: str):
    """احسب أرصدة الحساب (مدين/دائن) محوّلة إلى عملة تقديم باستخدام سعر إقفال التاريخ.
    تبسيط: نجمع رصيد كل عملة ونحوّلها بالـ closing في تاريخ التقرير.
    """
    from decimal import Decimal
    if convert_amount is None:
        return Decimal("0"), Decimal("0")

    # نجمع حسب العملة
    qs = JournalEntryLine.objects.filter(account=account, journal_entry__posted=True)
    if as_of_date:
        qs = qs.filter(journal_entry__entry_date__lte=as_of_date)
    rows = qs.values("currency").annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))

    debit_total = Decimal("0")
    credit_total = Decimal("0")

    for r in rows:
        cur = r["currency"] or account.currency or "EGP"
        total_debit = r["total_debit"] or Decimal("0")
        total_credit = r["total_credit"] or Decimal("0")
        # أضف الرصيد الافتتاحي لعملة الحساب فقط
        opening = account.opening_balance or Decimal("0")
        opening_for_cur = opening if (getattr(account, "currency", None) or "EGP") == cur else Decimal("0")

        if account.balance_type == "debit":
            bal = opening_for_cur + total_debit - total_credit
        else:
            bal = opening_for_cur + total_credit - total_debit

        if bal == 0:
            continue

        conv = convert_amount(abs(bal), cur, presentation_currency, as_of_date, rate_type="closing")
        if conv is None:
            continue
        if account.balance_type == "debit":
            if bal > 0:
                debit_total += conv
            else:
                credit_total += conv
        else:
            if bal > 0:
                credit_total += conv
            else:
                debit_total += conv

    return debit_total, credit_total


def _account_net_in_presentation(account, as_of_date, presentation_currency: str):
    """رصيد صافي بعملة التقديم (debit-positive for debit-type accounts)."""
    d, c = _account_balance_in_presentation(account, as_of_date, presentation_currency)
    if account.balance_type == 'debit':
        return d - c
    return c - d


# === FX diagnostics ===
try:
    from .exchange_models import ExchangeRate
except Exception:
    ExchangeRate = None


def _fx_availability_for_date(as_of_date, rate_type: str = 'closing'):
    """ارجع العملات المستخدمة وأسعارها المتاحة/الناقصة حتى تاريخ معين."""
    from accounting.models import JournalEntryLine
    used_currencies = set(
        JournalEntryLine.objects.filter(
            journal_entry__posted=True,
            journal_entry__entry_date__lte=as_of_date,
        ).values_list('currency', flat=True)
    )
    used_currencies.discard(None)
    used_currencies.discard('')
    used_currencies.discard(DEFAULT_PRESENTATION_CURRENCY)

    available = set()
    missing = set()
    if ExchangeRate:
        for cur in used_currencies:
            exists = ExchangeRate.objects.filter(
                currency=cur,
                rate_type=rate_type,
                rate_date__lte=as_of_date,
            ).exists()
            (available if exists else missing).add(cur)
    return {
        'used': sorted([x for x in used_currencies]),
        'available': sorted([x for x in available]),
        'missing': sorted([x for x in missing]),
        'rate_type': rate_type,
        'date': as_of_date,
    }



@accounting_access_required
def reports_dashboard(request):
    """لوحة تحكم التقارير"""
    context = {
        'title': 'التقارير المحاسبية',
    }
    return render(request, 'accounting/reports_dashboard.html', context)


@accounting_access_required
def balance_sheet(request):
    """الميزانية العمومية"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # تاريخ التقرير (افتراضياً نهاية الشهر الحالي)
    report_date = request.GET.get('date')
    if report_date:
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    else:
        report_date = timezone.now().date()

    # الأصول
    assets = ChartOfAccounts.objects.filter(
        account_type='asset',
        active=True
    ).order_by('account_code')

    # الخصوم
    liabilities = ChartOfAccounts.objects.filter(
        account_type='liability',
        active=True
    ).order_by('account_code')

    # حقوق الملكية
    equity = ChartOfAccounts.objects.filter(
        account_type='equity',
        active=True
    ).order_by('account_code')

    # نمط العرض: أصلي أو محوّل لعملة تقديم
    mode = request.GET.get('mode') or 'presentation'

    # حساب الأرصدة حتى تاريخ التقرير
    for acc in list(assets) + list(liabilities) + list(equity):
        if mode == 'presentation' and convert_amount:
            # تحويل كل العملات إلى عملة تقديم (سعر إقفال) — يمكن جمعها بأمان
            val = _account_net_in_presentation(acc, report_date, DEFAULT_PRESENTATION_CURRENCY)
        else:
            # الوضع الافتراضي: لا ندمج عملات مختلفة، نحسب فقط برمز عملة الحساب
            acc_currency = getattr(acc, 'currency', None)
            val = _account_balance_as_of(acc, report_date, currency=acc_currency)
        setattr(acc, 'computed_balance', val)

    # حساب الإجماليات من computed_balance
    total_assets = sum((getattr(a, 'computed_balance', Decimal('0')) or Decimal('0') for a in assets), Decimal('0'))
    total_liabilities = sum((getattr(l, 'computed_balance', Decimal('0')) or Decimal('0') for l in liabilities), Decimal('0'))
    total_equity = sum((getattr(e, 'computed_balance', Decimal('0')) or Decimal('0') for e in equity), Decimal('0'))

    # حساب صافي الدخل للفترة حسب العملة
    current_month = report_date.replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)

    # صافي الدخل والإجماليات حسب العملة من القيود اليومية
    from accounting.models import JournalEntryLine

    rev_accounts = ChartOfAccounts.objects.filter(account_type='revenue', active=True)
    exp_accounts = ChartOfAccounts.objects.filter(account_type='expense', active=True)

    rev_qs = JournalEntryLine.objects.filter(
        account__in=rev_accounts,
        journal_entry__posted=True,
        journal_entry__entry_date__gte=current_month,
        journal_entry__entry_date__lt=next_month,
    ).values('currency').annotate(total_credit=Sum('credit'), total_debit=Sum('debit'))

    exp_qs = JournalEntryLine.objects.filter(
        account__in=exp_accounts,
        journal_entry__posted=True,
        journal_entry__entry_date__gte=current_month,
        journal_entry__entry_date__lt=next_month,
    ).values('currency').annotate(total_credit=Sum('credit'), total_debit=Sum('debit'))

    # تحويل إلى قواميس للعمل بسهولة
    rev_totals = {r['currency']: (r['total_credit'] or Decimal('0')) - (r['total_debit'] or Decimal('0')) for r in rev_qs}
    exp_totals = {e['currency']: (e['total_debit'] or Decimal('0')) - (e['total_credit'] or Decimal('0')) for e in exp_qs}

    all_currencies = set(rev_totals.keys()) | set(exp_totals.keys())
    net_income_by_currency = {cur: (rev_totals.get(cur, Decimal('0')) - exp_totals.get(cur, Decimal('0'))) for cur in all_currencies}

    # تجهيز قوائم إجمالي الإيرادات/المصروفات حسب العملة للتوافق مع الواجهة
    monthly_revenue_by_currency = [{'currency': cur, 'total': rev_totals.get(cur, Decimal('0'))} for cur in sorted(rev_totals.keys())]
    monthly_expenses_by_currency = [{'currency': cur, 'total': exp_totals.get(cur, Decimal('0'))} for cur in sorted(exp_totals.keys())]

    context = {
        'report_date': report_date,
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'monthly_revenue_by_currency': monthly_revenue_by_currency,
        'monthly_expenses_by_currency': monthly_expenses_by_currency,
        'net_income_by_currency': net_income_by_currency,
        'all_currencies': sorted(all_currencies),
    }
    # Export handling
    export_format = request.GET.get('export')
    if export_format == 'excel':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="balance_sheet_{report_date}.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel
        writer = csv.writer(response)
        writer.writerow(['Section', 'Account Code', 'Account Name', 'Balance'])
        for acc in assets:
            writer.writerow(['Assets', acc.account_code, acc.account_name, f"{getattr(acc, 'computed_balance', Decimal('0'))}"])
        for acc in liabilities:
            writer.writerow(['Liabilities', acc.account_code, acc.account_name, f"{getattr(acc, 'computed_balance', Decimal('0'))}"])
        for acc in equity:
            writer.writerow(['Equity', acc.account_code, acc.account_name, f"{getattr(acc, 'computed_balance', Decimal('0'))}"])
        writer.writerow([])
        writer.writerow(['Total Assets', '', '', f"{total_assets}"])
        writer.writerow(['Total Liabilities', '', '', f"{total_liabilities}"])
        writer.writerow(['Total Equity', '', '', f"{total_equity}"])
        return response
    elif export_format == 'pdf':
        html = render(request, 'accounting/balance_sheet.html', context).content.decode('utf-8')
        if HTML is not None:
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="balance_sheet_{report_date}.pdf"'
            return response
        elif pisa is not None:
            from io import BytesIO
            result = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=result, encoding='utf-8')
            if pisa_status.err:
                return HttpResponse('Failed to generate PDF (xhtml2pdf error).', status=500)
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="balance_sheet_{report_date}.pdf"'
            return response
        else:
            return HttpResponse('No PDF engine available. Please install WeasyPrint dependencies or allow installing xhtml2pdf.', content_type='text/plain')

    return render(request, 'accounting/balance_sheet.html', context)


@accounting_access_required
def income_statement(request):
    """قائمة الدخل"""
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # فترة التقرير
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if date_from and date_to:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        # افتراضياً الشهر الحالي
        date_from = timezone.now().replace(day=1).date()
        date_to = (date_from + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    # نجلب البيانات مباشرة من نماذج الإيرادات والمصروفات لتفادي اعتماد القيد على وجود حسابات
    from accounting.models import DailyRevenue
    from accounting.expense_models import Expense

    rev_qs = DailyRevenue.objects.filter(
        zone__in=accessible_zones,
        date__gte=date_from,
        date__lte=date_to,
    )
    exp_qs = Expense.objects.filter(
        zone__in=accessible_zones,
        date__gte=date_from,
        date__lte=date_to,
    )

    # إجمالي الإيرادات والمصروفات حسب العملة (أصلية)
    total_revenue_by_currency = list(
        rev_qs.values('currency').annotate(total=Sum('amount')).order_by('currency')
    )
    total_expenses_by_currency = list(
        exp_qs.values('currency').annotate(total=Sum('amount')).order_by('currency')
    )

    # تفاصيل حسب المنطقة/التصنيف لاستخدامها في الجدول عند الحاجة
    revenues_by_currency = list(
        rev_qs.values('currency', 'zone__name').annotate(total_amount=Sum('amount')).order_by('currency', 'zone__name')
    )
    expenses_by_currency = list(
        exp_qs.values('currency', 'category').annotate(total_amount=Sum('amount')).order_by('currency', 'category')
    )

    # تحويل إلى قاموس صافي لكل عملة
    revenue_net = {r['currency']: (r['total'] or Decimal('0')) for r in total_revenue_by_currency}
    expense_net = {e['currency']: (e['total'] or Decimal('0')) for e in total_expenses_by_currency}

    all_currencies = set(revenue_net.keys()) | set(expense_net.keys())
    net_income_by_currency = {cur: (revenue_net.get(cur, Decimal('0')) - expense_net.get(cur, Decimal('0'))) for cur in all_currencies}

    # نمط العرض: presentation أو multi (تحويل لعملة تقديم باستخدام معدل Average الشهري)
    mode = request.GET.get('mode') or 'by_currency'
    presentation_currency = DEFAULT_PRESENTATION_CURRENCY
    converted_totals = None
    if mode in ('presentation', 'multi') and convert_amount:
        # نستخدم متوسط الشهر: نحدد تاريخ وسيط = آخر يوم في الفترة للتحويل
        pivot_date = date_to
        def convert_total(value_map: dict[str, Decimal]):
            total = Decimal('0')
            for cur, val in value_map.items():
                conv = convert_amount(val, cur, presentation_currency, pivot_date, rate_type='average') if convert_amount else None
                if conv is not None:
                    total += conv
            return total
        converted_totals = {
            'revenue': convert_total(revenue_net),
            'expenses': convert_total(expense_net),
        }

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue_by_currency': total_revenue_by_currency,
        'total_expenses_by_currency': total_expenses_by_currency,
        'revenues_by_currency': revenues_by_currency,
        'expenses_by_currency': expenses_by_currency,
        'net_income_by_currency': net_income_by_currency,
        'all_currencies': sorted(all_currencies),
        'mode': mode,
        'presentation_currency': presentation_currency,
        'converted_totals': converted_totals,
        'accessible_zones': accessible_zones,
    }
    # Export handling
    export_format = request.GET.get('export')
    if export_format == 'excel':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="income_statement_{date_from}_{date_to}.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel
        writer = csv.writer(response)
        writer.writerow(['Currency', 'Total Revenue', 'Total Expenses', 'Net Income'])
        for cur in sorted(all_currencies):
            rev = revenue_net.get(cur, Decimal('0'))
            exp = expense_net.get(cur, Decimal('0'))
            net = net_income_by_currency.get(cur, Decimal('0'))
            writer.writerow([cur, f"{rev}", f"{exp}", f"{net}"])
        return response
    elif export_format == 'pdf':
        html = render(request, 'accounting/income_statement.html', context).content.decode('utf-8')
        if HTML is not None:
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="income_statement_{date_from}_{date_to}.pdf"'
            return response
        elif pisa is not None:
            from io import BytesIO
            result = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=result, encoding='utf-8')
            if pisa_status.err:
                return HttpResponse('Failed to generate PDF (xhtml2pdf error).', status=500)
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="income_statement_{date_from}_{date_to}.pdf"'
            return response
        else:
            return HttpResponse('No PDF engine available. Please install WeasyPrint dependencies or allow installing xhtml2pdf.', content_type='text/plain')

    return render(request, 'accounting/income_statement.html', context)


@accounting_access_required
def trial_balance(request):
    """ميزان المراجعة"""
    # تاريخ التقرير
    report_date = request.GET.get('as_of_date') or request.GET.get('date')
    if report_date:
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    else:
        report_date = timezone.now().date()

    # فلترة عملة اختيارية + نمط عرض تقديمي
    currency_param = request.GET.get('currency') or None
    presentation = None
    selected_currency = None
    if currency_param:
        if currency_param.startswith('PRES-'):
            presentation = currency_param
        else:
            selected_currency = currency_param

    # جميع الحسابات النشطة
    accounts = ChartOfAccounts.objects.filter(active=True).order_by('account_code')

    # حساب الأرصدة لكل حساب حتى تاريخ التقرير
    trial_balance_data = []  # وضع الجدول الأحادي (عملة محددة أو تحويل تقديم)
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    # دعم عرض متعدد العملات: عندما لا يتم تحديد عملة ولا تحويل تقديم
    multi_currency_blocks = {}  # {cur: {'rows':[], 'total_debit':D, 'total_credit':C}}

    for account in accounts:
        if selected_currency is None and presentation is None:
            # لكل حساب، جهّز قائمة العملات المستخدمة حتى تاريخ التقرير
            qs = JournalEntryLine.objects.filter(account=account, journal_entry__posted=True)
            qs = qs.filter(journal_entry__entry_date__lte=report_date)
            currencies = set(qs.values_list('currency', flat=True))
            # أضف عملة الرصيد الافتتاحي إن لزم
            if (account.opening_balance or Decimal('0')) != 0:
                currencies.add(getattr(account, 'currency', None) or 'EGP')
            # نظف الفارغات
            currencies.discard(None)
            currencies.discard('')

            for cur in currencies or {getattr(account, 'currency', None) or 'EGP'}:
                bal = _account_balance_as_of(account, report_date, cur)
                if account.balance_type == 'debit':
                    d = bal if bal > 0 else Decimal('0')
                    c = abs(bal) if bal < 0 else Decimal('0')
                else:
                    c = bal if bal > 0 else Decimal('0')
                    d = abs(bal) if bal < 0 else Decimal('0')
                if d > 0 or c > 0:
                    block = multi_currency_blocks.setdefault(cur, {'rows': [], 'total_debit': Decimal('0'), 'total_credit': Decimal('0')})
                    block['rows'].append({'account': account, 'debit_balance': d, 'credit_balance': c})
                    block['total_debit'] += d
                    block['total_credit'] += c
        else:
            # وضع عملة مفردة أو تقديم
            balance = _account_balance_as_of(account, report_date, selected_currency)
            if account.balance_type == 'debit':
                debit_balance = balance if balance > 0 else Decimal('0')
                credit_balance = abs(balance) if balance < 0 else Decimal('0')
            else:
                credit_balance = balance if balance > 0 else Decimal('0')
                debit_balance = abs(balance) if balance < 0 else Decimal('0')

            if debit_balance > 0 or credit_balance > 0:
                trial_balance_data.append({
                    'account': account,
                    'debit_balance': debit_balance,
                    'credit_balance': credit_balance,
                })
                total_debit += debit_balance
                total_credit += credit_balance

    # دعم عرض محوّل إلى عملة تقديم
    if presentation and convert_amount:
        pres_cur = presentation.split('-', 1)[1] or DEFAULT_PRESENTATION_CURRENCY
        tb_presentation = []
        p_total_debit = Decimal('0')
        p_total_credit = Decimal('0')
        for row in trial_balance_data:
            acc = row['account']
            d_conv, c_conv = _account_balance_in_presentation(acc, report_date, pres_cur)
            if d_conv > 0 or c_conv > 0:
                tb_presentation.append({
                    'account': acc,
                    'debit_balance': d_conv,
                    'credit_balance': c_conv,
                })
                p_total_debit += d_conv
                p_total_credit += c_conv
        trial_balance_data = tb_presentation
        total_debit = p_total_debit
        total_credit = p_total_credit

    context = {
        'report_date': report_date,
        'today': timezone.now().date(),
        'trial_balance_data': trial_balance_data,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'balance_difference': total_debit - total_credit,
    }
    # Export handling
    export_format = request.GET.get('export')
    if export_format == 'excel':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="trial_balance_{report_date}.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel
        writer = csv.writer(response)
        writer.writerow(['Account Code', 'Account Name', 'Debit', 'Credit', 'Balance'])
        for row in trial_balance_data:
            acc = row['account']
            d = row['debit_balance']
            c = row['credit_balance']
            bal = (d - c) if acc.balance_type == 'debit' else (c - d)
            writer.writerow([acc.account_code, acc.account_name, f"{d}", f"{c}", f"{bal}"])
        writer.writerow([])
        writer.writerow(['Totals', '', f"{total_debit}", f"{total_credit}", f"{total_debit - total_credit}"])
        return response
    elif export_format == 'pdf':
        html = render(request, 'accounting/trial_balance.html', context).content.decode('utf-8')
        if HTML is not None:
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="trial_balance_{report_date}.pdf"'
            return response
        elif pisa is not None:
            from io import BytesIO
            result = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=result, encoding='utf-8')
            if pisa_status.err:
                return HttpResponse('Failed to generate PDF (xhtml2pdf error).', status=500)
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="trial_balance_{report_date}.pdf"'
            return response
        else:
            return HttpResponse('No PDF engine available. Please install WeasyPrint dependencies or allow installing xhtml2pdf.', content_type='text/plain')

    return render(request, 'accounting/trial_balance.html', context)


@accounting_access_required
def partner_statements(request):
    """كشوف حسابات الشركاء (حسب العملة) — توافق كامل مع القالب.
    - باراميتر الشريك في الواجهة اسمه partner وليس partner_id.
    - نجمع الرصيد الافتتاحي والحركة خلال الفترة لكل شراكة ولكل عملة.
    """
    # الحصول على المناطق المسموحة للمستخدم
    if hasattr(request.user, 'userprofile'):
        accessible_zones = request.user.userprofile.get_accessible_zones()
    else:
        accessible_zones = []

    # فترة التقرير
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    partner_id = request.GET.get('partner')  # يتوافق مع اسم الحقل في القالب

    if date_from_str and date_to_str:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    else:
        # افتراضياً الشهر الحالي
        date_from = timezone.now().replace(day=1).date()
        date_to = (date_from + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    # الشراكات المتاحة
    partnerships = Partnership.objects.filter(
        zone__in=accessible_zones,
        active=True
    ).select_related('zone').order_by('zone__name', 'partner_name')

    # إذا تم تحديد شريك، قصّر القائمة عليه
    if partner_id:
        partnerships = partnerships.filter(id=partner_id)

    # تحضير النتائج بحسب العملة
    partner_statements_by_currency: dict[str, list] = {}
    summary_by_currency: dict[str, dict] = {}

    for partnership in partnerships:
        # افتتاحي قبل بداية الفترة مجمع حسب العملة
        opening_rows = (
            PartnerAccount.objects
            .filter(partnership=partnership, transaction_date__lt=date_from)
            .values('currency')
            .annotate(total_debit=Sum('debit'), total_credit=Sum('credit'))
        )
        opening_map = {
            r['currency'] or 'EGP': (r['total_debit'] or Decimal('0')) - (r['total_credit'] or Decimal('0'))
            for r in opening_rows
        }

        # حركة الفترة مجمّعة حسب العملة
        period_rows = (
            PartnerAccount.objects
            .filter(partnership=partnership, transaction_date__gte=date_from, transaction_date__lte=date_to)
            .values('currency')
            .annotate(total_debit=Sum('debit'), total_credit=Sum('credit'))
        )
        period_map = {
            r['currency'] or 'EGP': {
                'debit': r['total_debit'] or Decimal('0'),
                'credit': r['total_credit'] or Decimal('0'),
            }
            for r in period_rows
        }

        # جميع العملات التي ظهرت سواء في الافتتاحي أو الحركة
        currencies = set(opening_map.keys()) | set(period_map.keys())
        for cur in currencies:
            opening_balance = opening_map.get(cur, Decimal('0'))
            deb = period_map.get(cur, {}).get('debit', Decimal('0'))
            cred = period_map.get(cur, {}).get('credit', Decimal('0'))
            closing_balance = opening_balance + deb - cred

            # تخطّ السطور الفارغة تماماً
            if opening_balance == 0 and deb == 0 and cred == 0 and closing_balance == 0:
                continue

            partner_statements_by_currency.setdefault(cur, []).append({
                'partnership': partnership,
                'opening_balance': opening_balance,
                'total_debit': deb,
                'total_credit': cred,
                'closing_balance': closing_balance,
            })

            # ملخصات حسب العملة
            s = summary_by_currency.setdefault(cur, {'total_positive': Decimal('0'), 'total_negative': Decimal('0'), 'net_balance': Decimal('0')})
            if closing_balance > 0:
                s['total_positive'] += closing_balance
            elif closing_balance < 0:
                s['total_negative'] += abs(closing_balance)
            s['net_balance'] += closing_balance

    # Export handling
    export_format = request.GET.get('export')
    if export_format == 'excel':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="partner_statements_{date_from}_{date_to}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Currency', 'Total Positive', 'Total Negative', 'Net Balance'])
        for cur in sorted(summary_by_currency.keys()):
            s = summary_by_currency[cur]
            writer.writerow([cur, f"{s['total_positive']}", f"{s['total_negative']}", f"{s['net_balance']}"])
        return response
    elif export_format == 'pdf':
        ctx = {
            'date_from': date_from,
            'date_to': date_to,
            'partnerships': partnerships,
            'partner_statements_by_currency': partner_statements_by_currency,
            'summary_by_currency': summary_by_currency,
        }
        html = render(request, 'accounting/partner_statements.html', ctx).content.decode('utf-8')
        if HTML is not None:
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="partner_statements_{date_from}_{date_to}.pdf"'
            return response
        elif pisa is not None:
            from io import BytesIO
            result = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=result, encoding='utf-8')
            if pisa_status.err:
                return HttpResponse('Failed to generate PDF (xhtml2pdf error).', status=500)
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="partner_statements_{date_from}_{date_to}.pdf"'
            return response
        else:
            return HttpResponse('No PDF engine available. Please install WeasyPrint dependencies or allow installing xhtml2pdf.', content_type='text/plain')

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'partnerships': partnerships,
        'partner_statements_by_currency': partner_statements_by_currency,
        'summary_by_currency': summary_by_currency,
    }

    return render(request, 'accounting/partner_statements.html', context)
