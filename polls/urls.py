from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("anket/yeni/", views.create, name="create"),
    path("anket/<uuid:pk>/", views.detail, name="detail"),
    path("u/<str:username>/", views.profile, name="profile"),
]
