from django.contrib import admin
from django.urls import include, path
from locations.views import index_view
urlpatterns = [
    path("", index_view, name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("locations.urls")),
]
