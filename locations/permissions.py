from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthorOrAdminOrReadOnly(BasePermission):
    """
    Читати можуть усі. Створювати — авторизовані.
    Редагувати або видаляти — лише автор локації або адміністратор.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.author_id == request.user.pk or bool(
            request.user.is_staff or request.user.is_superuser
        )