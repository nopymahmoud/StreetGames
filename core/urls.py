from django.urls import path
from . import views, api_views
from django.shortcuts import render

app_name = 'core'

def test_links_view(request):
    return render(request, 'test_links.html')

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # صفحات الإدارة الجديدة
    path('hotels/', views.hotels_list, name='hotels_list'),
    path('hotels/create/', views.hotel_create, name='hotel_create'),
    path('zones/', views.zones_list, name='zones_list'),
    path('zones/create/', views.zone_create, name='zone_create'),
    path('games/', views.games_list, name='games_list'),

    # الصفحات القديمة
    path('game-types/', views.game_types_list, name='game_types_list'),
    path('game-types/<int:pk>/edit/', views.game_type_update, name='game_type_update'),
    path('game-types/<int:pk>/delete/', views.game_type_delete, name='game_type_delete'),

    path('warehouses/', views.warehouses_list, name='warehouses_list'),
    path('warehouses/create/', views.warehouse_create, name='warehouse_create'),
    path('warehouses/<int:pk>/edit/', views.warehouse_update, name='warehouse_update'),
    path('warehouses/<int:pk>/delete/', views.warehouse_delete, name='warehouse_delete'),

    path('test-links/', test_links_view, name='test_links'),

    # إجراءات CRUD (مبدئية لتفادي NoReverseMatch)
    path('games/create/', views.game_create, name='game_create'),
    path('game-types/create/', views.game_type_create, name='game_type_create'),

    # CRUD للفنادق والمناطق
    path('hotels/<int:pk>/edit/', views.hotel_update, name='hotel_update'),
    path('hotels/<int:pk>/delete/', views.hotel_delete, name='hotel_delete'),
    path('zones/<int:pk>/edit/', views.zone_update, name='zone_update'),
    path('zones/<int:pk>/delete/', views.zone_delete, name='zone_delete'),

    # API endpoints
    path('api/dashboard-stats/', api_views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/revenue-chart/', api_views.revenue_chart_api, name='revenue_chart_api'),
    path('api/zone-revenue-distribution/', api_views.zone_revenue_distribution_api, name='zone_revenue_distribution_api'),
    path('api/recent-activities/', api_views.recent_activities_api, name='recent_activities_api'),
]
