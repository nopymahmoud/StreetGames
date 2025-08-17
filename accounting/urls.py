from django.urls import path
from . import views, reports_views

app_name = 'accounting'

urlpatterns = [
    path('', views.accounting_dashboard, name='dashboard'),

    # إجراءات صيانة
    path('rebuild/', views.rebuild_accounting_view, name='rebuild_accounting'),

    # الإيرادات
    path('revenues/', views.revenues_list, name='revenues_list'),
    path('revenues/create/', views.revenue_create, name='revenue_create'),
    path('revenues/<int:pk>/edit/', views.revenue_edit, name='revenue_edit'),
    path('revenues/<int:pk>/delete/', views.revenue_delete, name='revenue_delete'),

    # المصروفات
    path('expenses/', views.expenses_list, name='expenses_list'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),

    # التقارير
    path('reports/', reports_views.reports_dashboard, name='reports_dashboard'),
    path('reports/balance-sheet/', reports_views.balance_sheet, name='balance_sheet'),
    path('reports/income-statement/', reports_views.income_statement, name='income_statement'),
    path('reports/trial-balance/', reports_views.trial_balance, name='trial_balance'),
    path('reports/partner-statements/', reports_views.partner_statements, name='partner_statements'),

    # دليل الحسابات
    path('accounts/', views.accounts_list, name='accounts_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),

]
