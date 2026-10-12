from django.contrib import admin
from .models import (
    Service, Application, Profile, Complaint, AuditLog,
    VotingSession, Candidate, Vote, ElectedPosition, ElectedMember
)

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

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor', 'action', 'target_type', 'target_id', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('actor__username', 'target_type', 'target_id', 'details', 'ip_address')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'actor', 'action', 'target_type', 'target_id', 'ip_address', 'details')

@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'status', 'start_date', 'end_date', 'created_by')
    list_filter = ('status', 'position')
    search_fields = ('title', 'description')

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('user', 'candidate_name', 'voting_session', 'approved')
    list_filter = ('approved', 'voting_session')
    search_fields = ('user__username', 'candidate_name', 'bio')

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('voter', 'voting_session', 'candidate', 'voted_at')
    list_filter = ('voting_session',)
    readonly_fields = ('voter', 'voting_session', 'candidate', 'voted_at')

@admin.register(ElectedPosition)
class ElectedPositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'term_length', 'created_at')

@admin.register(ElectedMember)
class ElectedMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'position', 'voting_session', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'position')
