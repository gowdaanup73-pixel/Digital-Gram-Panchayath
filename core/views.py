import os
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponseNotAllowed
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    Profile, Application, Complaint, Service, MongoDBServiceApplication,
    ElectedPosition, VotingSession, Candidate, Vote, ElectedMember, AuditLog
)
from .forms import (
    CustomUserCreationForm, UserUpdateForm, ProfileUpdateForm,
    ComplaintForm, ServiceApplicationForm
)
from .decorators import is_officer, officer_required, citizen_required
from .throttling import is_rate_limited, record_failed_attempt, reset_attempts
from .validators import validate_complaint_attachment, validate_aadhar_number

logger = logging.getLogger(__name__)


# ==============================================================================
# Authentication Views
# ==============================================================================

def login_view(request):
    """
    Citizen login view with brute-force rate limiting and audit logging.
    """
    if request.user.is_authenticated:
        if is_officer(request.user):
            return redirect('officer_dashboard')
        return redirect('services')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()

        # Check rate limiting / brute force lockout
        if is_rate_limited(request, username):
            AuditLog.log(
                request=request,
                action='login_failure',
                target_type='User',
                target_id=username,
                details=f"Login blocked due to rate limit threshold for username '{username}'."
            )
            messages.error(request, 'Too many failed login attempts. Please wait 5 minutes before trying again.')
            return render(request, 'login.html', {
                'form': AuthenticationForm(),
                'next': request.GET.get('next', '')
            })

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            reset_attempts(request, username)

            AuditLog.log(
                request=request,
                action='login_success',
                target_type='User',
                target_id=str(user.id),
                details=f"User '{user.username}' logged in successfully as citizen."
            )
            messages.success(request, 'Login successful!')
            next_url = request.GET.get('next')
            if is_officer(user):
                return redirect(next_url or 'officer_dashboard')
            return redirect(next_url or 'services')
        else:
            attempts = record_failed_attempt(request, username)
            AuditLog.log(
                request=request,
                action='login_failure',
                target_type='User',
                target_id=username,
                details=f"Invalid login credentials for username '{username}' (Attempt {attempts})."
            )
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })


def officer_login(request):
    """
    Officer/Admin login view with strict role verification, rate limiting, and audit logging.
    """
    if request.user.is_authenticated and is_officer(request.user):
        return redirect('officer_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()

        if is_rate_limited(request, username):
            AuditLog.log(
                request=request,
                action='login_failure',
                target_type='Officer',
                target_id=username,
                details=f"Officer login blocked due to rate limit threshold for '{username}'."
            )
            messages.error(request, 'Too many failed login attempts. Please wait 5 minutes before trying again.')
            return render(request, 'officer_login.html', {'form': AuthenticationForm()})

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if is_officer(user):
                login(request, user)
                reset_attempts(request, username)
                AuditLog.log(
                    request=request,
                    action='login_success',
                    target_type='Officer',
                    target_id=str(user.id),
                    details=f"Officer '{user.username}' logged in successfully."
                )
                messages.success(request, f'Welcome back, Officer {user.username}!')
                next_url = request.GET.get('next')
                return redirect(next_url or 'officer_dashboard')
            else:
                record_failed_attempt(request, username)
                AuditLog.log(
                    request=request,
                    action='permission_denied',
                    target_type='Officer',
                    target_id=str(user.id),
                    details=f"User '{user.username}' attempted officer login without privileges."
                )
                form.add_error(None, 'Access Denied: You do not have officer/admin privileges.')
        else:
            record_failed_attempt(request, username)
            AuditLog.log(
                request=request,
                action='login_failure',
                target_type='Officer',
                target_id=username,
                details=f"Failed officer login attempt for '{username}'."
            )
    else:
        form = AuthenticationForm()

    return render(request, 'officer_login.html', {'form': form})


def register(request):
    """
    Citizen self-registration with strong password validation and privilege-escalation prevention.
    """
    if request.user.is_authenticated:
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            AuditLog.log(
                request=request,
                action='register',
                target_type='User',
                target_id=str(user.id),
                details=f"New citizen '{user.username}' registered successfully."
            )
            messages.success(request, 'Registration successful! You may now sign in.')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


def logout_view(request):
    """
    User logout view supporting both GET and POST with audit logging.
    """
    if request.user.is_authenticated:
        username = request.user.username
        AuditLog.log(
            request=request,
            action='login_success',
            target_type='User',
            target_id=str(request.user.id),
            details=f"User '{username}' logged out."
        )
        from django.contrib.auth import logout
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


# ==============================================================================
# Citizen Views
# ==============================================================================

@login_required(login_url='login')
def user_dashboard(request):
    """
    Citizen dashboard displaying only the authenticated user's applications and complaints.
    """
    applications = Application.objects.filter(user=request.user).select_related('service')
    complaints = Complaint.objects.filter(user=request.user).order_by('-created_at')
    services_list = Service.objects.all().order_by('-created_at')
    active_voting_sessions = VotingSession.objects.filter(
        status='active',
        end_date__gt=timezone.now()
    ).select_related('position')

    return render(request, 'user_dashboard.html', {
        'applications': applications,
        'complaints': complaints,
        'services': services_list,
        'active_voting_sessions': active_voting_sessions,
    })


@login_required(login_url='login')
def services(request):
    """List public services with search capability."""
    search_query = request.GET.get('q', '').strip()
    services_qs = Service.objects.all().order_by('-created_at')
    if search_query:
        services_qs = services_qs.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )
    return render(request, 'services.html', {
        'services': services_qs,
        'search_query': search_query,
    })


