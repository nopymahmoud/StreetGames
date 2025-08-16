from django.urls import path
from . import views

app_name = 'treasury'

urlpatterns = [
    # TODO: Add treasury views
    path('', views.treasury_dashboard, name='treasury_dashboard'),
]
