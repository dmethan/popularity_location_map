from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    LocationViewSet,
    ReviewViewSet,
    login_view,
    logout_view,
    password_reset_confirm_view,
    password_reset_request_view,
    register_view,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("locations", LocationViewSet, basename="location")

reviews_list = ReviewViewSet.as_view({"get": "list", "post": "create"})
reviews_detail = ReviewViewSet.as_view({"get": "retrieve"})
reviews_vote = ReviewViewSet.as_view({"post": "vote"})

urlpatterns = [
    path("auth/register/", register_view, name="auth-register"),
    path("auth/login/", login_view, name="auth-login"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path(
        "auth/password-reset/",
        password_reset_request_view,
        name="auth-password-reset",
    ),
    path(
        "auth/password-reset/confirm/",
        password_reset_confirm_view,
        name="auth-password-reset-confirm",
    ),
    path("", include(router.urls)),
    path(
        "locations/<int:location_pk>/reviews/",
        reviews_list,
        name="location-reviews-list",
    ),
    path(
        "locations/<int:location_pk>/reviews/<int:pk>/",
        reviews_detail,
        name="location-reviews-detail",
    ),
    path(
        "locations/<int:location_pk>/reviews/<int:pk>/vote/",
        reviews_vote,
        name="location-reviews-vote",
    ),
]