from typing import Any, cast
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Hotel, GameZone, GameType, Warehouse, UserProfile
from django.contrib.auth.models import User
from .decorators import role_required, manager_or_admin_required


@login_required
def dashboard(request):
    """لوحة التحكم الرئيسية"""
    context: dict[str, Any] = {
        'total_hotels': Hotel.objects.filter(active=True).count(),
        'total_zones': GameZone.objects.filter(active=True).count(),
        'total_game_types': GameType.objects.filter(active=True).count(),
        'total_warehouses': Warehouse.objects.filter(active=True).count(),
    }

    # إحصائيات إضافية
    try:
        from partnerships.models import Partnership
        context['total_partnerships'] = Partnership.objects.filter(active=True).count()
    except ImportError:
        context['total_partnerships'] = 0

    try:
        from accounting.models import DailyRevenue
        from accounting.expense_models import Expense
        from treasury.models import Treasury
        from partnerships.models import PartnerAccount

        # فلتر شهر محدد من المستخدم (YYYY-MM)
        month_str = request.GET.get('month')
        if month_str:
            try:
                month_start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date().replace(day=1)
            except ValueError:
                month_start = timezone.now().date().replace(day=1)
        else:
            month_start = timezone.now().date().replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        context['selected_month_str'] = month_start.strftime('%Y-%m')

        # الإيرادات الشهرية حسب العملة (من سجلات DailyRevenue مباشرة)
        revenue_qs = (
            DailyRevenue.objects.filter(
                date__gte=month_start,
                date__lt=next_month,
                zone__in=UserProfile.objects.get(user=request.user).get_accessible_zones() if hasattr(request.user, 'userprofile') else GameZone.objects.filter(active=True)
            )
            .values('currency')
            .annotate(total=Sum('amount'))
            .order_by('currency')
        )
        monthly_revenue_by_currency = [
            {'currency': r['currency'], 'total': r['total'] or 0}
            for r in revenue_qs
        ]

        # المصروفات الشهرية حسب العملة (من جدول Expense مباشرة)
        expense_qs = (
            Expense.objects.filter(
                date__gte=month_start,
                date__lt=next_month,
                zone__in=UserProfile.objects.get(user=request.user).get_accessible_zones() if hasattr(request.user, 'userprofile') else GameZone.objects.filter(active=True)
            )
            .values('currency')
            .annotate(total=Sum('amount'))
            .order_by('currency')
        )
        monthly_expenses_by_currency = [
            {'currency': e['currency'], 'total': e['total'] or 0}
            for e in expense_qs
        ]

        # أرصدة الخزائن (مباشرة)
        treasury_balances = Treasury.objects.all().order_by('currency')

        # أرصدة الشركاء حسب العملة
        partner_balances_by_currency = PartnerAccount.objects.values('currency').annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
            net_balance=Sum('debit') - Sum('credit')
        ).order_by('currency')

        context.update({
            'monthly_revenue_by_currency': monthly_revenue_by_currency,
            'monthly_expenses_by_currency': monthly_expenses_by_currency,
            'treasury_balances': treasury_balances,
            'partner_balances_by_currency': partner_balances_by_currency,
        })
    except ImportError:
        context.update({
            'monthly_revenue_by_currency': [],
            'monthly_expenses_by_currency': [],
            'treasury_balances': [],
            'partner_balances_by_currency': [],
        })

    return render(request, 'dashboard.html', context)


@login_required
def hotels_list(request):
    """صفحة إدارة الفنادق"""
    # احسب عدد المناطق لكل فندق بدون الحاجة لتعديل الموديل
    hotels = (
        Hotel.objects.all()
        .annotate(zones_count=Count('gamezone'))  # يستخدم related_query_name الافتراضي
        .order_by('name')
    )

    total_zones_in_hotels = sum(getattr(h, 'zones_count', 0) for h in hotels)

    context: dict[str, Any] = {
        'hotels': hotels,
        'total_hotels': hotels.count(),
        'active_hotels': hotels.filter(active=True).count(),
        'inactive_hotels': hotels.filter(active=False).count(),
        'total_zones_in_hotels': total_zones_in_hotels,
    }

    return render(request, 'core/hotels.html', context)


