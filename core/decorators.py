from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.urls import reverse
from .models import AuditLog

def is_officer(user):
    """
    Check if the user is an authorized officer or admin.
    Must be authenticated and have staff or superuser status.
    """
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))

def is_admin(user):
    """
    Legacy compatibility helper.
    """
    return is_officer(user)

def officer_required(view_func):
    """
    Decorator for views that require officer or administrator privileges.
    Unauthenticated users are redirected to officer_login.
    Authenticated citizens without officer privileges receive a strict 403 Forbidden response.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('officer_login')}?next={request.path}")

        if not is_officer(request.user):
            AuditLog.log(
                request=request,
                action='permission_denied',
                target_type='view',
                target_id=view_func.__name__,
                details=f"Citizen '{request.user.username}' attempted to access restricted officer view '{view_func.__name__}'."
            )
            return HttpResponseForbidden("403 Forbidden: Officer or administrator privileges required.")

        return view_func(request, *args, **kwargs)
    return _wrapped_view

def citizen_required(view_func):
    """
    Decorator for views requiring citizen authentication.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