@login_required(login_url='login')
def apply_service(request, service_id):
    """
    Apply for a service with atomic duplicate prevention and quota checks.
    """
    service = get_object_or_404(Service, id=service_id)

    with transaction.atomic():
        total_applications = Application.objects.filter(service=service).count()
        if total_applications >= service.max_applications:
            messages.warning(
                request,
                f'The maximum number of applications for {service.name} has been reached.'
            )
            return render(request, 'apply_service.html', {'service': service})

        user_applications = Application.objects.filter(user=request.user, service=service).count()
        if user_applications >= 1:
            messages.warning(request, f'You have already applied for {service.name}.')
            return render(request, 'apply_service.html', {'service': service})

        if request.method == 'POST':
            form = ServiceApplicationForm(request.POST)
            if form.is_valid():
                app = Application.objects.create(
                    user=request.user,
                    service=service,
                    full_name=form.cleaned_data['full_name'],
                    aadhar_number=form.cleaned_data['aadhar_number'],
                    address=form.cleaned_data['address']
                )
                AuditLog.log(
                    request=request,
                    action='app_status_update',
                    target_type='Application',
                    target_id=str(app.id),
                    details=f"Application submitted for service '{service.name}'."
                )
                messages.success(request, 'Application submitted successfully!')
                return redirect('user_dashboard')
            else:
                messages.error(request, 'Please fix the errors in the application form.')
        else:
            form = ServiceApplicationForm()

    return render(request, 'apply_service.html', {'form': form, 'service': service})


@login_required(login_url='login')
def submit_complaint(request):
    """
    Submit a citizen complaint with file upload validation and size limits.
    """
    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        location = request.POST.get('location', '').strip()
        attachment = request.FILES.get('attachment')

        if not all([category, subject, description, location]):
            messages.error(request, 'Please fill all required fields.')
            return render(request, 'submit_complaint.html', {
                'categories': Complaint.CATEGORY_CHOICES
            })

        valid_categories = dict(Complaint.CATEGORY_CHOICES).keys()
        if category not in valid_categories:
            messages.error(request, 'Invalid complaint category.')
            return render(request, 'submit_complaint.html', {
                'categories': Complaint.CATEGORY_CHOICES
            })

        if attachment:
            try:
                validate_complaint_attachment(attachment)
            except Exception as e:
                messages.error(request, str(e))
                return render(request, 'submit_complaint.html', {
                    'categories': Complaint.CATEGORY_CHOICES
                })

        complaint = Complaint.objects.create(
            user=request.user,
            category=category,
            subject=subject,
            description=description,
            location=location,
            attachment=attachment
        )
        AuditLog.log(
            request=request,
            action='complaint_status_update',
            target_type='Complaint',
            target_id=str(complaint.id),
            details=f"Complaint #{complaint.id} ('{subject}') submitted."
        )
        messages.success(request, 'Your complaint has been submitted successfully.')
        return redirect('view_complaints')

    return render(request, 'submit_complaint.html', {
        'categories': Complaint.CATEGORY_CHOICES
    })