@login_required
def zones_list(request):
    """صفحة إدارة المناطق"""
    from accounting.models import DailyRevenue

    # لو مفيش created_at في الموديل، استخدم -id
    zones = GameZone.objects.all().order_by('-id')
    hotels = Hotel.objects.filter(active=True)

    # إضافة إحصائيات لكل منطقة
    for zone in zones:
        # عدد الألعاب (إذا كان هناك علاقة)
        z = cast(Any, zone)
        z.games_count = 0  # TODO: إضافة العلاقة مع الألعاب

        # الإيرادات الشهرية
        current_month = timezone.now().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)

        z.monthly_revenue = list(
            DailyRevenue.objects.filter(
                zone=zone,
                date__gte=current_month,
                date__lt=next_month
            ).values('currency').annotate(
                total=Sum('amount')
            ).order_by('currency')
        )

    context = {
        'zones': zones,
        'hotels': hotels,
        'total_zones': zones.count(),
        'active_zones': zones.filter(active=True).count(),
        'zones_with_games': 0,  # TODO: حساب المناطق التي بها ألعاب
        'total_games_in_zones': 0,  # TODO: حساب إجمالي الألعاب
    }

    return render(request, 'core/zones.html', context)


@login_required
def games_list(request):
    """صفحة إدارة الألعاب"""
    from accounting.models import DailyRevenue

    game_types = GameType.objects.filter(active=True)

    # TODO: إنشاء model للألعاب الفردية
    # حالياً سنعرض أنواع الألعاب
    games = game_types

    # إضافة إحصائيات لكل لعبة
    current_month = timezone.now().replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    today = timezone.now().date()

    for game in games:
        g = cast(Any, game)
        # الإيرادات الشهرية (TODO: إضافة علاقة game_type في DailyRevenue)
        g.monthly_revenue = []  # مؤقتاً حتى يتم إضافة العلاقة

        # عدد مرات اللعب (TODO: إضافة علاقة game_type في DailyRevenue)
        g.play_count = 0  # مؤقتاً حتى يتم إضافة العلاقة

        # السعر (TODO: إضافة أسعار متعددة العملات)
        g.price_per_play = [
            {'currency': 'EGP', 'amount': 10.00},
            {'currency': 'USD', 'amount': 0.50},
        ]

    context = {
        'games': games,
        'game_types': game_types,
        'total_games': games.count(),
        'active_games': games.filter(active=True).count(),
        'games_with_revenue': games.count(),  # TODO: حساب الألعاب التي لها إيرادات
        'total_revenue_today': 'متعدد العملات',  # TODO: حساب إيرادات اليوم
    }

    return render(request, 'core/games.html', context)


@require_http_methods(["POST"])
def hotel_create(request):
    name = request.POST.get('name')
    address = request.POST.get('address')
    active = bool(request.POST.get('active'))
    if name:
        Hotel.objects.create(name=name, location=address or '', manager=None, active=active)
    return redirect('core:hotels_list')


@require_http_methods(["POST"])
def zone_create(request):
    name = request.POST.get('name')
    hotel_id = request.POST.get('hotel')
    active = bool(request.POST.get('active'))
    # حقول إلزامية في GameZone
    code = f"Z{GameZone.objects.count()+1:04d}"
    monthly_rent = Decimal('0.00')
    currency = 'EGP'
    opening_date = timezone.now().date()
    hotel = Hotel.objects.filter(id=hotel_id).first()
    if hotel and name:
        GameZone.objects.create(
            hotel=hotel,
            name=name,
            code=code,
            monthly_rent=monthly_rent,
            currency=currency,
            opening_date=opening_date,
            manager=None,
            active=active,
        )
    return redirect('core:zones_list')



