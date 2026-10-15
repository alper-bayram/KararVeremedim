from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("anket/yeni/", views.create, name="create"),
    path("anket/<uuid:pk>/", views.detail, name="detail"),
    path("anket/<uuid:pk>/oy/", views.vote, name="vote"),
    path("anket/<uuid:pk>/kapat/", views.close, name="close"),
    path("anket/<uuid:pk>/sil/", views.delete, name="delete"),
    path("u/<str:username>/", views.profile, name="profile"),
]
