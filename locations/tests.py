from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Category, Location, Review

User = get_user_model()


class LocationPopularityMapAPITests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="StrongPassword123!",
        )
        self.user2 = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="StrongPassword123!",
        )
        self.category = Category.objects.create(
            name="Парки",
            description="Зелені зони та сквери",
        )
        self.location = Location.objects.create(
            title="Маріїнський парк",
            description="Старовинний парк у центрі міста",
            category=self.category,
            address="вул. Михайла Грушевського, Київ",
            latitude=50.4475,
            longitude=30.5384,
            author=self.user1,
        )

    def test_session_auth_and_location_crud_with_soft_delete(self):
        # Анонім може лише читати
        list_url = reverse("location-list")
        res = self.client.get(list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        create_res = self.client.post(
            list_url,
            {
                "title": "Парк Шевченка",
                "description": "Популярний парк",
                "category": self.category.pk,
                "address": "вул. Володимирська, Київ",
                "latitude": 50.4418,
                "longitude": 30.5134,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)

        # Вхід через сесію
        login_url = reverse("auth-login")
        login_res = self.client.post(
            login_url,
            {"username": "alice", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        # Створення власної локації
        create_res = self.client.post(
            list_url,
            {
                "title": "Парк Шевченка",
                "description": "Популярний парк",
                "category": self.category.pk,
                "address": "вул. Володимирська, Київ",
                "latitude": 50.4418,
                "longitude": 30.5134,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        created_id = create_res.data["id"]

        # Інший користувач не може видалити локацію alice
        self.client.force_authenticate(user=self.user2)
        detail_url = reverse("location-detail", kwargs={"pk": created_id})
        forbidden_del = self.client.delete(detail_url)
        self.assertEqual(forbidden_del.status_code, status.HTTP_403_FORBIDDEN)

        # Автор може зробити soft delete
        self.client.force_authenticate(user=self.user1)
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        loc_db = Location.objects.get(pk=created_id)
        self.assertTrue(loc_db.is_deleted)
        self.assertIsNotNone(loc_db.deleted_at)

    def test_coordinate_validation(self):
        self.client.force_authenticate(user=self.user1)
        list_url = reverse("location-list")
        res = self.client.post(
            list_url,
            {
                "title": "Невалідні координати",
                "description": "Тест",
                "category": self.category.pk,
                "address": "Десь",
                "latitude": 120.0,
                "longitude": 200.0,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unique_review_votes_subscription_and_notifications(self):
        reviews_url = reverse(
            "location-reviews-list", kwargs={"location_pk": self.location.pk}
        )
        sub_url = reverse("location-subscribe", kwargs={"pk": self.location.pk})

        # Bob підписується на оновлення локації
        self.client.force_authenticate(user=self.user2)
        sub_res = self.client.post(sub_url)
        self.assertEqual(sub_res.status_code, status.HTTP_201_CREATED)

        # Bob залишає відгук -> мають піти листи автору локації (alice) та підписникам
        rev_res = self.client.post(
            reviews_url,
            {"rating": 5, "comment": "Дуже гарне місце"},
            format="json",
        )
        self.assertEqual(rev_res.status_code, status.HTTP_201_CREATED)
        review_id = rev_res.data["id"]
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("alice@example.com", mail.outbox[0].to)

        # Повторний відгук від того ж користувача до тієї ж локації повертає помилку
        dup_res = self.client.post(
            reviews_url,
            {"rating": 4, "comment": "Другий відгук"},
            format="json",
        )
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Голосування: додати like -> змінити на dislike -> повторний dislike знімає голос
        vote_url = reverse(
            "location-reviews-vote",
            kwargs={"location_pk": self.location.pk, "pk": review_id},
        )
        v1 = self.client.post(vote_url, {"vote_type": "like"}, format="json")
        self.assertEqual(v1.status_code, status.HTTP_200_OK)
        self.assertEqual(v1.data["likes_count"], 1)

        v2 = self.client.post(vote_url, {"vote_type": "dislike"}, format="json")
        self.assertEqual(v2.status_code, status.HTTP_200_OK)
        self.assertEqual(v2.data["likes_count"], 0)
        self.assertEqual(v2.data["dislikes_count"], 1)

        v3 = self.client.post(vote_url, {"vote_type": "dislike"}, format="json")
        self.assertEqual(v3.status_code, status.HTTP_200_OK)
        self.assertEqual(v3.data["dislikes_count"], 0)
        self.assertIsNone(v3.data["current_vote"])

    @patch("locations.services.get_redis_client")
    def test_views_rate_limit_and_export_formats(self, mock_redis):
        # Імітуємо Redis nx=True для першого запиту і nx=False для другого протягом години
        fake_client = mock_redis.return_value
        fake_client.set.side_effect = [True, False]

        detail_url = reverse("location-detail", kwargs={"pk": self.location.pk})
        r1 = self.client.get(detail_url)
        r2 = self.client.get(detail_url)
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["views_last_7_days"], 1)
        self.assertEqual(r2.data["views_last_7_days"], 1)

        # Експорт у JSON та CSV
        export_url = reverse("location-export-locations")
        json_res = self.client.get(export_url, {"format": "json"})
        self.assertEqual(json_res.status_code, status.HTTP_200_OK)
        self.assertIn("Маріїнський парк", json_res.content.decode("utf-8"))

        csv_res = self.client.get(export_url, {"format": "csv"})
        self.assertEqual(csv_res.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", csv_res["Content-Type"])
        self.assertIn("Маріїнський парк", csv_res.content.decode("utf-8"))