@require_http_methods(["POST"])
@manager_or_admin_required
def hotel_update(request, pk):
    hotel = Hotel.objects.filter(pk=pk).first()
    if not hotel:
        return redirect('core:hotels_list')
    hotel.name = request.POST.get('name', hotel.name)
    hotel.location = request.POST.get('address', hotel.location)
    hotel.active = bool(request.POST.get('active'))
    hotel.save()
    return redirect('core:hotels_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def hotel_delete(request, pk):
    Hotel.objects.filter(pk=pk).delete()
    return redirect('core:hotels_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def zone_update(request, pk):
    zone = GameZone.objects.filter(pk=pk).first()
    if not zone:
        return redirect('core:zones_list')
    name = request.POST.get('name', zone.name)
    hotel_id = request.POST.get('hotel')
    active = bool(request.POST.get('active'))
    if hotel_id:
        h = Hotel.objects.filter(pk=hotel_id).first()
        if h:
            zone.hotel = h
    zone.name = name
    zone.active = active
    zone.save()
    return redirect('core:zones_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def zone_delete(request, pk):
    GameZone.objects.filter(pk=pk).delete()
    return redirect('core:zones_list')

@require_http_methods(["GET", "POST"])
def game_create(request):
    if request.method == "POST":
        # TODO: احفظ اللعبة الجديدة
        return redirect('core:games_list')
    return render(request, 'core/games.html', {
        'games': [],
        'game_types': GameType.objects.filter(active=True),
        'total_games': 0,
        'active_games': 0,
        'games_with_revenue': 0,
        'total_revenue_today': 'متعدد العملات',
    })



@manager_or_admin_required
def game_types_list(request):
    """قائمة أنواع الألعاب"""
    game_types = GameType.objects.filter(active=True).order_by('name')

    context = {
        'games': game_types,  # استخدام نفس اسم المتغير في template
        'game_types': game_types,
        'total_games': game_types.count(),
        'active_games': game_types.filter(active=True).count(),
        'games_with_revenue': 0,
        'total_revenue_today': 'متعدد العملات',
        'is_game_types': True,
    }

    return render(request, 'core/games.html', context)

@require_http_methods(["POST"])
@manager_or_admin_required
def game_type_update(request, pk):
    gt = GameType.objects.filter(pk=pk).first()
    if not gt:
        return redirect('core:game_types_list')
    gt.name = request.POST.get('name', gt.name)
    gt.code = request.POST.get('code', gt.code)
    if request.POST.get('category'):
        gt.category = request.POST.get('category')
    gt.active = bool(request.POST.get('active'))
    gt.save()
    return redirect('core:game_types_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def game_type_delete(request, pk):
    GameType.objects.filter(pk=pk).delete()
    return redirect('core:game_types_list')



@require_http_methods(["GET", "POST"])
@manager_or_admin_required
def game_type_create(request):
    if request.method == "POST":
        # TODO: احفظ نوع اللعبة الجديد
        return redirect('core:game_types_list')
    return render(request, 'core/games.html', {
        'games': [],
        'game_types': GameType.objects.filter(active=True),
        'total_games': 0,
        'active_games': 0,
        'games_with_revenue': 0,
        'total_revenue_today': 'متعدد العملات',
    })


@manager_or_admin_required
def warehouses_list(request):
    """قائمة المخازن"""
    warehouses = Warehouse.objects.filter(active=True).order_by('name')

    context = {
        'warehouses': warehouses,
        'total_warehouses': warehouses.count(),
        'active_warehouses': warehouses.filter(active=True).count(),
    }

    return render(request, 'core/warehouses.html', context)


@require_http_methods(["POST"])
@manager_or_admin_required
def warehouse_create(request):
    name = request.POST.get('name')
    code = request.POST.get('code') or f"W{Warehouse.objects.count()+1:04d}"
    location = request.POST.get('location', '')
    manager_id = request.POST.get('manager')
    active = bool(request.POST.get('active'))
    warehouse_type = request.POST.get('warehouse_type') or 'main'
    manager = User.objects.filter(id=manager_id).first() if manager_id else None
    if name and code:
        Warehouse.objects.create(
            name=name, code=code, location=location, warehouse_type=warehouse_type,
            manager=manager, active=active
        )
    return redirect('core:warehouses_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def warehouse_update(request, pk):
    wh = Warehouse.objects.filter(pk=pk).first()
    if not wh:
        return redirect('core:warehouses_list')
    wh.name = request.POST.get('name', wh.name)
    wh.location = request.POST.get('location', wh.location)
    wh.active = bool(request.POST.get('active'))
    if request.POST.get('warehouse_type'):
        wh.warehouse_type = request.POST.get('warehouse_type')
    wh.save()
    return redirect('core:warehouses_list')


@require_http_methods(["POST"])
@manager_or_admin_required
def warehouse_delete(request, pk):
    Warehouse.objects.filter(pk=pk).delete()
    return redirect('core:warehouses_list')
