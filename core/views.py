# User dashboard for service tracking
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import (
    Profile, Application, Complaint, Service, MongoDBServiceApplication,
    ElectedPosition, VotingSession, Candidate, Vote, ElectedMember
)
from .forms import CustomUserCreationForm, UserUpdateForm, ProfileUpdateForm

def is_admin(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_admin, login_url='login')
def manage_services(request):
    services = Service.objects.all().order_by('-created_at')
    return render(request, 'manage_services.html', {'services': services})

@user_passes_test(is_admin, login_url='login')
def create_service(request):
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            max_applications = int(request.POST.get('max_applications', 1))
            
            # Validate form data
            if not name:
                messages.error(request, 'Service name is required.')
                return render(request, 'create_service.html')
            
            if not description:
                messages.error(request, 'Service description is required.')
                return render(request, 'create_service.html')
            
            if max_applications < 1:
                messages.error(request, 'Maximum applications must be at least 1.')
                return render(request, 'create_service.html')
            
            # Check if service with same name already exists
            if Service.objects.filter(name__iexact=name).exists():
                messages.error(request, 'A service with this name already exists.')
                return render(request, 'create_service.html')
            
            # Create the service
            service = Service.objects.create(
                name=name,
                description=description,
                max_applications=max_applications
            )
            
            messages.success(request, f'Service "{service.name}" was created successfully!')
            return redirect('manage_services')
            
        except ValueError:
            messages.error(request, 'Please enter a valid number for maximum applications.')
            return render(request, 'create_service.html')
        except Exception as e:
            messages.error(request, f'An error occurred while creating the service. Please try again.')
            return render(request, 'create_service.html')
    
    return render(request, 'create_service.html')

@login_required(login_url='login')
def user_dashboard(request):
    applications = Application.objects.filter(user=request.user).select_related('service')
    # Only show resolved complaints to users
    complaints = Complaint.objects.filter(
        user=request.user,
        status='resolved'
    ).order_by('-updated_at')
    # Get all available services for users to apply
    services = Service.objects.all().order_by('-created_at')
    # Get active voting sessions
    active_voting_sessions = VotingSession.objects.filter(
        status='active',
        end_date__gt=timezone.now()
    ).select_related('position')
    return render(request, 'user_dashboard.html', {
        'applications': applications,
        'complaints': complaints,
        'services': services,
        'active_voting_sessions': active_voting_sessions,
    })

@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def delete_service(request, service_id):
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    service = get_object_or_404(Service, id=service_id)
    service.delete()
    messages.success(request, 'Service deleted successfully.')
    return redirect('manage_services')

# Officer: View Applications
@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def view_applications(request):
    from django.shortcuts import get_object_or_404
    from django.contrib import messages
    applications = Application.objects.select_related('user', 'service').all()
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        action = request.POST.get('action')
        application = get_object_or_404(Application, id=app_id)
        if action == 'accept':
            application.status = 'Approved'
            messages.success(request, 'Application approved.')
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason')
            if not rejection_reason:
                messages.error(request, 'Rejection reason is required.')
                return redirect('view_applications')
            application.status = 'Rejected'
            application.rejection_reason = rejection_reason
            messages.success(request, 'Application rejected with reason provided.')
        application.save()
        return redirect('view_applications')
    return render(request, 'view_applications.html', {'applications': applications})
def officer_login(request):
	if request.method == 'POST':
		form = AuthenticationForm(request, data=request.POST)
		if form.is_valid():
			user = form.get_user()
			if user.is_superuser:
				login(request, user)
				return redirect('officer_dashboard')
			else:
				form.add_error(None, 'You do not have officer/admin privileges.')
	else:
		form = AuthenticationForm()
	return render(request, 'officer_login.html', {'form': form})
# Import user_passes_test at the top
from django.contrib.auth.decorators import user_passes_test, login_required
# Officer/Admin dashboard view
@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def officer_dashboard(request):
    # Get recent complaints (last 5)
    recent_complaints = Complaint.objects.all().order_by('-created_at')[:5]
    # Get complaints count by category
    complaints_by_category = {
        'pending': Complaint.objects.filter(status='pending').count(),
        'in_progress': Complaint.objects.filter(status='in_progress').count(),
        'resolved': Complaint.objects.filter(status='resolved').count(),
    }
    context = {
        'recent_complaints': recent_complaints,
        'complaints_by_category': complaints_by_category,
    }
    return render(request, 'officer_dashboard.html', context)

