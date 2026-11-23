from django.contrib import admin
from django.urls import include, path

from apps.core import views

role_patterns = ([
    path('', views.dashboard_administrador, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'administrador')

role_patterns_admin = ([
    path('', views.dashboard_administrador, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'administrador')

role_patterns_vigilante = ([
    path('', views.dashboard_vigilante, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'vigilante')

role_patterns_residente = ([
    path('', views.dashboard_residente, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'residente')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('salir/', views.logout_view, name='logout'),

    # Vistas separadas por rol (prefijo completo)
    path('administrador/', include(role_patterns_admin, namespace='administrador')),
    path('vigilante/', include(role_patterns_vigilante, namespace='vigilante')),
    path('residente/', include(role_patterns_residente, namespace='residente')),

    # Compatibilidad: rutas genéricas redirigen según rol
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('torres/generacion-masiva/', views.dashboard_redirect, name='torre_masiva'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle_redirect, name='apartamento_detalle'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_redirect, name='reporte_pdf'),
    path('modulo/<slug:slug>/', views.module_redirect, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_redirect, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_redirect, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_redirect, name='delete'),
]
