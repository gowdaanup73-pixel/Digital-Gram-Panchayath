from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from . import views
from . import voting_views

urlpatterns = [
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('create-service/', views.create_service, name='create_service'),
    path('manage-services/', views.manage_services, name='manage_services'),
    path('delete-service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('view-applications/', views.view_applications, name='view_applications'),
    path('officer-dashboard/', views.officer_dashboard, name='officer_dashboard'),
    path('officer-login/', views.officer_login, name='officer_login'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', views.register, name='register'),
    path('', lambda request: redirect('login'), name='root'),
    path('services/', views.services, name='services'),
    path('services/building-construction/', views.building_construction, name='building_construction'),
    path('services/skill-equipment/', views.skill_equipment, name='skill_equipment'),
    path('services/bio-gas-plant/', views.bio_gas_plant, name='bio_gas_plant'),
    path('apply-service/<int:service_id>/', views.apply_service, name='apply_service'),
    path('manage-complaints/', views.manage_complaints, name='manage_complaints'),
    path('submit-complaint/', views.submit_complaint, name='submit_complaint'),
    path('profile/', views.profile, name='profile'),
    path('profile/<str:username>/', views.profile, name='view_profile'),
    path('view-complaints/', views.view_complaints, name='view_complaints'),
    path('update-complaint-status/<int:complaint_id>/', views.update_complaint_status, name='update_complaint_status'),
    path('delete-complaint/<int:complaint_id>/', views.delete_complaint, name='delete_complaint'),
    path('roles-responsibilities/', views.roles_responsibilities, name='roles_responsibilities'),

    # Voting URLs
    path('voting-sessions/', views.voting_sessions, name='voting_sessions'),
    path('vote/<int:session_id>/', views.vote, name='vote'),
    path('apply-candidacy/<int:session_id>/', views.apply_candidacy, name='apply_candidacy'),

    # Officer/Admin Voting Management URLs
    path('manage-voting-sessions/', voting_views.manage_voting_sessions, name='manage_voting_sessions'),
    path('create-voting-session/', voting_views.create_voting_session, name='create_voting_session'),
]