@login_required(login_url='login')
def view_complaints(request):
    """
    View only the authenticated citizen's complaints.
    """
    user_complaints = Complaint.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'view_complaints.html', {
        'complaints': user_complaints
    })


@login_required(login_url='login')
def profile(request, username=None):
    """
    Citizen and Officer profile view with strict IDOR access control.
    Citizens can ONLY view and edit their own profile.
    Officers can view other profiles.
    """
    if username:
        view_user = get_object_or_404(User, username=username)
        # IDOR prevention: Only officers or the user themselves may view
        if not is_officer(request.user) and request.user != view_user:
            AuditLog.log(
                request=request,
                action='permission_denied',
                target_type='User',
                target_id=username,
                details=f"Citizen '{request.user.username}' attempted unauthorized view of profile '{username}'."
            )
            return HttpResponseForbidden("You do not have permission to view this profile.")
    else:
        view_user = request.user

    profile_obj, _ = Profile.objects.get_or_create(user=view_user)
    can_edit = is_officer(request.user) or request.user == view_user

    if request.method == 'POST' and can_edit:
        u_form = UserUpdateForm(request.POST, instance=view_user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile_obj)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            prefix = "Your" if view_user == request.user else f"{view_user.username}'s"
            messages.success(request, f"{prefix} profile has been updated!")
            return redirect('view_profile', username=view_user.username) if username else redirect('profile')
        else:
            messages.error(request, 'Please correct the profile errors.')
    else:
        u_form = UserUpdateForm(instance=view_user)
        p_form = ProfileUpdateForm(instance=profile_obj)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'profile': profile_obj,
        'view_user': view_user,
        'can_edit': can_edit,
        'is_own_profile': request.user == view_user
    }
    return render(request, 'profile.html', context)


# ==============================================================================
# Officer / Admin Views
# ==============================================================================

@officer_required
def officer_dashboard(request):
    """
    Officer administrative dashboard with metric counts and recent complaints.
    """
    recent_complaints = Complaint.objects.all().order_by('-created_at')[:5]
    complaints_by_category = {
        'pending': Complaint.objects.filter(status='pending').count(),
        'in_progress': Complaint.objects.filter(status='in_progress').count(),
        'resolved': Complaint.objects.filter(status='resolved').count(),
    }
    context = {
        'recent_complaints': recent_complaints,
        'complaints_by_category': complaints_by_category,
        'total_applications': Application.objects.count(),
        'pending_applications': Application.objects.filter(status='Pending').count(),
    }
    return render(request, 'officer_dashboard.html', context)


@officer_required
def view_applications(request):
    """
    Officer view for reviewing, approving, and rejecting citizen applications.
    Strictly verifies status transitions and requires rejection reasons.
    """
    applications = Application.objects.select_related('user', 'service').all()

    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        action = request.POST.get('action')
        application = get_object_or_404(Application, id=app_id)

        if action == 'accept':
            application.status = Application.STATUS_APPROVED
            application.rejection_reason = ''
            application.save()
            AuditLog.log(
                request=request,
                action='app_status_update',
                target_type='Application',
                target_id=str(application.id),
                details=f"Application #{application.id} approved by Officer '{request.user.username}'."
            )
            messages.success(request, f'Application #{application.id} approved.')
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '').strip()
            if not rejection_reason:
                messages.error(request, 'Rejection reason is required when rejecting an application.')
                return redirect('view_applications')
            application.status = Application.STATUS_REJECTED
            application.rejection_reason = rejection_reason
            application.save()
            AuditLog.log(
                request=request,
                action='app_status_update',
                target_type='Application',
                target_id=str(application.id),
                details=f"Application #{application.id} rejected by Officer '{request.user.username}'. Reason: {rejection_reason}"
            )
            messages.success(request, f'Application #{application.id} rejected with reason provided.')
        else:
            messages.error(request, 'Invalid action specified.')

        return redirect('view_applications')

    return render(request, 'view_applications.html', {'applications': applications})


