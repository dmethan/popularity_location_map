import django_filters
from .models import Location


class LocationFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_id")
    author = django_filters.NumberFilter(field_name="author_id")

    min_rating = django_filters.NumberFilter(
        field_name="avg_rating", lookup_expr="gte"
    )
    max_rating = django_filters.NumberFilter(
        field_name="avg_rating", lookup_expr="lte"
    )
    min_reviews = django_filters.NumberFilter(
        field_name="reviews_count", lookup_expr="gte"
    )
    min_views_7d = django_filters.NumberFilter(
        field_name="views_last_7_days", lookup_expr="gte"
    )

    class Meta:
        model = Location
        fields = [
            "category",
            "author",
            "min_rating",
            "max_rating",
            "min_reviews",
            "min_views_7d",
        ]