from django.db import transaction
from django.utils import timezone
from rest_framework import generics, viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from core.models import Service, Application, Complaint, Profile, VotingSession, Candidate, Vote, AuditLog
from core.api.serializers import (
    UserRegistrationSerializer, UserSerializer, ProfileSerializer,
    ServiceSerializer, ApplicationSerializer, ApplicationReviewSerializer,
    ComplaintSerializer, ComplaintReviewSerializer,
    VotingSessionSerializer, VoteSerializer
)
from core.api.permissions import IsOfficerOrAdmin, IsOwnerOrOfficer


class RegisterAPIView(generics.CreateAPIView):
    """
    Public citizen registration API endpoint.
    Strictly sets is_staff=False and is_superuser=False.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuditLog.log(
            request=request,
            action='register',
            target_type='User',
            target_id=str(user.id),
            details=f"API Registration: Citizen '{user.username}' registered successfully."
        )
        return Response(
            {
                "message": "User registered successfully.",
                "user": UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )


class LogoutAPIView(APIView):
    """
    Logout API endpoint. Revokes/blacklists the provided refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            AuditLog.log(
                request=request,
                action='login_success',
                target_type='User',
                target_id=str(request.user.id),
                details=f"API Logout: Refresh token revoked for user '{request.user.username}'."
            )
            return Response({"message": "Successfully logged out. Refresh token revoked."}, status=status.HTTP_200_OK)
        except TokenError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProfileAPIView(generics.RetrieveUpdateAPIView):
    """
    Retrieve and update the authenticated user's profile.
    Citizens can never access or modify other citizens' profiles through this endpoint.
    """
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile


class ServiceViewSet(viewsets.ModelViewSet):
    """
    Services API endpoint.
    Read-only for regular citizens; full CRUD for authorized officers.
    """
    queryset = Service.objects.all().order_by('-created_at')
    serializer_class = ServiceSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsOfficerOrAdmin()]

    def perform_create(self, serializer):
        service = serializer.save()
        AuditLog.log(
            request=self.request,
            action='service_create',
            target_type='Service',
            target_id=str(service.id),
            details=f"API Service create: '{service.name}' created by '{self.request.user.username}'."
        )

    def perform_destroy(self, instance):
        service_id = instance.id
        service_name = instance.name
        instance.delete()
        AuditLog.log(
            request=self.request,
            action='service_delete',
            target_type='Service',
            target_id=str(service_id),
            details=f"API Service delete: '{service_name}' deleted by '{self.request.user.username}'."
        )


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    Applications API endpoint.
    Citizens can view and submit only their own applications (IDOR prevention).
    Officers can view all applications and review (approve/reject) them.
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOfficer]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Application.objects.select_related('user', 'service').all().order_by('-created_at')
        return Application.objects.filter(user=user).select_related('service').order_by('-created_at')

    def perform_create(self, serializer):
        app = serializer.save()
        AuditLog.log(
            request=self.request,
            action='app_status_update',
            target_type='Application',
            target_id=str(app.id),
            details=f"API Application submitted: #{app.id} for '{app.service.name}' by '{self.request.user.username}'."
        )

    @action(detail=True, methods=['post'], permission_classes=[IsOfficerOrAdmin])
    def review(self, request, pk=None):
        """Officer review action to accept or reject an application."""
        application = self.get_object()
        serializer = ApplicationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_choice = serializer.validated_data['action']
        if action_choice == 'accept':
            application.status = Application.STATUS_APPROVED
            application.rejection_reason = ''
            application.save()
            AuditLog.log(
                request=request,
                action='app_status_update',
                target_type='Application',
                target_id=str(application.id),
                details=f"API Application review: #{application.id} approved by '{request.user.username}'."
            )
            return Response({"message": f"Application #{application.id} approved successfully."})
        else:
            reason = serializer.validated_data.get('rejection_reason', '')
            application.status = Application.STATUS_REJECTED
            application.rejection_reason = reason
            application.save()
            AuditLog.log(
                request=request,
                action='app_status_update',
                target_type='Application',
                target_id=str(application.id),
                details=f"API Application review: #{application.id} rejected by '{request.user.username}'. Reason: {reason}"
            )
            return Response({"message": f"Application #{application.id} rejected."})


class ComplaintViewSet(viewsets.ModelViewSet):
    """
    Complaints API endpoint.
    Citizens can view and create only their own complaints (IDOR prevention).
    Officers can view all complaints and update their resolution status.
    """
    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOfficer]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Complaint.objects.select_related('user').all().order_by('-created_at')
        return Complaint.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        complaint = serializer.save()
        AuditLog.log(
            request=self.request,
            action='complaint_status_update',
            target_type='Complaint',
            target_id=str(complaint.id),
            details=f"API Complaint submitted: #{complaint.id} by '{self.request.user.username}'."
        )

    def perform_destroy(self, instance):
        complaint_id = instance.id
        instance.delete()
        AuditLog.log(
            request=self.request,
            action='complaint_delete',
            target_type='Complaint',
            target_id=str(complaint_id),
            details=f"API Complaint deleted: #{complaint_id} by '{self.request.user.username}'."
        )

    @action(detail=True, methods=['post'], permission_classes=[IsOfficerOrAdmin])
    def review(self, request, pk=None):
        """Officer review action to update complaint status and add remarks."""
        complaint = self.get_object()
        serializer = ComplaintReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        complaint.status = serializer.validated_data['status']
        if 'admin_remarks' in serializer.validated_data:
            complaint.admin_remarks = serializer.validated_data['admin_remarks']
        complaint.save()

        AuditLog.log(
            request=request,
            action='complaint_status_update',
            target_type='Complaint',
            target_id=str(complaint.id),
            details=f"API Complaint review: #{complaint.id} status changed to '{complaint.status}' by '{request.user.username}'."
        )
        return Response({"message": f"Complaint #{complaint.id} status updated to {complaint.status}."})


class VotingSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Voting sessions API endpoint.
    List and retrieve active, upcoming, or completed election sessions.
    Allows authenticated citizens to cast a vote with concurrency safety.
    """
    queryset = VotingSession.objects.all().order_by('-created_at')
    serializer_class = VotingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        session = self.get_object()
        serializer = VoteSerializer(data=request.data, context={'request': request, 'session': session})
        serializer.is_valid(raise_exception=True)

        candidate = serializer.validated_data['candidate']

        with transaction.atomic():
            if Vote.objects.filter(voter=request.user, voting_session=session).exists():
                return Response({"error": "You have already voted in this session."}, status=status.HTTP_400_BAD_REQUEST)

            vote = Vote.objects.create(
                voter=request.user,
                voting_session=session,
                candidate=candidate
            )
            AuditLog.log(
                request=request,
                action='vote_cast',
                target_type='VotingSession',
                target_id=str(session.id),
                details=f"API Vote cast: Citizen '{request.user.username}' voted in session #{session.id}."
            )

        return Response({"message": "Vote recorded successfully."}, status=status.HTTP_201_CREATED)