@officer_required
def manage_services(request):
    """Officer service listing and management."""
    services_qs = Service.objects.all().order_by('-created_at')
    return render(request, 'manage_services.html', {'services': services_qs})


@officer_required
def create_service(request):
    """Officer service creation with server-side validation."""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            max_applications = int(request.POST.get('max_applications', 1))

            if not name:
                messages.error(request, 'Service name is required.')
                return render(request, 'create_service.html')

            if not description:
                messages.error(request, 'Service description is required.')
                return render(request, 'create_service.html')

            if max_applications < 1:
                messages.error(request, 'Maximum applications must be at least 1.')
                return render(request, 'create_service.html')

            if Service.objects.filter(name__iexact=name).exists():
                messages.error(request, 'A service with this name already exists.')
                return render(request, 'create_service.html')

            service = Service.objects.create(
                name=name,
                description=description,
                max_applications=max_applications
            )
            AuditLog.log(
                request=request,
                action='service_create',
                target_type='Service',
                target_id=str(service.id),
                details=f"Service '{service.name}' created by Officer '{request.user.username}'."
            )
            messages.success(request, f'Service "{service.name}" created successfully!')
            return redirect('manage_services')

        except ValueError:
            messages.error(request, 'Please enter a valid number for maximum applications.')
            return render(request, 'create_service.html')
        except Exception:
            messages.error(request, 'An error occurred while creating the service.')
            return render(request, 'create_service.html')

    return render(request, 'create_service.html')


@officer_required
@require_POST
def delete_service(request, service_id):
    """
    Officer service deletion. Strictly requires POST to prevent CSRF/accidental deletion.
    """
    service = get_object_or_404(Service, id=service_id)
    service_name = service.name
    service.delete()
    AuditLog.log(
        request=request,
        action='service_delete',
        target_type='Service',
        target_id=str(service_id),
        details=f"Service '{service_name}' deleted by Officer '{request.user.username}'."
    )
    messages.success(request, f'Service "{service_name}" deleted successfully.')
    return redirect('manage_services')


@officer_required
def manage_complaints(request):
    """Officer complaints management and status progression."""
    complaints = Complaint.objects.all().order_by('-created_at')

    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '').strip()

        complaint = get_object_or_404(Complaint, id=complaint_id)
        if action in ['in_progress', 'resolved', 'rejected']:
            complaint.status = action
            if remarks:
                complaint.admin_remarks = remarks
            complaint.save()
            AuditLog.log(
                request=request,
                action='complaint_status_update',
                target_type='Complaint',
                target_id=str(complaint.id),
                details=f"Complaint #{complaint.id} status changed to '{action}' by Officer '{request.user.username}'."
            )
            messages.success(request, f'Complaint #{complaint.id} status updated to {action}.')
        else:
            messages.error(request, 'Invalid status transition.')

    return render(request, 'manage_complaints.html', {'complaints': complaints})


@officer_required
@require_POST
def update_complaint_status(request, complaint_id):
    """Dedicated endpoint to update complaint status with strict POST validation."""
    complaint = get_object_or_404(Complaint, id=complaint_id)
    status_val = request.POST.get('status')
    admin_remarks = request.POST.get('admin_remarks', '').strip()

    valid_statuses = [c[0] for c in Complaint.STATUS_CHOICES]
    if status_val not in valid_statuses:
        messages.error(request, 'Invalid complaint status choice.')
        return redirect('manage_complaints')

    complaint.status = status_val
    if admin_remarks:
        complaint.admin_remarks = admin_remarks
    complaint.save()

    AuditLog.log(
        request=request,
        action='complaint_status_update',
        target_type='Complaint',
        target_id=str(complaint.id),
        details=f"Complaint #{complaint.id} status updated to '{status_val}'."
    )
    messages.success(request, 'Complaint status updated successfully.')
    return redirect('manage_complaints')


