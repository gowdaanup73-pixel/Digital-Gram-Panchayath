from django.db import models
from django.contrib.auth.models import User

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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    aadhar_number = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending')
    rejection_reason = models.TextField(blank=True, null=True, help_text="Required when application is rejected")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.service.name}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
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

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.FileField(upload_to='complaints/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.subject} ({self.status})"

    class Meta:
        ordering = ['-created_at']

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
    position = models.ForeignKey(ElectedPosition, on_delete=models.CASCADE)
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
        # Use get_status_display() method from Django
        return f"{self.title} - {self.get_status_display()}"  # type: ignore

    class Meta:
        ordering = ['-created_at']

class Candidate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    voting_session = models.ForeignKey(VotingSession, on_delete=models.CASCADE)
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
        """Get the candidate's display name, falling back to user's full name or username"""
        return self.candidate_name or self.user.get_full_name() or self.user.username

    class Meta:
        unique_together = ['user', 'voting_session']

class Vote(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    voting_session = models.ForeignKey(VotingSession, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
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
    service_id = models.CharField(max_length=100)  # MongoDB ObjectId as string
    service_name = models.CharField(max_length=255)
    service_category = models.CharField(max_length=100)
    full_name = models.CharField(max_length=100)
    aadhar_number = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(max_length=20, default='Pending', 
                            choices=[('Pending', 'Pending'),
                                   ('Approved', 'Approved'),
                                   ('Rejected', 'Rejected')])
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.service_name} ({self.status})"