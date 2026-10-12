from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from . import views
from . import voting_views

urlpatterns = [
    # Dashboard & Navigation
    path('', lambda request: redirect('login'), name='root'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('officer-dashboard/', views.officer_dashboard, name='officer_dashboard'),

    # Authentication & Session Management
    path('login/', views.login_view, name='login'),
    path('officer-login/', views.officer_login, name='officer_login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),

    # Password Reset Flow
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),

    # Services
    path('services/', views.services, name='services'),
    path('apply-service/<int:service_id>/', views.apply_service, name='apply_service'),
    path('manage-services/', views.manage_services, name='manage_services'),
    path('create-service/', views.create_service, name='create_service'),
    path('delete-service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('view-applications/', views.view_applications, name='view_applications'),

    # Specialized Services (Preserved)
    path('services/building-construction/', views.building_construction, name='building_construction'),
    path('services/skill-equipment/', views.skill_equipment, name='skill_equipment'),
    path('services/bio-gas-plant/', views.bio_gas_plant, name='bio_gas_plant'),

    # Complaints
    path('submit-complaint/', views.submit_complaint, name='submit_complaint'),
    path('view-complaints/', views.view_complaints, name='view_complaints'),
    path('manage-complaints/', views.manage_complaints, name='manage_complaints'),
    path('update-complaint-status/<int:complaint_id>/', views.update_complaint_status, name='update_complaint_status'),
    path('delete-complaint/<int:complaint_id>/', views.delete_complaint, name='delete_complaint'),

    # User Profile
    path('profile/', views.profile, name='profile'),
    path('profile/<str:username>/', views.profile, name='view_profile'),
    path('roles-responsibilities/', views.roles_responsibilities, name='roles_responsibilities'),

    # Voting System (Citizen)
    path('voting-sessions/', views.voting_sessions, name='voting_sessions'),
    path('vote/<int:session_id>/', views.vote, name='vote'),
    path('apply-candidacy/<int:session_id>/', views.apply_candidacy, name='apply_candidacy'),

    # Voting System (Officer/Admin Management)
    path('manage-voting-sessions/', voting_views.manage_voting_sessions, name='manage_voting_sessions'),
    path('create-voting-session/', voting_views.create_voting_session, name='create_voting_session'),
]
