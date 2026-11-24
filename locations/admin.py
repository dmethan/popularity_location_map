from django.contrib import admin
from .models import (
    Category,
    Location,
    LocationSubscription,
    LocationView,
    Review,
    ReviewVote,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name", "description")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "author",
        "latitude",
        "longitude",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_deleted", "category", "created_at")
    search_fields = ("title", "description", "address")


@admin.register(LocationView)
class LocationViewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "user", "viewer_key", "viewed_at")
    list_filter = ("viewed_at",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "author", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment",)


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "vote_type", "created_at")
    list_filter = ("vote_type",)


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "user", "created_at")