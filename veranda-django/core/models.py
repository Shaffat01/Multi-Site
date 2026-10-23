from django.db import models

class HomeContent(models.Model):
    # Hero Section
    hero_title = models.CharField(max_length=255)
    hero_description = models.TextField()
    
    # Welcome Section
    welcome_title = models.CharField(max_length=255)
    welcome_subtitle = models.CharField(max_length=255)
    welcome_text = models.TextField()
    welcome_image = models.ImageField(upload_to='home_images/')


    def __str__(self):
        return "Home Page Content"
        
class Inquiry(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    event_type = models.CharField(max_length=50)
    event_date = models.DateField()
    message = models.TextField()
    status = models.CharField(max_length=20, default='New') # New, Contacted, Completed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.event_type}"

class Testimonial(models.Model):
    client_name = models.CharField(max_length=100)
    event_type = models.CharField(max_length=100, help_text="e.g., Wedding, Sweet 16")
    content = models.TextField()
    stars = models.IntegerField(default=5) # ১ থেকে ৫ এর মধ্যে
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_name} - {self.event_type}"