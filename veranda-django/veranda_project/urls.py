from django.contrib import admin
from django.urls import path, include  # include ইমপোর্ট করা হয়েছে
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core.views import CustomLoginView
from core import views

admin.site.site_header = "Veranda Admin"
admin.site.site_title = "Veranda Dashboard"
admin.site.index_title = "Welcome to Veranda Manager"

urlpatterns = [
    path('', views.index, name='home'),
    path('about/', views.about, name='about'),
    path('weddings/', views.weddings, name='weddings'),
    path('events/', views.social_events, name='events'),
    path('corporate/', views.corporate, name='corporate'),
    path('gallery/', views.gallery, name='gallery'),
    path('floor-plans/', views.floor_plans, name='floor_plans'),
    path('faq/', views.faq, name='faq'),
    path('contact/', views.contact, name='contact'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)