from django.contrib import admin
from .models import Service, Application, Profile, Complaint

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_applications', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('service', 'user', 'full_name', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'service')
    search_fields = ('full_name', 'aadhar_number', 'user__username', 'service__name')
    ordering = ('-created_at',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'aadhar_number')
    search_fields = ('user__username', 'phone_number', 'aadhar_number')
    list_filter = ('user__date_joined',)

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'subject', 'status', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('user__username', 'subject', 'description', 'location')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
