import io
import json
from datetime import timedelta
import pandas as pd
import redis
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from .models import Location, LocationSubscription, LocationView


def get_redis_client():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def get_viewer_key(request):
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}"

    if not request.session.session_key:
        request.session.save()
    session_part = request.session.session_key or "no-session"

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else request.META.get("REMOTE_ADDR", "unknown-ip")
    )
    return f"anon:{ip}:{session_part}"


def record_location_view(request, location):
    """Збільшує перегляди максимум 1 раз на годину на користувача/аноніма через Redis."""
    viewer_key = get_viewer_key(request)
    redis_key = f"loc_view:{location.pk}:{viewer_key}"

    try:
        client = get_redis_client()
        was_set = client.set(redis_key, "1", ex=3600, nx=True)
    except redis.RedisError:
        # Якщо Redis тимчасово недоступний, перевіряємо останні 60 хв у БД як fallback
        cutoff = timezone.now() - timedelta(hours=1)
        exists_recently = LocationView.objects.filter(
            location=location,
            viewer_key=viewer_key,
            viewed_at__gte=cutoff,
        ).exists()
        was_set = not exists_recently

    if was_set:
        user = request.user if request.user and request.user.is_authenticated else None
        LocationView.objects.create(
            location=location,
            user=user,
            viewer_key=viewer_key,
        )
        invalidate_locations_cache()
        return True

    return False


def get_annotated_locations_queryset():
    """
    Повертає активні (не видалені через soft delete) локації з обчисленими
    середнім рейтингом, кількістю відгуків, переглядами за 7 днів та популярністю.
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Уникаємо подвійного множення через JOIN reviews і view_events за рахунок distinct=True
    qs = (
        Location.objects.filter(is_deleted=False)
        .select_related("category", "author")
        .annotate(
            avg_rating=Coalesce(
                Avg("reviews__rating"),
                Value(0.0),
                output_field=FloatField(),
            ),
            reviews_count=Count("reviews", distinct=True),
            views_last_7_days=Count(
                "view_events",
                filter=Q(view_events__viewed_at__gte=seven_days_ago),
                distinct=True,
            ),
        )
        .annotate(
            popularity_score=ExpressionWrapper(
                F("avg_rating") * 2.0
                + F("reviews_count") * 1.5
                + F("views_last_7_days") * 0.5,
                output_field=FloatField(),
            )
        )
    )
    return qs


def build_locations_cache_key(query_params):
    sorted_items = sorted((k, v) for k, v in query_params.items())
    raw = json.dumps(sorted_items, ensure_ascii=False)
    return f"locations_list:{raw}"


def get_cached_locations_payload(cache_key):
    try:
        client = get_redis_client()
        raw = client.get(cache_key)
        if raw:
            return json.loads(raw)
    except redis.RedisError:
        pass
    return None


def set_cached_locations_payload(cache_key, payload, ttl=120):
    try:
        client = get_redis_client()
        client.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=ttl)
    except redis.RedisError:
        pass


def invalidate_locations_cache():
    try:
        client = get_redis_client()
        keys = client.keys("locations_list:*")
        if keys:
            client.delete(*keys)
    except redis.RedisError:
        pass


def serialize_locations_for_export(queryset):
    rows = []
    for loc in queryset:
        rows.append(
            {
                "id": loc.id,
                "title": loc.title,
                "description": loc.description,
                "category": loc.category.name,
                "address": loc.address,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "author": loc.author.username,
                "avg_rating": round(float(getattr(loc, "avg_rating", 0.0) or 0.0), 2),
                "reviews_count": int(getattr(loc, "reviews_count", 0) or 0),
                "views_last_7_days": int(getattr(loc, "views_last_7_days", 0) or 0),
                "popularity_score": round(
                    float(getattr(loc, "popularity_score", 0.0) or 0.0), 2
                ),
                "created_at": loc.created_at.isoformat(),
                "updated_at": loc.updated_at.isoformat(),
            }
        )
    return rows


def export_locations_to_json_bytes(queryset):
    data = serialize_locations_for_export(queryset)
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def export_locations_to_csv_bytes(queryset):
    data = serialize_locations_for_export(queryset)
    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def notify_about_new_review(review):
    """Надсилає email автору локації та підписникам на локацію (на email з профілю)."""
    location = review.location
    author_email = (location.author.email or "").strip()

    if author_email:
        send_mail(
            subject=f"Новий відгук до локації «{location.title}»",
            message=(
                f"Користувач {review.author.username} залишив відгук ({review.rating}/5) "
                f"до вашої локації «{location.title}»:\n\n{review.comment}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[author_email],
            fail_silently=True,
        )

    subscriptions = (
        LocationSubscription.objects.filter(location=location)
        .select_related("user")
        .exclude(user=review.author)
    )
    subscriber_emails = sorted(
        {
            (sub.user.email or "").strip()
            for sub in subscriptions
            if (sub.user.email or "").strip()
        }
    )

    if subscriber_emails:
        send_mail(
            subject=f"Оновлення локації «{location.title}»: новий відгук",
            message=(
                f"У локації «{location.title}», на яку ви підписані, з'явився новий відгук "
                f"від {review.author.username} (оцінка: {review.rating}/5):\n\n{review.comment}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=subscriber_emails,
            fail_silently=True,
        )