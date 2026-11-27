import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-edifiq-dev-key'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']

INSTALLED_APPS = [
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.core',
    'apps.personas',
    'apps.usuarios',
    'apps.residentes',
    'apps.visitas',
    'apps.paquetes',
    'apps.reservas',
    'apps.recibos',
    'apps.legado',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'apps.core.schema_auth.SchemaAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.NoStoreAuthenticatedCacheMiddleware',
]

ROOT_URLCONF = 'edifiq.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'edifiq.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'edifiq'),
        'USER': os.environ.get('DB_USER', 'antony'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'ant2613z'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3308'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
    'legado': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'edifiq_legado.sqlite3',
    },
}

# Las tablas de negocio y esquema mapeadas son managed=False y fuente de verdad externa.
# Se deshabilitan sus migraciones históricas (stubs no-op) para que migrate/showmigrations
# no creen ni alteren tablas de negocio.
MIGRATION_MODULES = {
    'core': None,
    'usuarios': None,
    'personas': 'edifiq.test_migrations.personas',
    'residentes': 'edifiq.test_migrations.residentes',
    'visitas': 'edifiq.test_migrations.visitas',
    'paquetes': 'edifiq.test_migrations.paquetes',
    'reservas': 'edifiq.test_migrations.reservas',
    'recibos': 'edifiq.test_migrations.recibos',
    'legado': 'edifiq.test_migrations.legado',
}

AUTH_PASSWORD_VALIDATORS = []
DATABASE_ROUTERS = ['apps.legado.router.LegacyRouter']
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_ROOT = BASE_DIR / 'private_media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
TEST_RUNNER = 'edifiq.test_runner.SchemaManagedTestRunner'

# Autenticación y sesión basadas solo en tablas originales del esquema (sin auth_user, django_session, usuarios_perfil).
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').strip().lower() in ('1', 'true', 'yes', 'on')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'webmaster@localhost')
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '15'))

