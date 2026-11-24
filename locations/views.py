from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from .filters import LocationFilter
from .models import Category, Location, LocationSubscription, Review, ReviewVote
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    CategorySerializer,
    LocationSerializer,
    LocationSubscriptionSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ReviewSerializer,
    ReviewVoteSerializer,
)
from .services import (
    build_locations_cache_key,
    export_locations_to_csv_bytes,
    export_locations_to_json_bytes,
    get_annotated_locations_queryset,
    get_cached_locations_payload,
    invalidate_locations_cache,
    notify_about_new_review,
    record_location_view,
    set_cached_locations_payload,
)

User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(
        {"id": user.pk, "username": user.username, "email": user.email},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )
    if not user:
        return Response(
            {"detail": "Невірний логін або пароль."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    login(request, user)
    return Response(
        {"id": user.pk, "username": user.username, "email": user.email},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"detail": "Вихід виконано."}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].strip()

    user = User.objects.filter(email__iexact=email).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_mail(
            subject="Скидання пароля — Мапа популярності локацій",
            message=(
                f"Вітаємо, {user.username}!\n\n"
                f"Для скидання пароля використайте:\n"
                f"uid: {uid}\n"
                f"token: {token}"
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

    return Response(
        {"detail": "Якщо акаунт з таким email існує, інструкцію надіслано."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    user.set_password(serializer.validated_data["new_password"])
    user.save()
    return Response({"detail": "Пароль успішно оновлено."}, status=status.HTTP_200_OK)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filterset_class = LocationFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "avg_rating", "popularity_score"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return get_annotated_locations_queryset()

    def list(self, request, *args, **kwargs):
        cache_key = build_locations_cache_key(request.query_params)
        cached = get_cached_locations_payload(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            set_cached_locations_payload(cache_key, response.data)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        record_location_view(request, instance)
        # Перечитуємо об'єкт з анотаціями, щоб повернути актуальні перегляди й популярність
        refreshed = self.get_queryset().get(pk=instance.pk)
        serializer = self.get_serializer(refreshed)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        invalidate_locations_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_locations_cache()

    def perform_destroy(self, instance):
        instance.soft_delete()
        invalidate_locations_cache()

    @action(
        detail=False,
        methods=["get"],
        url_path="export",
        permission_classes=[AllowAny],
    )
    def export_locations(self, request):
        export_format = request.query_params.get("format", "json").lower()
        qs = self.filter_queryset(self.get_queryset())

        if export_format == "csv":
            content = export_locations_to_csv_bytes(qs)
            response = HttpResponse(content, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="locations.csv"'
            return response

        if export_format == "json":
            content = export_locations_to_json_bytes(qs)
            response = HttpResponse(
                content, content_type="application/json; charset=utf-8"
            )
            response["Content-Disposition"] = 'attachment; filename="locations.json"'
            return response

        return Response(
            {"detail": "Підтримуються лише формати: json або csv."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="subscribe",
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, pk=None):
        location = self.get_object()

        if request.method == "DELETE":
            deleted_count, _ = LocationSubscription.objects.filter(
                location=location, user=request.user
            ).delete()
            if deleted_count == 0:
                return Response(
                    {"detail": "Ви не підписані на цю локацію."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"detail": "Підписку скасовано."}, status=status.HTTP_200_OK
            )

        subscription, created = LocationSubscription.objects.get_or_create(
            location=location, user=request.user
        )
        if not created:
            return Response(
                {"detail": "Ви вже підписані на оновлення цієї локації."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LocationSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_location(self):
        return get_object_or_404(
            Location, pk=self.kwargs["location_pk"], is_deleted=False
        )

    def get_queryset(self):
        return Review.objects.filter(
            location_id=self.kwargs["location_pk"],
            location__is_deleted=False,
        ).select_related("author")

    def perform_create(self, serializer):
        location = self.get_location()
        if Review.objects.filter(location=location, author=self.request.user).exists():
            raise ValidationError(
                {"detail": "Ви вже залишили відгук до цієї локації."}
            )
        try:
            review = serializer.save(location=location, author=self.request.user)
        except IntegrityError:
            raise ValidationError(
                {"detail": "Ви вже залишили відгук до цієї локації."}
            )

        invalidate_locations_cache()
        notify_about_new_review(review)

    @action(
        detail=True,
        methods=["post"],
        url_path="vote",
        permission_classes=[IsAuthenticated],
    )
    def vote(self, request, location_pk=None, pk=None):
        review = self.get_object()
        serializer = ReviewVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chosen_vote = serializer.validated_data["vote_type"]

        existing = ReviewVote.objects.filter(review=review, user=request.user).first()
        if existing:
            if existing.vote_type == chosen_vote:
                # Повторне натискання того самого голосу — знімаємо його
                existing.delete()
                status_text = "vote_removed"
                current_vote = None
            else:
                # Перемикаємо голос (like <-> dislike)
                existing.vote_type = chosen_vote
                existing.save(update_fields=["vote_type"])
                status_text = "vote_updated"
                current_vote = existing.vote_type
        else:
            ReviewVote.objects.create(
                review=review, user=request.user, vote_type=chosen_vote
            )
            status_text = "vote_added"
            current_vote = chosen_vote

        return Response(
            {
                "status": status_text,
                "current_vote": current_vote,
                "likes_count": review.votes.filter(vote_type=ReviewVote.LIKE).count(),
                "dislikes_count": review.votes.filter(
                    vote_type=ReviewVote.DISLIKE
                ).count(),
            },
            status=status.HTTP_200_OK,
        )