from rest_framework import permissions

class IsOfficerOrAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated officers/admins.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))


class IsOwnerOrOfficer(permissions.BasePermission):
    """
    Object-level permission allowing citizens to view/edit only their own objects,
    while officers have administrative read/review access.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        if hasattr(obj, 'user'):
            return obj.user == request.user

        if hasattr(obj, 'voter'):
            return obj.voter == request.user

        return False
