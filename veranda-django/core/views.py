from django.shortcuts import render
from .models import HomeContent, Testimonial
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from .models import Inquiry
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy


def contact(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        event_type = request.POST.get('eventType') 
        event_date = request.POST.get('date')     
        message = request.POST.get('message')

        Inquiry.objects.create(
            name=name, email=email, phone=phone,
            event_type=event_type, event_date=event_date, message=message
        )
        return render(request, 'contact.html', {'success': True})
    
    return render(request, 'contact.html')


class CustomLoginView(LoginView):
    template_name = 'admin/login.html' 
    
    def get_success_url(self):
        return reverse_lazy('admin_dashboard')

def index(request):
    content = HomeContent.objects.first()
    testimonials = Testimonial.objects.all().order_by('-created_at')
    
    context = {
        'content': content,
        'testimonials': testimonials
    }
    return render(request, 'index.html', context)

def about(request):
    return render(request, 'about.html')

def weddings(request):
    return render(request, 'weddings.html')

def social_events(request):
    return render(request, 'social-events.html')

def corporate(request):
    return render(request, 'corporate.html')

def gallery(request):
    return render(request, 'gallery.html')

def floor_plans(request):
    return render(request, 'floor-plans.html')

def faq(request):
    return render(request, 'faq.html')

def contact(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        event_type = request.POST.get('eventType') 
        event_date = request.POST.get('date')     
        message = request.POST.get('message')

        Inquiry.objects.create(
            name=name, email=email, phone=phone,
            event_type=event_type, event_date=event_date, message=message
        )
        return render(request, 'contact.html', {'success': True})
    
    return render(request, 'contact.html')


class CustomLoginView(LoginView):
    template_name = 'login.html' # CHANGED: Removed 'admin/' prefix
    
    def get_success_url(self):
        return reverse_lazy('admin_dashboard')

# ... other views ...

@login_required
def admin_dashboard(request):
    all_inquiries = Inquiry.objects.all().order_by('-created_at')
    context = {
        'inquiries': all_inquiries,
        'total_count': all_inquiries.count(),
        'new_count': Inquiry.objects.filter(status='New').count(),
    }
    # CHANGED: Removed 'admin/' prefix
    return render(request, 'admin_dashboard.html', context)