from django.urls import path
from . import views

urlpatterns = [
    # Ingestion endpoints
    path('sessions/start/', views.start_session_view, name='start_session'),
    path('performance/', views.performance_metric_view, name='performance_metric'),
    path('thread-analysis/', views.thread_analysis_view, name='thread_analysis'),
    path('worker-thread/', views.worker_thread_view, name='worker_thread'),
    path('memory/', views.memory_metric_view, name='memory_metric'),
    path('network/', views.network_metric_view, name='network_metric'),
    path('errors/', views.error_log_view, name='error_log'),
    path('activity/', views.user_activity_view, name='user_activity'),
    path('telemetry/batch/', views.batch_telemetry_view, name='batch_telemetry'),

    # Analytics Dashboard endpoints
    path('dashboard/overview/', views.dashboard_overview_view, name='dashboard_overview'),
    path('dashboard/threads/', views.dashboard_threads_view, name='dashboard_threads'),
    path('dashboard/memory/', views.dashboard_memory_view, name='dashboard_memory'),
    path('dashboard/network/', views.dashboard_network_view, name='dashboard_network'),
    path('dashboard/errors/', views.dashboard_errors_view, name='dashboard_errors'),
    path('dashboard/ai-predictions/', views.dashboard_ai_predictions_view, name='dashboard_ai_predictions'),
    path('dashboard/session-replay/', views.dashboard_session_replay_view, name='dashboard_session_replay'),
    path('dashboard/browser-comparison/', views.dashboard_browser_comparison_view, name='dashboard_browser_comparison'),

    # Demo Seed endpoint
    path('dashboard/seed-demo-data/', views.seed_demo_data_view, name='seed_demo_data'),
]
