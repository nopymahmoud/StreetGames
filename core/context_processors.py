from django.conf import settings


def user_context(request):
    """إضافة معلومات المستخدم للقوالب"""
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'userprofile'):
        profile = request.user.userprofile
        context.update({
            'user_profile': profile,
            'user_role': profile.role,
            'user_role_display': profile.get_role_display(),
            'can_access_all_zones': profile.can_access_all_zones,
            'accessible_zones': profile.get_accessible_zones(),
            'preferred_currency': profile.preferred_currency,
        })
        
        # صلاحيات سريعة
        context.update({
            'is_admin': profile.role == 'admin' or request.user.is_superuser,
            'is_manager': profile.role in ['admin', 'manager'] or request.user.is_superuser,
            'can_access_accounting': profile.role in ['admin', 'manager', 'accountant'] or request.user.is_superuser,
            'can_access_treasury': profile.role in ['admin', 'manager', 'accountant', 'cashier'] or request.user.is_superuser,
        })
    
    return context


from .utils import get_supported_currencies

def app_context(request):
    """إضافة معلومات التطبيق للقوالب"""
    return {
        'app_name': 'Street Games V2',
        'app_version': '2.0.0',
        'company_name': 'شركة ألعاب الشارع',
        'support_email': 'support@streetgames.com',
        'debug_mode': settings.DEBUG,
        'supported_currencies': get_supported_currencies(),
    }
