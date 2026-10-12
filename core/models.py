from django.db import models
from django.contrib.auth.models import User
from .validators import validate_complaint_attachment

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    requirements = models.TextField(blank=True, help_text="Documents or criteria required for the service.")
    benefits = models.TextField(blank=True, help_text="Benefits provided by the service.")
    created_at = models.DateTimeField(auto_now_add=True)
    max_applications = models.PositiveIntegerField(default=1, help_text="Maximum applications per user for this service.")

    def __str__(self):
        return self.name


class Application(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_APPROVED = 'Approved'
    STATUS_REJECTED = 'Rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=100)
    aadhar_number = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True, null=True, help_text="Required when application is rejected")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['service', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.service.name}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    aadhar_number = models.CharField(max_length=12, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Complaint(models.Model):
    CATEGORY_CHOICES = [
        ('infrastructure', 'Infrastructure'),
        ('sanitation', 'Sanitation'),
        ('water', 'Water Supply'),
        ('electricity', 'Electricity'),
        ('road', 'Road Issues'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.FileField(
        upload_to='complaints/',
        null=True,
        blank=True,
        validators=[validate_complaint_attachment]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.subject} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-created_at']),
        ]


class ElectedPosition(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    term_length = models.PositiveIntegerField(help_text="Term length in years")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class VotingSession(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    position = models.ForeignKey(ElectedPosition, on_delete=models.CASCADE, related_name='voting_sessions')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_voting_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date']),
        ]


class Candidate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidacies')
    voting_session = models.ForeignKey(VotingSession, on_delete=models.CASCADE, related_name='candidates')
    candidate_name = models.CharField(max_length=255, blank=True, null=True, help_text="Candidate's display name (optional)")
    bio = models.TextField()
    experience = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        name = self.candidate_name or self.user.get_full_name() or self.user.username
        return f"{name} - {self.voting_session.title}"

    def get_display_name(self):
        return self.candidate_name or self.user.get_full_name() or self.user.username

    class Meta:
        unique_together = ['user', 'voting_session']


class Vote(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='votes')
    voting_session = models.ForeignKey(VotingSession, on_delete=models.CASCADE, related_name='session_votes')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='received_votes')
    voted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.voter.username} voted in {self.voting_session.title}"

    class Meta:
        unique_together = ['voter', 'voting_session']


class ElectedMember(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    position = models.ForeignKey(ElectedPosition, on_delete=models.CASCADE)
    voting_session = models.ForeignKey(VotingSession, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('resigned', 'Resigned'),
            ('terminated', 'Terminated')
        ],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.position.name}"


class MongoDBServiceApplication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service_id = models.CharField(max_length=100)
    service_name = models.CharField(max_length=255)
    service_category = models.CharField(max_length=100)
    full_name = models.CharField(max_length=100)
    aadhar_number = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(
        max_length=20,
        default='Pending',
        choices=[
            ('Pending', 'Pending'),
            ('Approved', 'Approved'),
            ('Rejected', 'Rejected')
        ]
    )
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.service_name} ({self.status})"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('login_success', 'Login Success'),
        ('login_failure', 'Login Failure'),
        ('register', 'User Registered'),
        ('app_status_update', 'Application Status Updated'),
        ('complaint_status_update', 'Complaint Status Updated'),
        ('complaint_delete', 'Complaint Deleted'),
        ('service_create', 'Service Created'),
        ('service_delete', 'Service Deleted'),
        ('voting_session_status', 'Voting Session Status Changed'),
        ('vote_cast', 'Vote Cast'),
        ('permission_denied', 'Permission Denied'),
    ]

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50, blank=True, null=True)
    target_id = models.CharField(max_length=50, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['actor']),
        ]

    def __str__(self):
        username = self.actor.username if self.actor else 'Anonymous/System'
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {username} - {self.action}"

    @classmethod
    def log(cls, request, action, target_type='', target_id='', details=''):
        ip = None
        actor = None
        if request:
            if hasattr(request, 'user') and request.user.is_authenticated:
                actor = request.user
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')

        return cls.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else '',
            ip_address=ip,
            details=details,
        )