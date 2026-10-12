from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from core.models import (
    Service, Application, Complaint, Profile,
    VotingSession, Candidate, Vote, ElectedPosition
)
from core.validators import validate_complaint_attachment, validate_aadhar_number


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password_confirm')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            is_staff=False,
            is_superuser=False
        )
        Profile.objects.get_or_create(user=user)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser')
        read_only_fields = ('id', 'username', 'is_staff', 'is_superuser')


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ('id', 'user', 'phone_number', 'address', 'aadhar_number', 'date_of_birth')

    def validate_aadhar_number(self, value):
        if value:
            validate_aadhar_number(value)
        return value


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ('id', 'name', 'description', 'requirements', 'benefits', 'max_applications', 'created_at')


class ApplicationSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    service_name = serializers.ReadOnlyField(source='service.name')

    class Meta:
        model = Application
        fields = (
            'id', 'user', 'service', 'service_name', 'full_name',
            'aadhar_number', 'address', 'status', 'rejection_reason',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'status', 'rejection_reason', 'created_at', 'updated_at')

    def validate_aadhar_number(self, value):
        validate_aadhar_number(value)
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        service = attrs.get('service')
        if request and service:
            user = request.user
            # Check maximum applications quota
            total_apps = Application.objects.filter(service=service).count()
            if total_apps >= service.max_applications:
                raise serializers.ValidationError(
                    f"Maximum applications quota ({service.max_applications}) has been reached for this service."
                )
            # Check duplicate application by user
            if Application.objects.filter(user=user, service=service).exists():
                raise serializers.ValidationError("You have already applied for this service.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        return Application.objects.create(user=user, **validated_data)


class ApplicationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get('action') == 'reject' and not attrs.get('rejection_reason', '').strip():
            raise serializers.ValidationError({"rejection_reason": "Rejection reason is required when rejecting."})
        return attrs


class ComplaintSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Complaint
        fields = (
            'id', 'user', 'category', 'subject', 'location',
            'description', 'attachment', 'status', 'admin_remarks',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'status', 'admin_remarks', 'created_at', 'updated_at')

    def validate_attachment(self, value):
        if value:
            validate_complaint_attachment(value)
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        return Complaint.objects.create(user=user, **validated_data)


class ComplaintReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[c[0] for c in Complaint.STATUS_CHOICES])
    admin_remarks = serializers.CharField(required=False, allow_blank=True)


class CandidateSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ('id', 'candidate_name', 'display_name', 'bio', 'experience', 'approved', 'created_at')

    def get_display_name(self, obj):
        return obj.get_display_name()


class VotingSessionSerializer(serializers.ModelSerializer):
    position_name = serializers.ReadOnlyField(source='position.name')
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = VotingSession
        fields = (
            'id', 'title', 'description', 'position', 'position_name',
            'start_date', 'end_date', 'status', 'candidates', 'created_at'
        )


class VoteSerializer(serializers.Serializer):
    candidate_id = serializers.IntegerField(required=True)

    def validate(self, attrs):
        request = self.context.get('request')
        session = self.context.get('session')
        user = request.user
        candidate_id = attrs['candidate_id']

        now = timezone.now()
        if session.status != 'active' or now < session.start_date or now > session.end_date:
            raise serializers.ValidationError("This election session is not active.")

        if Vote.objects.filter(voter=user, voting_session=session).exists():
            raise serializers.ValidationError("You have already voted in this session.")

        try:
            candidate = Candidate.objects.get(id=candidate_id, voting_session=session, approved=True)
        except Candidate.DoesNotExist:
            raise serializers.ValidationError("Invalid or unapproved candidate selected for this session.")

        attrs['candidate'] = candidate
        return attrs
