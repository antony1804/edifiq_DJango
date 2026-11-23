import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-edifiq-dev-key'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
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
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'edifiq.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
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
# no creen ni alteren tablas de negocio. Solo deben migrarse contrib y usuarios.
MIGRATION_MODULES = {
    'core': None,
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
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
TEST_RUNNER = 'edifiq.test_runner.SchemaManagedTestRunner'


