from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('suppliers/', views.suppliers_list, name='suppliers_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),

    path('bills/', views.bills_list, name='bills_list'),
    path('bills/create/', views.bill_create, name='bill_create'),
    path('bills/<int:pk>/edit/', views.bill_edit, name='bill_edit'),
    path('bills/<int:pk>/delete/', views.bill_delete, name='bill_delete'),

    path('returns/', views.returns_list, name='returns_list'),
    path('returns/create/', views.return_create, name='return_create'),
    path('returns/<int:pk>/edit/', views.return_edit, name='return_edit'),
    path('suppliers/<int:pk>/pay/', views.supplier_payment_view, name='supplier_payment'),
    path('suppliers/<int:pk>/ledger/export/', views.supplier_ledger_export, name='supplier_ledger_export'),

    path('returns/<int:pk>/delete/', views.return_delete, name='return_delete'),

    path('suppliers/<int:pk>/ledger/', views.supplier_ledger, name='supplier_ledger'),
]