@login_required(login_url='login')
@require_POST
def delete_complaint(request, complaint_id):
    """
    Complaint deletion.
    Allows officers, or the citizen owner if the complaint is still pending.
    Strictly requires POST to prevent CSRF / accidental deletion.
    """
    complaint = get_object_or_404(Complaint, id=complaint_id)

    # Permission check: officer or complaint owner (if pending)
    if not (is_officer(request.user) or (complaint.user == request.user and complaint.status == 'pending')):
        AuditLog.log(
            request=request,
            action='permission_denied',
            target_type='Complaint',
            target_id=str(complaint_id),
            details=f"Unauthorized delete attempt on Complaint #{complaint_id} by '{request.user.username}'."
        )
        return HttpResponseForbidden("You do not have permission to delete this complaint.")

    complaint.delete()
    AuditLog.log(
        request=request,
        action='complaint_delete',
        target_type='Complaint',
        target_id=str(complaint_id),
        details=f"Complaint #{complaint_id} deleted by '{request.user.username}'."
    )
    messages.success(request, 'Complaint deleted successfully.')
    if is_officer(request.user):
        return redirect('manage_complaints')
    return redirect('view_complaints')


# ==============================================================================
# Legacy Specialized Service Views (Backward-Compatible)
# ==============================================================================

