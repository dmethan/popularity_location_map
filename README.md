# Мапа популярності локацій (Django REST Framework)

REST API сервіс для додавання цікавих локацій, оцінювання, відгуків, перегляду популярних місць, експорту даних у JSON/CSV та email-сповіщень.

## Технологічний стек
- **Python 3.12**, **Django 5.1**, **Django REST Framework**
- **PostgreSQL 16** (у Docker-контейнері з автоматичним створенням БД та користувача)
- **Redis 7** (у Docker-контейнері — лічильник переглядів 1 раз/год та кешування списку локацій)
- **Session + Cookies** аутентифікація Django (без JWT)
- **django-filter** для фільтрації та **pandas** для експорту у CSV
- **Docker Compose**

## Структура проєкту

```text
.
├── .env
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── README.md
├── requirements.txt
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── locations/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── filters.py
    ├── models.py
    ├── permissions.py
    ├── serializers.py
    ├── services.py
    ├── tests.py
    ├── urls.py
    └── views.py
```

## Запуск проєкту в Docker та створення `.env`

Під час першого запуску база даних PostgreSQL створюється автоматично з нуля згідно з параметрами `POSTGRES_DB`, `POSTGRES_USER` та `POSTGRES_PASSWORD`. Назву бази, ім'я користувача та пароль можна ставити будь-які. Якщо раніше вже запускався контейнер і ви змінили пароль або назву БД у `.env`, виконайте `docker compose down -v`, щоб очистити старий volume і створити базу з новими значеннями.

Файл `.env` доданий до `.gitignore` і не потрапляє на GitHub (у репозиторії зберігається лише шаблон `.env.example`).

### Створення файлу `.env` із заданими значеннями та запуск Docker-контейнерів (PowerShell)

Відкрийте термінал PowerShell у кореневій папці проєкту та виконайте команду — вона створить файл `.env` із вказаними параметрами (`$db`, `$user`, `$pass`, `$secret`) і одразу запустить `docker compose up --build`:

```powershell
$db="locations_db"; $user="locations_user"; $pass="MyAnyPassword123!"; $secret="my-django-secret-key-123456"; @"
DJANGO_SECRET_KEY=$secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
POSTGRES_DB=$db
POSTGRES_USER=$user
POSTGRES_PASSWORD=$pass
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@locations-map.local
"@ | Set-Content -Path .env -Encoding UTF8; docker compose up --build
```
### Що відбувається під час виконання

1. Створюється або оновлюється файл `.env` із налаштуваннями Django, PostgreSQL, Redis та пошти.
2. Запускаються контейнери PostgreSQL (`db`) і Redis (`redis`) з перевіркою готовності (`healthcheck`).
3. Сервіс Django (`web`) чекає готовності БД та Redis, автоматично виконує `python manage.py migrate` і запускає API на `http://localhost:8000/api/` (адмін-панель — `http://localhost:8000/admin/`).

### Корисні команди для роботи з Docker

**Запуск у фоновому режимі (коли `.env` уже створено):**

PowerShell

```powershell
docker compose up -d --build
```

# Корисні команди Docker

## Перевірити стан контейнерів

### PowerShell

```powershell
docker compose ps
```

## Переглянути логи веб-сервісу

Міграції, помилки, вивід листів при `console.EmailBackend`.

### PowerShell

```powershell
docker compose logs -f web
```

## Створити суперкористувача

### PowerShell

```powershell
docker compose exec web python manage.py createsuperuser
```

## Запустити API-тести

### PowerShell

```powershell
docker compose exec web python manage.py test
```

## Зупинити контейнери

Дані БД та Redis зберігаються.

### PowerShell

```powershell
docker compose down
```

## Видалити контейнери та volumes

Використовується для створення БД з нуля або застосування нового пароля з `.env`.

### PowerShell

```powershell
docker compose down -v
```

# Основні API Endpoints

## Аутентифікація (Session + Cookies)

### Реєстрація

```http
POST /api/auth/register/
```

Параметри:

- `username`
- `email`
- `password`

### Вхід у систему

```http
POST /api/auth/login/
```

Параметри:

- `username`
- `password`

### Вихід із системи

```http
POST /api/auth/logout/
```

### Запит на скидання пароля

```http
POST /api/auth/password-reset/
```

Параметри:

- `email`

### Підтвердження нового пароля

```http
POST /api/auth/password-reset/confirm/
```

Параметри:

- `uid`
- `token`
- `new_password`

---

## Категорії та локації

### Категорії

```http
GET    /api/categories/
POST   /api/categories/
GET    /api/categories/{id}/
PUT    /api/categories/{id}/
PATCH  /api/categories/{id}/
DELETE /api/categories/{id}/
```

### Локації

```http
GET    /api/locations/
POST   /api/locations/
GET    /api/locations/{id}/
PUT    /api/locations/{id}/
PATCH  /api/locations/{id}/
DELETE /api/locations/{id}/
```

### Особливості

- `DELETE /api/locations/{id}/` виконує **Soft Delete**:
  - `is_deleted=True`
  - `deleted_at` автоматично заповнюється

- Редагувати або видаляти локацію може лише:
  - автор локації;
  - адміністратор.

- Координати перевіряються у стандартних географічних межах:
  - `latitude`: від `-90` до `90`
  - `longitude`: від `-180` до `180`

### Підписка на оновлення локації

```http
POST   /api/locations/{id}/subscribe/
DELETE /api/locations/{id}/subscribe/
```

Дозволяє авторизованому користувачу підписатися або скасувати підписку на оновлення локації через email зі свого акаунта.

### Експорт локацій

```http
GET /api/locations/export/?format=json
GET /api/locations/export/?format=csv
```

Підтримувані формати:

- JSON
- CSV (через pandas)

---

## Відгуки та голоси

### Відгуки

```http
GET  /api/locations/{location_id}/reviews/
POST /api/locations/{location_id}/reviews/
```

Містять:

- рейтинг від `1` до `5`
- коментар

Обмеження:

- один відгук на користувача для однієї локації

### Голосування за відгуки

```http
POST /api/locations/{location_id}/reviews/{id}/vote/
```

Тіло запиту:

```json
{
  "vote_type": "like"
}
```

або

```json
{
  "vote_type": "dislike"
}
```

Логіка голосування:

- повторний однаковий голос знімається;
- протилежний голос автоматично перемикається.

---

## Пошук, фільтрація та сортування

### Пошук

```text
?search=назва_або_опис
```

### Фільтрація

```text
?category=1
&author=2
&min_rating=4
&max_rating=5
&min_reviews=1
&min_views_7d=5
```

### Сортування

```text
?ordering=created_at
?ordering=-avg_rating
?ordering=-popularity_score
```

### Пагінація

```text
?page=1
```

За замовчуванням відображається **10 записів на сторінку**.

---

## Рейтинг і популярність (без збереження в БД)

### Середній рейтинг

Поля:

- `avg_rating`
- `reviews_count`

Обчислюються через ORM-агрегації.

### Перегляди за останні 7 днів

Поле:

- `views_last_7_days`

Підраховується на основі подій переглядів за останні 7 діб.

Лічильник збільшується не частіше ніж **1 раз на годину** для кожного:

- авторизованого користувача;
- анонімного відвідувача.

Для кешування використовується Redis з:

```text
TTL = 3600 сек
```

### Популярність

Поле:

- `popularity_score`

Обчислюється динамічно через ORM-вираз на основі:

- `avg_rating`
- `reviews_count`
- `views_last_7_days`