from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import Hotel, GameZone, GameType, Warehouse


@login_required
def dashboard_stats_api(request):
    """API لإحصائيات لوحة التحكم"""
    try:
        # الحصول على المناطق المسموحة للمستخدم
        if hasattr(request.user, 'userprofile'):
            accessible_zones = request.user.userprofile.get_accessible_zones()
        else:
            # في حال عدم وجود ملف مستخدم، اعرض كل المناطق النشطة كافتراضي
            accessible_zones = GameZone.objects.filter(active=True)
        
        # إحصائيات أساسية
        stats = {
            'total_hotels': Hotel.objects.filter(active=True).count(),
            'total_zones': GameZone.objects.filter(active=True).count(),
            'total_game_types': GameType.objects.filter(active=True).count(),
            'total_warehouses': Warehouse.objects.filter(active=True).count(),
        }
        
        # إحصائيات الشراكات
        try:
            from partnerships.models import Partnership
            if hasattr(accessible_zones, 'exists') and accessible_zones.exists():
                stats['total_partnerships'] = Partnership.objects.filter(zone__in=accessible_zones, active=True).count()
            else:
                # لو المستخدم ليس له مناطق محددة، اعرض الإجمالي العام كي لا تبقى القيمة صفر
                stats['total_partnerships'] = Partnership.objects.filter(active=True).count()
        except ImportError:
            stats['total_partnerships'] = 0
        
        # إحصائيات مالية (بدعم فلتر شهر عبر ?month=YYYY-MM)
        month_str = request.GET.get('month')
        if month_str:
            try:
                current_month = datetime.strptime(month_str + '-01', '%Y-%m-%d').date().replace(day=1)
            except ValueError:
                current_month = timezone.now().date().replace(day=1)
        else:
            current_month = timezone.now().date().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)

        try:
            from accounting.models import DailyRevenue
            from accounting.expense_models import Expense

            # إجماليات الشهر الحالية الإجمالية
            monthly_revenue = DailyRevenue.objects.filter(
                zone__in=accessible_zones,
                date__gte=current_month,
                date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            monthly_expenses = Expense.objects.filter(
                zone__in=accessible_zones,
                date__gte=current_month,
                date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            # تفصيل حسب العملة
            rev_by_cur = list(
                DailyRevenue.objects.filter(
                    zone__in=accessible_zones,
                    date__gte=current_month,
                    date__lt=next_month
                ).values('currency').annotate(total=Sum('amount')).order_by('currency')
            )
            exp_by_cur = list(
                Expense.objects.filter(
                    zone__in=accessible_zones,
                    date__gte=current_month,
                    date__lt=next_month
                ).values('currency').annotate(total=Sum('amount')).order_by('currency')
            )
            rev_map = {r['currency']: (r['total'] or Decimal('0')) for r in rev_by_cur}
            exp_map = {e['currency']: (e['total'] or Decimal('0')) for e in exp_by_cur}
            currencies = sorted(set(rev_map.keys()) | set(exp_map.keys()))
            profit_by_currency = [
                {
                    'currency': cur,
                    'amount': float((rev_map.get(cur, Decimal('0')) - exp_map.get(cur, Decimal('0'))))
                }
                for cur in currencies
            ]

            stats['monthly_revenue'] = float(monthly_revenue)
            stats['monthly_expenses'] = float(monthly_expenses)
            stats['monthly_profit'] = float(monthly_revenue - monthly_expenses)
            stats['monthly_profit_by_currency'] = profit_by_currency
        except ImportError:
            stats.update({
                'monthly_revenue': 0,
                'monthly_expenses': 0,
                'monthly_profit': 0,
            })
        
        # إحصائيات الخزينة
        try:
            from treasury.models import Treasury, BankAccount
            
            treasury_balance = Treasury.objects.aggregate(
                total=Sum('balance')
            )['total'] or Decimal('0')

            # أرصدة الخزينة حسب العملة
            treasury_by_currency = list(
                Treasury.objects.values('currency').annotate(total=Sum('balance')).order_by('currency')
            )
            treasury_by_currency = [
                {'currency': t['currency'], 'amount': float(t['total'] or 0)} for t in treasury_by_currency
            ]

            bank_balance = BankAccount.objects.filter(active=True).aggregate(
                total=Sum('current_balance')
            )['total'] or Decimal('0')

            bank_by_currency = list(
                BankAccount.objects.filter(active=True).values('currency').annotate(total=Sum('current_balance')).order_by('currency')
            )
            bank_by_currency = [
                {'currency': b['currency'], 'amount': float(b['total'] or 0)} for b in bank_by_currency
            ]

            stats['treasury_balance'] = float(treasury_balance)
            stats['treasury_by_currency'] = treasury_by_currency
            stats['bank_balance'] = float(bank_balance)
            stats['bank_by_currency'] = bank_by_currency
            stats['total_cash'] = float(treasury_balance + bank_balance)
        except ImportError:
            stats.update({
                'treasury_balance': 0,
                'bank_balance': 0,
                'total_cash': 0,
            })
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def revenue_chart_api(request):
    """API لبيانات مخطط الإيرادات"""
    try:
        # الحصول على المناطق المسموحة للمستخدم
        if hasattr(request.user, 'userprofile'):
            accessible_zones = request.user.userprofile.get_accessible_zones()
        else:
            accessible_zones = GameZone.objects.filter(active=True)
        
        # الحصول على بيانات آخر 6 أشهر
        months_data = []
        current_date = timezone.now().replace(day=1)
        
        try:
            from accounting.models import DailyRevenue
            from accounting.expense_models import Expense
            
            for i in range(6):
                month_start = (current_date - timedelta(days=32*i)).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                
                revenue = DailyRevenue.objects.filter(
                    zone__in=accessible_zones,
                    date__gte=month_start,
                    date__lt=month_end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                expenses = Expense.objects.filter(
                    zone__in=accessible_zones,
                    date__gte=month_start,
                    date__lt=month_end
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                months_data.insert(0, {
                    'month': month_start.strftime('%Y-%m'),
                    'month_name': month_start.strftime('%B %Y'),
                    'revenue': float(revenue),
                    'expenses': float(expenses),
                    'profit': float(revenue - expenses)
                })
        except ImportError:
            # بيانات وهمية للاختبار
            months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو']
            for i, month in enumerate(months):
                months_data.append({
                    'month': f"2024-{i+1:02d}",
                    'month_name': month,
                    'revenue': 120000 + (i * 5000),
                    'expenses': 80000 + (i * 2000),
                    'profit': 40000 + (i * 3000)
                })
        
        return JsonResponse({'success': True, 'data': months_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def zone_revenue_distribution_api(request):
    """API لتوزيع الإيرادات حسب المنطقة"""
    try:
        # الحصول على المناطق المسموحة للمستخدم
        if hasattr(request.user, 'userprofile'):
            accessible_zones = request.user.userprofile.get_accessible_zones()
        else:
            accessible_zones = GameZone.objects.filter(active=True)
        
        # الحصول على إيرادات الشهر الحالي لكل منطقة (بدون خلط العملات)
        current_month = timezone.now().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)

        try:
            from accounting.models import DailyRevenue
            # نجمع حسب المنطقة والعملة معاً
            rows = (
                DailyRevenue.objects.filter(
                    zone__in=accessible_zones,
                    date__gte=current_month,
                    date__lt=next_month
                )
                .values('zone_id', 'zone__name', 'zone__code', 'currency')
                .annotate(total=Sum('amount'))
            )
            zones_dict = {}
            for r in rows:
                amt = r['total'] or Decimal('0')
                if amt <= 0:
                    continue
                zid = r['zone_id']
                if zid not in zones_dict:
                    zones_dict[zid] = {
                        'zone_name': r['zone__name'],
                        'zone_code': r['zone__code'],
                        'revenues': []
                    }
                zones_dict[zid]['revenues'].append({'currency': r['currency'], 'amount': float(amt)})
            zones_data = list(zones_dict.values())
            # نرتب حسب أكبر مبلغ داخل المنطقة (بدون جمع العملات)
            zones_data.sort(key=lambda z: max([rv['amount'] for rv in z['revenues']]) if z['revenues'] else 0, reverse=True)
            zones_data = zones_data[:5]
        except ImportError:
            # بيانات وهمية للاختبار
            zones_data = []

        return JsonResponse({'success': True, 'data': zones_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def recent_activities_api(request):
    """API لآخر الأنشطة"""
    try:
        # الحصول على المناطق المسموحة للمستخدم
        if hasattr(request.user, 'userprofile'):
            accessible_zones = request.user.userprofile.get_accessible_zones()
        else:
            accessible_zones = GameZone.objects.filter(active=True)
        
        activities = []
        
        try:
            from accounting.models import DailyRevenue
            from accounting.expense_models import Expense
            
            # آخر الإيرادات
            recent_revenues = DailyRevenue.objects.filter(
                zone__in=accessible_zones
            ).select_related('zone').order_by('-date', '-created_at')[:5]
            
            for revenue in recent_revenues:
                activities.append({
                    'type': 'revenue',
                    'date': revenue.date.strftime('%Y-%m-%d'),
                    'description': f"إيراد {revenue.zone.name}",
                    'amount': float(revenue.amount),
                    'currency': revenue.currency
                })
            
            # آخر المصروفات
            recent_expenses = Expense.objects.filter(
                zone__in=accessible_zones
            ).select_related('zone').order_by('-date', '-created_at')[:5]
            
            for expense in recent_expenses:
                activities.append({
                    'type': 'expense',
                    'date': expense.date.strftime('%Y-%m-%d'),
                    'description': f"مصروف {expense.get_category_display()} - {expense.zone.name}",
                    'amount': float(expense.amount),
                    'currency': expense.currency
                })
            
            # ترتيب الأنشطة حسب التاريخ
            activities.sort(key=lambda x: x['date'], reverse=True)
            activities = activities[:10]  # أحدث 10 أنشطة
            
        except ImportError:
            activities = []
        
        return JsonResponse({'success': True, 'data': activities})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
