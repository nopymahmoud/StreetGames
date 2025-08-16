from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from .models import GameZone


def role_required(allowed_roles):
    """
    Decorator للتحقق من دور المستخدم
    Usage: @role_required(['admin', 'manager'])
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'userprofile'):
                raise PermissionDenied("ملف المستخدم غير موجود")
            
            user_role = request.user.userprofile.role
            if user_role not in allowed_roles:
                raise PermissionDenied(f"غير مسموح لك بالوصول. الأدوار المطلوبة: {', '.join(allowed_roles)}")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def zone_access_required(zone_param='zone_id'):
    """
    Decorator للتحقق من صلاحية الوصول لمنطقة معينة
    Usage: @zone_access_required('zone_id')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'userprofile'):
                raise PermissionDenied("ملف المستخدم غير موجود")
            
            # الحصول على معرف المنطقة من المعاملات
            zone_id = kwargs.get(zone_param) or request.GET.get(zone_param) or request.POST.get(zone_param)
            
            if zone_id:
                zone = get_object_or_404(GameZone, id=zone_id, active=True)
                if not request.user.userprofile.has_zone_access(zone):
                    raise PermissionDenied("غير مسموح لك بالوصول لهذه المنطقة")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(view_func):
    """
    Decorator للتحقق من صلاحيات المدير
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'userprofile'):
            raise PermissionDenied("ملف المستخدم غير موجود")
        
        if request.user.userprofile.role != 'admin' and not request.user.is_superuser:
            raise PermissionDenied("هذه الصفحة مخصصة للمديرين فقط")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def manager_or_admin_required(view_func):
    """
    Decorator للتحقق من صلاحيات المدير أو المدير العام
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'userprofile'):
            raise PermissionDenied("ملف المستخدم غير موجود")
        
        user_role = request.user.userprofile.role
        if user_role not in ['admin', 'manager'] and not request.user.is_superuser:
            raise PermissionDenied("هذه الصفحة مخصصة للمديرين والمديرين العامين فقط")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def accounting_access_required(view_func):
    """
    Decorator للتحقق من صلاحيات الوصول للمحاسبة
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # السماح للمدير العام بالوصول
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not hasattr(request.user, 'userprofile'):
            return HttpResponseForbidden("ملف المستخدم غير موجود")

        user_role = request.user.userprofile.role
        allowed_roles = ['admin', 'manager', 'accountant']

        if user_role not in allowed_roles:
            return HttpResponseForbidden("غير مسموح لك بالوصول للنظام المحاسبي")

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def treasury_access_required(view_func):
    """
    Decorator للتحقق من صلاحيات الوصول للخزينة
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # السماح للمدير العام بالوصول
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not hasattr(request.user, 'userprofile'):
            return HttpResponseForbidden("ملف المستخدم غير موجود")

        user_role = request.user.userprofile.role
        allowed_roles = ['admin', 'manager', 'accountant', 'cashier']

        if user_role not in allowed_roles:
            return HttpResponseForbidden("غير مسموح لك بالوصول لنظام الخزينة")

        return view_func(request, *args, **kwargs)
    return _wrapped_view
