

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()
    ats_score = models.IntegerField(default=0)
    analyzed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ResumeTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    preview_image = models.CharField(max_length=255)  # image path
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

from django.db import models
from django.contrib.auth.models import User

class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    mobile = models.CharField(max_length=15)
    linkedin = models.URLField(blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True, null=True)

    career_objective = models.TextField()

   
    edu_qualification = models.TextField()
    edu_year = models.TextField()
    edu_college = models.TextField()
    edu_university = models.TextField()
    edu_cgpa = models.TextField()
    edu_class = models.TextField()

    achievements = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    languages = models.TextField(blank=True)
    skills = models.TextField()
    projects = models.TextField(blank=True)
    hobbies = models.TextField(blank=True)

    ats_score = models.IntegerField(default=0)
    analyzed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name