from django.urls import path

from users.views import DemoLoginView, MePreferencesView, MeView

urlpatterns = [
    path("demo/login/", DemoLoginView.as_view(), name="demo-login"),
    path("me/", MeView.as_view(), name="me"),
    path("me/preferences/", MePreferencesView.as_view(), name="me-preferences"),
]
