import os
from pathlib import Path
from django.templatetags.static import static
import dj_database_url

# root-directory
BASE_DIR = Path(__file__).resolve().parent.parent

# security
SECRET_KEY = 'django-insecure-your-secret-key-here'
DEBUG = False
ALLOWED_HOSTS = ['44.214.103.249','.vercel.app', '127.0.0.1', 'localhost']

# applications
INSTALLED_APPS = [
    'jazzmin',   
    # "unfold", 
    # "unfold.contrib.filters", 
    # "unfold.contrib.forms",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'veranda_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # আপনার templates ফোল্ডার
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'veranda_project.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        # Fallback to local SQLite if DATABASE_URL is not set
        default=os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        # Only require SSL if NOT using SQLite (e.g., on production/Postgres)
        ssl_require=not os.environ.get('DATABASE_URL', '').startswith('sqlite') and os.environ.get('DATABASE_URL') is not None
    )
}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = 'admin_dashboard'
LOGOUT_REDIRECT_URL = 'login'


# UNFOLD = {
#     "SITE_TITLE": "Veranda Admin",
#     "SITE_SYMBOL": "speed", # Material Symbols থেকে আইকন
#     "site_title": "Veranda Admin",
#     "site_header": "Veranda",
#     "site_brand": "Veranda Administration", 
    
#     "COLORS": {
#         "primary": {
#             "50": "250 245 239",
#             "100": "241 230 216",
#             "200": "225 201 172",
#             "300": "202 165 120",
#             "400": "184 135 83",
#             "500": "166 110 58", 
#             "600": "141 87 47",
#             "700": "114 67 40",
#             "800": "94 56 36",
#             "900": "79 48 32",
#             "950": "44 25 16",
#         },
#     },
#     "SIDEBAR": {
#         "show_search": True,
#         "show_all_applications": True,
#     },

#     "TABS": [
#     {
#         "models": ["core.homecontent", "core.inquiry", "core.testimonial"],
#         "items": [
#             {"title": "Overview", "link": "admin:index", "icon": "dashboard"},
#             {"title": "Booking Request", "link": "admin:core_inquiry_changelist", "icon": "mail"},
#         ],
#     },
# ],
# }




JAZZMIN_SETTINGS = {
    "site_header": "Veranda",
    "site_logo": "images/Veranda Logo/Logo.jpg", 

    "copyright": "Veranda Event Venue",

    "welcome_sign": "Welcome to Veranda Dashboard",

    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Visit Website", "url": "/", "new_window": True},
    ],

    "usermenu_links": [
        {"name": "Support", "url": "https://github.com/farridav/django-jazzmin/issues", "new_window": True},
        {"model": "auth.user"}
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "solar",
    "dark_mode_theme": "darkly",

    "navbar": "navbar-dark",
    "brand_colour": "navbar-primary",
    "sidebar": "sidebar-dark-warning",
    "no_navbar_border": True,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}