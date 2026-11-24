from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from .models import Category, Location, LocationSubscription, Review, ReviewVote

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except Exception:
            raise serializers.ValidationError({"uid": "Некоректний ідентифікатор користувача."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Недійсний або прострочений токен."})

        attrs["user"] = user
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class LocationSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_last_7_days = serializers.IntegerField(read_only=True)
    popularity_score = serializers.FloatField(read_only=True)

    class Meta:
        model = Location
        fields = [
            "id",
            "title",
            "description",
            "category",
            "category_name",
            "address",
            "latitude",
            "longitude",
            "author",
            "author_username",
            "avg_rating",
            "reviews_count",
            "views_last_7_days",
            "popularity_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "author_username",
            "avg_rating",
            "reviews_count",
            "views_last_7_days",
            "popularity_score",
            "created_at",
            "updated_at",
        ]

    def validate_latitude(self, value):
        if value < -90.0 or value > 90.0:
            raise serializers.ValidationError("Широта повинна бути в межах від -90 до 90.")
        return value

    def validate_longitude(self, value):
        if value < -180.0 or value > 180.0:
            raise serializers.ValidationError("Довгота повинна бути в межах від -180 до 180.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "location",
            "author",
            "author_username",
            "rating",
            "comment",
            "likes_count",
            "dislikes_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "location",
            "author",
            "author_username",
            "likes_count",
            "dislikes_count",
            "created_at",
            "updated_at",
        ]

    def get_likes_count(self, obj):
        return obj.votes.filter(vote_type=ReviewVote.LIKE).count()

    def get_dislikes_count(self, obj):
        return obj.votes.filter(vote_type=ReviewVote.DISLIKE).count()

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Рейтинг повинен бути в межах від 1 до 5.")
        return value


class ReviewVoteSerializer(serializers.Serializer):
    vote_type = serializers.ChoiceField(choices=[ReviewVote.LIKE, ReviewVote.DISLIKE])


class LocationSubscriptionSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = LocationSubscription
        fields = ["id", "location", "user", "email", "created_at"]
        read_only_fields = ["id", "location", "user", "email", "created_at"]