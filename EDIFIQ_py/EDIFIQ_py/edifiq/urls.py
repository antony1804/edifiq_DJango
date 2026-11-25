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
    path('apartamentos/<int:pk>/info-modal/', views.apartamento_ver_modal, name='apartamento_ver_modal'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'administrador')

role_patterns_admin = ([
    path('', views.dashboard_administrador, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/toggle-estado/', views.toggle_estado_view, name='toggle_estado'),
    path('modulo/<slug:slug>/<str:pk>/salida/', views.asignacion_salida_view, name='asignacion_salida'),
    path('modulo/<slug:slug>/<str:pk>/reasignar/', views.asignacion_reasignar_view, name='asignacion_reasignar'),
    path('modulo/<slug:slug>/<str:pk>/entregar/', views.paquete_entregar_view, name='paquete_entregar'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('apartamentos/<int:pk>/info-modal/', views.apartamento_ver_modal, name='apartamento_ver_modal'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'administrador')

role_patterns_vigilante = ([
    path('', views.dashboard_vigilante, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/toggle-estado/', views.toggle_estado_view, name='toggle_estado'),
    path('modulo/<slug:slug>/<str:pk>/salida/', views.asignacion_salida_view, name='asignacion_salida'),
    path('modulo/<slug:slug>/<str:pk>/reasignar/', views.asignacion_reasignar_view, name='asignacion_reasignar'),
    path('modulo/<slug:slug>/<str:pk>/entregar/', views.paquete_entregar_view, name='paquete_entregar'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('apartamentos/<int:pk>/info-modal/', views.apartamento_ver_modal, name='apartamento_ver_modal'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'vigilante')

role_patterns_residente = ([
    path('', views.dashboard_residente, name='dashboard'),
    path('modulo/<slug:slug>/', views.module_view, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_view, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_view, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/toggle-estado/', views.toggle_estado_view, name='toggle_estado'),
    path('modulo/<slug:slug>/<str:pk>/salida/', views.asignacion_salida_view, name='asignacion_salida'),
    path('modulo/<slug:slug>/<str:pk>/reasignar/', views.asignacion_reasignar_view, name='asignacion_reasignar'),
    path('modulo/<slug:slug>/<str:pk>/entregar/', views.paquete_entregar_view, name='paquete_entregar'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_view, name='delete'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_pdf, name='reporte_pdf'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle, name='apartamento_detalle'),
    path('apartamentos/<int:pk>/info-modal/', views.apartamento_ver_modal, name='apartamento_ver_modal'),
    path('torres/generacion-masiva/', views.torre_masiva, name='torre_masiva'),
], 'residente')

urlpatterns = [
    path('', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('salir/', views.logout_view, name='logout'),

    # Vistas separadas por rol (prefijo completo)
    path('administrador/', include(role_patterns_admin, namespace='administrador')),
    path('vigilante/', include(role_patterns_vigilante, namespace='vigilante')),
    path('residente/', include(role_patterns_residente, namespace='residente')),

    # Compatibilidad: rutas genÃ©ricas redirigen segÃºn rol
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('torres/generacion-masiva/', views.dashboard_redirect, name='torre_masiva'),
    path('apartamentos/<int:pk>/', views.apartamento_detalle_redirect, name='apartamento_detalle'),
    path('apartamentos/<int:pk>/info-modal/', views.apartamento_ver_modal_redirect, name='apartamento_ver_modal'),
    path('modulo/<slug:slug>/reporte.pdf', views.reporte_redirect, name='reporte_pdf'),
    path('modulo/<slug:slug>/', views.module_redirect, name='module'),
    path('modulo/<slug:slug>/nuevo/', views.create_redirect, name='create'),
    path('modulo/<slug:slug>/<str:pk>/editar/', views.edit_redirect, name='edit'),
    path('modulo/<slug:slug>/<str:pk>/toggle-estado/', views.toggle_estado_redirect, name='toggle_estado'),
    path('modulo/<slug:slug>/<str:pk>/salida/', views.asignacion_salida_redirect, name='asignacion_salida'),
    path('modulo/<slug:slug>/<str:pk>/reasignar/', views.asignacion_reasignar_redirect, name='asignacion_reasignar'),
    path('modulo/<slug:slug>/<str:pk>/entregar/', views.paquete_entregar_redirect, name='paquete_entregar'),
    path('modulo/<slug:slug>/<str:pk>/eliminar/', views.delete_redirect, name='delete'),
]
