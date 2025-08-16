from django.urls import path
from . import views

app_name = 'partnerships'

urlpatterns = [
    # الشراكات
    path('', views.partnerships_list, name='partnerships_list'),
    path('create/', views.partnership_create, name='partnership_create'),
    path('<int:pk>/edit/', views.partnership_edit, name='partnership_edit'),

    # كشوف الحسابات
    path('accounts/', views.partner_accounts_list, name='partner_accounts_list'),

    # المدفوعات
    path('payments/', views.payments_list, name='payments_list'),
    path('payments/create/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/edit/', views.payment_edit, name='payment_edit'),
]