@login_required(login_url='login')
def building_construction(request):
    service = Service.objects.filter(name__icontains='building').first()
    if not service:
        messages.warning(request, 'Building construction service not found.')
        return render(request, 'building_construction.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You already have a pending application for this service.')
        return render(request, 'building_construction.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        address = request.POST.get('address', '').strip()

        if full_name and aadhar_number and address:
            try:
                validate_aadhar_number(aadhar_number)
            except Exception as e:
                messages.error(request, str(e))
                return render(request, 'building_construction.html')

            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=address
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('building_construction')
        else:
            messages.error(request, 'All fields are required.')

    return render(request, 'building_construction.html')


@login_required(login_url='login')
def skill_equipment(request):
    service = Service.objects.filter(name__icontains='skill').first()
    if not service:
        messages.warning(request, 'Skill equipment service not found.')
        return render(request, 'skill_equipment.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You already have a pending application for this service.')
        return render(request, 'skill_equipment.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        skill_type = request.POST.get('skill_type', '').strip()

        if full_name and aadhar_number and skill_type:
            try:
                validate_aadhar_number(aadhar_number)
            except Exception as e:
                messages.error(request, str(e))
                return render(request, 'skill_equipment.html')

            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=skill_type
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('skill_equipment')
        else:
            messages.error(request, 'All fields are required.')

    return render(request, 'skill_equipment.html')


@login_required(login_url='login')
def bio_gas_plant(request):
    service = Service.objects.filter(name__icontains='bio').first()
    if not service:
        messages.warning(request, 'Bio-gas plant service not found.')
        return render(request, 'bio_gas_plant.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You already have a pending application for this service.')
        return render(request, 'bio_gas_plant.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        address = request.POST.get('address', '').strip()

        if full_name and aadhar_number and address:
            try:
                validate_aadhar_number(aadhar_number)
            except Exception as e:
                messages.error(request, str(e))
                return render(request, 'bio_gas_plant.html')

            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=address
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('bio_gas_plant')
        else:
            messages.error(request, 'All fields are required.')

    return render(request, 'bio_gas_plant.html')


# ==============================================================================
# Voting Views
# ==============================================================================

@login_required(login_url='login')
def voting_sessions(request):
    """List active, upcoming, and completed voting sessions."""
    current_time = timezone.now()

    active_sessions = VotingSession.objects.filter(
        start_date__lte=current_time,
        end_date__gte=current_time,
        status='active'
    ).order_by('end_date')

    upcoming_sessions = VotingSession.objects.filter(
        start_date__gt=current_time,
        status='pending'
    ).order_by('start_date')

    completed_sessions = VotingSession.objects.filter(status='completed').order_by('-end_date')

    completed_results = {}
    for session in completed_sessions:
        winner = Vote.objects.filter(voting_session=session)\
            .values('candidate')\
            .annotate(votes=Count('id'))\
            .order_by('-votes')\
            .first()
        if winner:
            try:
                cand = Candidate.objects.get(id=winner['candidate'])
                completed_results[session.pk] = {
                    'winner_name': cand.get_display_name(),
                    'votes': winner['votes']
                }
            except Candidate.DoesNotExist:
                pass

    voted_sessions = Vote.objects.filter(voter=request.user).values_list('voting_session_id', flat=True)
    user_candidacies = Candidate.objects.filter(user=request.user)

    return render(request, 'voting_sessions.html', {
        'active_sessions': active_sessions,
        'upcoming_sessions': upcoming_sessions,
        'completed_sessions': completed_sessions,
        'completed_results': completed_results,
        'voted_sessions': voted_sessions,
        'user_candidacies': user_candidacies,
    })


@login_required(login_url='login')
def vote(request, session_id):
    """
    Cast vote with atomic transaction and double-vote prevention.
    """
    voting_session = get_object_or_404(VotingSession, id=session_id)

    if request.method == 'POST':
        now = timezone.now()
        if voting_session.status != 'active' or now < voting_session.start_date or now > voting_session.end_date:
            messages.error(request, 'This voting session is not currently active.')
            return redirect('voting_sessions')

        candidate_id = request.POST.get('candidate')
        if not candidate_id:
            messages.error(request, 'Please select a candidate.')
            return redirect('vote', session_id=session_id)

        candidate = get_object_or_404(
            Candidate,
            id=candidate_id,
            voting_session=voting_session,
            approved=True
        )

        with transaction.atomic():
            if Vote.objects.filter(voter=request.user, voting_session=voting_session).exists():
                messages.error(request, 'You have already voted in this session.')
                return redirect('voting_sessions')

            Vote.objects.create(
                voter=request.user,
                voting_session=voting_session,
                candidate=candidate
            )
            AuditLog.log(
                request=request,
                action='vote_cast',
                target_type='VotingSession',
                target_id=str(voting_session.id),
                details=f"Citizen '{request.user.username}' cast vote in session #{voting_session.id}."
            )

        messages.success(request, 'Your vote has been recorded successfully.')
        return redirect('voting_sessions')

    candidates = Candidate.objects.filter(voting_session=voting_session, approved=True).select_related('user')
    return render(request, 'cast_vote.html', {'voting_session': voting_session, 'candidates': candidates})


@login_required(login_url='login')
def apply_candidacy(request, session_id):
    """Citizen candidacy application for an upcoming session."""
    voting_session = get_object_or_404(VotingSession, id=session_id)

    if timezone.now() >= voting_session.start_date:
        messages.error(request, 'The candidacy application period for this position has ended.')
        return redirect('voting_sessions')

    if request.method == 'POST':
        candidate_name = request.POST.get('candidate_name', '').strip()
        bio = request.POST.get('bio', '').strip()
        experience = request.POST.get('experience', '').strip()

        if not bio or not experience:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('apply_candidacy', session_id=session_id)

        if Candidate.objects.filter(user=request.user, voting_session=voting_session).exists():
            messages.error(request, 'You have already applied for this position.')
            return redirect('voting_sessions')

        Candidate.objects.create(
            user=request.user,
            voting_session=voting_session,
            candidate_name=candidate_name if candidate_name else None,
            bio=bio,
            experience=experience
        )
        messages.success(request, 'Your candidacy application has been submitted successfully.')
        return redirect('voting_sessions')

    return render(request, 'apply_candidacy.html', {'voting_session': voting_session})


def roles_responsibilities(request):
    """Public portal listing active elected members and their roles."""
    elected_members = ElectedMember.objects.filter(
        status='active'
    ).select_related('user', 'position').order_by('position__name')

    return render(request, 'roles_responsibilities.html', {
        'elected_members': elected_members
    })
