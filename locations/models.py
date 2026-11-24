from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        return self.name


class Location(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="locations",
    )
    address = models.CharField(max_length=255)
    latitude = models.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)]
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)]
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Локація"
        verbose_name_plural = "Локації"

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def __str__(self):
        return self.title


class LocationView(models.Model):
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="view_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="location_views",
    )
    viewer_key = models.CharField(max_length=255, db_index=True)
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]
        verbose_name = "Перегляд локації"
        verbose_name_plural = "Перегляди локацій"

    def __str__(self):
        return f"{self.location_id} ({self.viewer_key}) @ {self.viewed_at}"


class Review(models.Model):
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Відгук"
        verbose_name_plural = "Відгуки"
        constraints = [
            models.UniqueConstraint(
                fields=["location", "author"],
                name="unique_review_per_user_location",
            )
        ]

    def __str__(self):
        return f"Review #{self.pk} ({self.rating}/5) on {self.location_id}"


class ReviewVote(models.Model):
    LIKE = "like"
    DISLIKE = "dislike"
    VOTE_CHOICES = [
        (LIKE, "Like"),
        (DISLIKE, "Dislike"),
    ]

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_votes",
    )
    vote_type = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Голос до відгуку"
        verbose_name_plural = "Голоси до відгуків"
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"],
                name="unique_vote_per_user_review",
            )
        ]

    def __str__(self):
        return f"{self.user_id} -> Review #{self.review_id}: {self.vote_type}"


class LocationSubscription(models.Model):
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Підписка на локацію"
        verbose_name_plural = "Підписки на локації"
        constraints = [
            models.UniqueConstraint(
                fields=["location", "user"],
                name="unique_subscription_per_user_location",
            )
        ]

    def __str__(self):
        return f"{self.user_id} subscribed to {self.location_id}"