

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("videos.urls")),
    path("", include("payments.urls")),
    path("", include("contact.urls")),
    path("", include("captcha_app.urls")),
    path("", include("scheduler.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