@login_required(login_url='login')
def submit_complaint(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        subject = request.POST.get('subject')
        description = request.POST.get('description')
        location = request.POST.get('location')
        attachment = request.FILES.get('attachment')

        if all([category, subject, description, location]):
            complaint = Complaint.objects.create(
                user=request.user,
                category=category,
                subject=subject,
                description=description,
                location=location,
                attachment=attachment
            )
            messages.success(request, 'Your complaint has been submitted successfully.')
            return redirect('view_complaints')
        else:
            messages.error(request, 'Please fill all required fields.')
    
    return render(request, 'submit_complaint.html', {
        'categories': Complaint.CATEGORY_CHOICES
    })

@login_required(login_url='login')
def view_complaints(request):
    user_complaints = Complaint.objects.filter(user=request.user)
    return render(request, 'view_complaints.html', {
        'complaints': user_complaints
    })

@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def manage_complaints(request):
    complaints = Complaint.objects.all()
    
    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        action = request.POST.get('action')
        remarks = request.POST.get('remarks')
        
        complaint = get_object_or_404(Complaint, id=complaint_id)
        if action in ['in_progress', 'resolved', 'rejected']:
            complaint.status = action
            if remarks:
                complaint.admin_remarks = remarks
            complaint.save()
            messages.success(request, f'Complaint status updated to {action}.')
        
    return render(request, 'manage_complaints.html', {
        'complaints': complaints
    })

@user_passes_test(lambda u: u.is_superuser, login_url='officer_login')
def update_complaint_status(request, complaint_id):
    if request.method == 'POST':
        try:
            complaint = Complaint.objects.get(id=complaint_id)
            complaint.status = request.POST['status']
            complaint.admin_remarks = request.POST['admin_remarks']
            complaint.save()
            messages.success(request, 'Complaint status updated successfully.')
        except Complaint.DoesNotExist:
            messages.error(request, 'Complaint not found.')
        except Exception as e:
            messages.error(request, 'Error updating complaint status.')
    return redirect('manage_complaints')

@login_required(login_url='login')
def profile(request, username=None):
    from django.shortcuts import get_object_or_404
    from django.contrib.auth.models import User
    from django.http import HttpResponseForbidden

    if username:
        # Viewing someone else's profile
        view_user = get_object_or_404(User, username=username)
        if not request.user.is_superuser and request.user != view_user:
            return HttpResponseForbidden("You don't have permission to view this profile.")
    else:
        # Viewing own profile
        view_user = request.user

    try:
        profile = getattr(view_user, 'profile', None)
        if not profile:
            profile = Profile.objects.create(user=view_user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=view_user)

    can_edit = request.user.is_superuser or request.user == view_user

    if request.method == 'POST' and can_edit:
        u_form = UserUpdateForm(request.POST, instance=view_user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            # Build the message prefix separately to avoid backslashes inside f-string expressions
            prefix = "Your" if view_user == request.user else f"{view_user.username}'s"
            messages.success(request, f"{prefix} profile has been updated!")
            return redirect('view_profile', username=view_user.username) if username else redirect('profile')
    else:
        u_form = UserUpdateForm(instance=view_user)
        p_form = ProfileUpdateForm(instance=profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'profile': profile,
        'view_user': view_user,
        'can_edit': can_edit,
        'is_own_profile': request.user == view_user
    }
    return render(request, 'profile.html', context)

def login_view(request):
    from django.contrib import messages
    from django.views.decorators.csrf import ensure_csrf_cookie
    from django.utils.decorators import method_decorator

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Login successful!')
            next_url = request.GET.get('next')
            # If officer, redirect to officer dashboard
            if user.is_superuser:
                return redirect(next_url or 'officer_dashboard')
            # Otherwise, redirect to services
            return redirect(next_url or 'services')
    else:
        form = AuthenticationForm()
    
    response = render(request, 'login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })
    response.set_cookie('csrftoken', request.META.get('CSRF_COOKIE', ''), samesite='Lax')
    return response

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

@login_required(login_url='login')
def voting_sessions(request):
    """List active, upcoming and completed voting sessions (with results)."""
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

    # Build completed results map
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
                    'winner_name': cand.user.get_full_name() or cand.user.username,
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
    voting_session = get_object_or_404(VotingSession, id=session_id)

    if request.method == 'POST':
        now = timezone.now()
        if voting_session.status != 'active' or now < voting_session.start_date or now > voting_session.end_date:
            messages.error(request, 'This voting session is not currently active.')
            return redirect('voting_sessions')

        if Vote.objects.filter(voter=request.user, voting_session=voting_session).exists():
            messages.error(request, 'You have already voted in this session.')
            return redirect('voting_sessions')

        candidate_id = request.POST.get('candidate')
        if not candidate_id:
            messages.error(request, 'Please select a candidate.')
            return redirect('vote', session_id=session_id)

        candidate = get_object_or_404(Candidate, id=candidate_id, voting_session=voting_session, approved=True)

        Vote.objects.create(voter=request.user, voting_session=voting_session, candidate=candidate)
        messages.success(request, 'Your vote has been recorded successfully.')
        return redirect('voting_sessions')

    candidates = Candidate.objects.filter(voting_session=voting_session, approved=True).select_related('user')
    return render(request, 'cast_vote.html', {'voting_session': voting_session, 'candidates': candidates})


@login_required(login_url='login')
def apply_candidacy(request, session_id):
    voting_session = get_object_or_404(VotingSession, id=session_id)

    if timezone.now() >= voting_session.start_date:
        messages.error(request, 'The application period for this position has ended.')
        return redirect('voting_sessions')

    if request.method == 'POST':
        candidate_name = request.POST.get('candidate_name', '').strip()
        bio = request.POST.get('bio')
        experience = request.POST.get('experience')
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



@user_passes_test(is_admin, login_url='login')
def delete_complaint(request, complaint_id):
    if request.method == 'POST':
        complaint = get_object_or_404(Complaint, id=complaint_id)
        complaint.delete()
        messages.success(request, 'Complaint deleted successfully.')
    return HttpResponseRedirect(reverse('manage_complaints'))


@login_required(login_url='login')
def services(request):
    """List services with optional search."""
    search_query = request.GET.get('q', '').strip()
    services_qs = Service.objects.all().order_by('-created_at')
    if search_query:
        from django.db.models import Q
        services_qs = services_qs.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
    return render(request, 'services.html', {
        'services': services_qs,
        'search_query': search_query,
    })


@login_required(login_url='login')
def building_construction(request):
    from django.contrib import messages
    service = Service.objects.filter(name__icontains='building').first()
    if not service:
        messages.warning(request, 'Service not available.')
        return render(request, 'building_construction.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You have already submitted a pending application for this service.')
        return render(request, 'building_construction.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        aadhar_number = request.POST.get('aadhar_number')
        address = request.POST.get('address')
        if full_name and aadhar_number and address:
            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=address
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('building_construction')

    return render(request, 'building_construction.html')


@login_required(login_url='login')
def skill_equipment(request):
    from django.contrib import messages
    service = Service.objects.filter(name__icontains='skill').first()
    if not service:
        messages.warning(request, 'Service not available.')
        return render(request, 'skill_equipment.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You have already submitted a pending application for this service.')
        return render(request, 'skill_equipment.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        aadhar_number = request.POST.get('aadhar_number')
        skill_type = request.POST.get('skill_type')
        if full_name and aadhar_number and skill_type:
            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=skill_type
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('skill_equipment')

    return render(request, 'skill_equipment.html')


@login_required(login_url='login')
def bio_gas_plant(request):
    from django.contrib import messages
    service = Service.objects.filter(name__icontains='bio').first()
    if not service:
        messages.warning(request, 'Service not available.')
        return render(request, 'bio_gas_plant.html')

    existing = Application.objects.filter(user=request.user, service=service, status='Pending').exists()
    if existing:
        messages.warning(request, 'You have already submitted a pending application for this service.')
        return render(request, 'bio_gas_plant.html')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        aadhar_number = request.POST.get('aadhar_number')
        address = request.POST.get('address')
        if full_name and aadhar_number and address:
            Application.objects.create(
                user=request.user,
                service=service,
                full_name=full_name,
                aadhar_number=aadhar_number,
                address=address
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('bio_gas_plant')

    return render(request, 'bio_gas_plant.html')


from django import forms
class GenericApplicationForm(forms.Form):
    full_name = forms.CharField(max_length=100, required=True)
    aadhar_number = forms.CharField(max_length=20, required=True)
    address = forms.CharField(widget=forms.Textarea, required=True)


@login_required(login_url='login')
def apply_service(request, service_id):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    service = get_object_or_404(Service, id=service_id)
    # Count all applications for this service (optionally only pending/approved)
    total_applications = Application.objects.filter(service=service).count()
    if total_applications >= service.max_applications:
        messages.warning(request, f'The maximum number of applications for {service.name} has been reached. No more applications are allowed.')
        return render(request, 'apply_service.html', {'service': service})
    # Prevent duplicate applications per user
    user_applications = Application.objects.filter(user=request.user, service=service).count()
    if user_applications >= 1:
        messages.warning(request, f'You have already applied for {service.name}.')
        return render(request, 'apply_service.html', {'service': service})
    if request.method == 'POST':
        form = GenericApplicationForm(request.POST)
        if form.is_valid():
            Application.objects.create(
                user=request.user,
                service=service,
                full_name=form.cleaned_data['full_name'],
                aadhar_number=form.cleaned_data['aadhar_number'],
                address=form.cleaned_data['address']
            )
            messages.success(request, 'Application submitted successfully!')
            return redirect('apply_service', service_id=service.pk)
    else:
        form = GenericApplicationForm()
    return render(request, 'apply_service.html', {'form': form, 'service': service})


def roles_responsibilities(request):
    # Get all active elected members with their positions
    elected_members = ElectedMember.objects.filter(
        status='active'
    ).select_related('user', 'position').order_by('position__name')
    
    return render(request, 'roles_responsibilities.html', {
        'elected_members': elected_members
    })
