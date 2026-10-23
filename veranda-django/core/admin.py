from django.contrib import admin
from .models import HomeContent
from .models import Inquiry
from .models import Testimonial

@admin.register(HomeContent)
class HomeContentAdmin(admin.ModelAdmin):
    list_display = ('hero_title', 'welcome_title')

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'event_type', 'event_date', 'status')
    search_fields = ('name', 'email')
    list_filter = ('status', 'event_type')
    
@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'event_type', 'stars')