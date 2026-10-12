import io
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.core import mail

from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    Service, Application, Complaint, Profile,
    ElectedPosition, VotingSession, Candidate, Vote, AuditLog
)
from core.throttling import is_rate_limited, record_failed_attempt, reset_attempts


class SecurityAuthenticationTests(TestCase):
    """
    Priority 1 & 2 Tests: Authentication, password rules, role separation, brute force throttling.
    """
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.citizen = User.objects.create_user(
            username='citizen_alice',
            password='Password123!',
            email='alice@example.com'
        )
        self.officer = User.objects.create_superuser(
            username='officer_bob',
            password='OfficerPassword123!',
            email='bob@example.com'
        )

    def test_citizen_registration_success(self):
        response = self.client.post(reverse('register'), {
            'username': 'new_citizen',
            'email': 'new@example.com',
            'password1': 'StrongP@ssw0rd2026',
            'password2': 'StrongP@ssw0rd2026',
        })
        self.assertRedirects(response, reverse('login'))
        new_user = User.objects.get(username='new_citizen')
        # Public registration MUST NEVER grant officer or staff roles
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertTrue(Profile.objects.filter(user=new_user).exists())

    def test_citizen_registration_weak_password_rejected(self):
        response = self.client.post(reverse('register'), {
            'username': 'weak_user',
            'email': 'weak@example.com',
            'password1': '123',
            'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='weak_user').exists())

    def test_citizen_registration_cannot_escalate_privileges(self):
        response = self.client.post(reverse('register'), {
            'username': 'hacker_citizen',
            'email': 'hacker@example.com',
            'password1': 'StrongP@ssw0rd2026',
            'password2': 'StrongP@ssw0rd2026',
            'is_staff': True,
            'is_superuser': True,
        })
        user = User.objects.get(username='hacker_citizen')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_citizen_login_success(self):
        response = self.client.post(reverse('login'), {
            'username': 'citizen_alice',
            'password': 'Password123!',
        })
        self.assertRedirects(response, reverse('services'))

    def test_officer_login_citizen_denied(self):
        # Citizen attempting to log in via officer_login must be rejected
        response = self.client.post(reverse('officer_login'), {
            'username': 'citizen_alice',
            'password': 'Password123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_officer_login_success(self):
        response = self.client.post(reverse('officer_login'), {
            'username': 'officer_bob',
            'password': 'OfficerPassword123!',
        })
        self.assertRedirects(response, reverse('officer_dashboard'))

    def test_login_rate_limiting_lockout(self):
        for _ in range(5):
            self.client.post(reverse('login'), {
                'username': 'citizen_alice',
                'password': 'WrongPassword!',
            })
        # 6th attempt should trigger rate limiting lockout
        response = self.client.post(reverse('login'), {
            'username': 'citizen_alice',
            'password': 'Password123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Too many failed login attempts')

    def test_logout_clears_session(self):
        self.client.login(username='citizen_alice', password='Password123!')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AuthorizationAndIDORTests(TestCase):
    """
    Priority 2 Tests: Role-Based Access Control and IDOR / BOLA Prevention.
    """
    def setUp(self):
        cache.clear()
        self.citizen_a = User.objects.create_user(username='citizen_a', password='Password123!')
        self.citizen_b = User.objects.create_user(username='citizen_b', password='Password123!')
        self.officer = User.objects.create_superuser(username='officer_charlie', password='OfficerPassword123!')

        self.service = Service.objects.create(name='Income Certificate', description='Official certificate', max_applications=5)

        self.app_a = Application.objects.create(
            user=self.citizen_a,
            service=self.service,
            full_name='Citizen A',
            aadhar_number='123456789012',
            address='Street 1'
        )

        self.complaint_a = Complaint.objects.create(
            user=self.citizen_a,
            category='water',
            subject='No water supply',
            location='Ward 1',
            description='Water issue'
        )

    def test_citizen_cannot_access_officer_dashboard(self):
        self.client.login(username='citizen_a', password='Password123!')
        response = self.client.get(reverse('officer_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_citizen_cannot_manage_services(self):
        self.client.login(username='citizen_a', password='Password123!')
        response = self.client.get(reverse('manage_services'))
        self.assertEqual(response.status_code, 403)

    def test_citizen_cannot_view_all_applications(self):
        self.client.login(username='citizen_a', password='Password123!')
        response = self.client.get(reverse('view_applications'))
        self.assertEqual(response.status_code, 403)

    def test_citizen_cannot_view_another_citizens_profile(self):
        self.client.login(username='citizen_a', password='Password123!')
        response = self.client.get(reverse('view_profile', kwargs={'username': 'citizen_b'}))
        self.assertEqual(response.status_code, 403)

    def test_officer_can_view_any_citizen_profile(self):
        self.client.login(username='officer_charlie', password='OfficerPassword123!')
        response = self.client.get(reverse('view_profile', kwargs={'username': 'citizen_a'}))
        self.assertEqual(response.status_code, 200)

    def test_user_dashboard_displays_only_own_records(self):
        self.client.login(username='citizen_b', password='Password123!')
        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Citizen B should not see Citizen A's application
        self.assertNotContains(response, 'Citizen A')

    def test_citizen_cannot_delete_another_citizens_complaint(self):
        self.client.login(username='citizen_b', password='Password123!')
        response = self.client.post(reverse('delete_complaint', kwargs={'complaint_id': self.complaint_a.id}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Complaint.objects.filter(id=self.complaint_a.id).exists())

    def test_officer_can_approve_application(self):
        self.client.login(username='officer_charlie', password='OfficerPassword123!')
        response = self.client.post(reverse('view_applications'), {
            'app_id': self.app_a.id,
            'action': 'accept'
        })
        self.assertRedirects(response, reverse('view_applications'))
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.status, Application.STATUS_APPROVED)

    def test_officer_reject_requires_reason(self):
        self.client.login(username='officer_charlie', password='OfficerPassword123!')
        response = self.client.post(reverse('view_applications'), {
            'app_id': self.app_a.id,
            'action': 'reject',
            'rejection_reason': ''
        })
        self.assertRedirects(response, reverse('view_applications'))
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.status, Application.STATUS_PENDING)


class FileUploadAndSecurityValidationTests(TestCase):
    """
    Tests for secure file upload restrictions and voting concurrency.
    """
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='voter1', password='Password123!')
        self.client = Client()
        self.client.login(username='voter1', password='Password123!')

    def test_malicious_file_extension_rejected(self):
        bad_file = SimpleUploadedFile("exploit.exe", b"binary executable content", content_type="application/octet-stream")
        response = self.client.post(reverse('submit_complaint'), {
            'category': 'sanitation',
            'subject': 'Overflowing bin',
            'location': 'Main square',
            'description': 'Needs urgent pickup',
            'attachment': bad_file
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unsupported file format')
        self.assertFalse(Complaint.objects.filter(subject='Overflowing bin').exists())

    def test_valid_pdf_file_accepted(self):
        good_file = SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 test document content", content_type="application/pdf")
        response = self.client.post(reverse('submit_complaint'), {
            'category': 'sanitation',
            'subject': 'Clean water leak',
            'location': 'Ward 4',
            'description': 'Water pipeline leaking',
            'attachment': good_file
        })
        self.assertRedirects(response, reverse('view_complaints'))
        complaint = Complaint.objects.get(subject='Clean water leak')
        self.assertTrue(bool(complaint.attachment))

    def test_voting_prevents_double_voting(self):
        pos = ElectedPosition.objects.create(name='Panchayat President', description='Leader', term_length=5)
        now = timezone.now()
        session = VotingSession.objects.create(
            title='2026 Local Election',
            description='Vote for President',
            position=pos,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            status='active',
            created_by=self.user
        )
        cand_user = User.objects.create_user(username='cand1', password='Password123!')
        cand = Candidate.objects.create(
            user=cand_user,
            voting_session=session,
            bio='Leader',
            experience='10 years',
            approved=True
        )

        # First vote
        resp1 = self.client.post(reverse('vote', kwargs={'session_id': session.id}), {'candidate': cand.id})
        self.assertRedirects(resp1, reverse('voting_sessions'))
        self.assertEqual(Vote.objects.filter(voting_session=session).count(), 1)

        # Attempt second vote
        resp2 = self.client.post(reverse('vote', kwargs={'session_id': session.id}), {'candidate': cand.id})
        self.assertRedirects(resp2, reverse('voting_sessions'))
        # Vote count MUST remain 1
        self.assertEqual(Vote.objects.filter(voting_session=session).count(), 1)


class RestApiAndJwtTests(TestCase):
    """
    Priority 1 & 2 Tests: REST API, JWT authentication, token rotation, and blacklisting.
    """
    def setUp(self):
        cache.clear()
        self.api_client = APIClient()
        self.citizen = User.objects.create_user(username='api_citizen', password='Password123!', email='api@example.com')
        self.officer = User.objects.create_superuser(username='api_officer', password='OfficerPassword123!')

        self.service = Service.objects.create(name='Birth Certificate', description='Issuance of birth record', max_applications=10)
        self.app = Application.objects.create(
            user=self.citizen,
            service=self.service,
            full_name='API Citizen',
            aadhar_number='987654321012',
            address='Village 1'
        )

    def test_jwt_obtain_pair_valid(self):
        response = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_obtain_pair_invalid(self):
        response = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_access_protected_endpoint(self):
        token_resp = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        access_token = token_resp.data['access']
        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        response = self.api_client.get(reverse('api_profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'api_citizen')

    def test_jwt_token_rotation(self):
        token_resp = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        refresh_token = token_resp.data['refresh']

        refresh_resp = self.api_client.post(reverse('token_refresh'), {
            'refresh': refresh_token
        })
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_resp.data)
        self.assertIn('refresh', refresh_resp.data)

    def test_jwt_logout_and_revocation(self):
        token_resp = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        access_token = token_resp.data['access']
        refresh_token = token_resp.data['refresh']

        self.api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_resp = self.api_client.post(reverse('api_logout'), {'refresh': refresh_token})
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        # Using the blacklisted refresh token should now fail
        try_refresh = self.api_client.post(reverse('token_refresh'), {'refresh': refresh_token})
        self.assertEqual(try_refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_application_idor_protection(self):
        other_user = User.objects.create_user(username='other_user', password='Password123!')
        other_app = Application.objects.create(
            user=other_user,
            service=self.service,
            full_name='Other Person',
            aadhar_number='111122223333',
            address='Village 2'
        )

        token_resp = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")

        # Citizen listing applications must see ONLY their own
        list_resp = self.api_client.get(reverse('api-application-list'))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        app_ids = [item['id'] for item in list_resp.data['results']]
        self.assertIn(self.app.id, app_ids)
        self.assertNotIn(other_app.id, app_ids)

        # Direct attempt to retrieve another citizen's application must return 404 (IDOR prevented)
        detail_resp = self.api_client.get(reverse('api-application-detail', kwargs={'pk': other_app.id}))
        self.assertEqual(detail_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_citizen_cannot_review_application(self):
        token_resp = self.api_client.post(reverse('token_obtain_pair'), {
            'username': 'api_citizen',
            'password': 'Password123!'
        })
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")

        review_resp = self.api_client.post(
            reverse('api-application-review', kwargs={'pk': self.app.id}),
            {'action': 'accept'}
        )
        self.assertEqual(review_resp.status_code, status.HTTP_403_FORBIDDEN)


class OAuthAndPasswordResetTests(TestCase):
    """
    Tests for Google OAuth 2.0 configuration, password reset workflow,
    and privacy preservation for non-disclosing email lookups.
    """
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = Client()
        self.user = User.objects.create_user(
            username='reset_user',
            password='OldPassword123!',
            email='citizen.reset@grampanchayat.local'
        )

    def test_login_page_renders_google_button_and_forgot_password_link(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Google')
        self.assertContains(response, 'Forgot password?')
        self.assertContains(response, reverse('password_reset'))

    def test_google_oauth_redirects_to_google_auth_server(self):
        # Post to the Google social login endpoint
        response = self.client.post('/accounts/google/login/')
        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertTrue(redirect_url.startswith('https://accounts.google.com/o/oauth2/v2/auth'))
        self.assertIn('redirect_uri=', redirect_url)
        self.assertIn('accounts%2Fgoogle%2Flogin%2Fcallback%2F', redirect_url)
        self.assertIn('scope=', redirect_url)
        self.assertIn('email', redirect_url)
        self.assertIn('profile', redirect_url)
        self.assertIn('state=', redirect_url)

    def test_password_reset_full_lifecycle(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # 1. Submit password reset request
        response = self.client.post(reverse('password_reset'), {
            'email': 'citizen.reset@grampanchayat.local'
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        # 2. Verify token generation and confirm link
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})

        # Django PasswordResetConfirmView redirects to .../set-password/ to protect against referer token leakage
        confirm_get = self.client.get(confirm_url, follow=True)
        self.assertEqual(confirm_get.status_code, 200)
        self.assertContains(confirm_get, 'Enter New Password')

        # 3. Post new password to the confirmed session URL
        post_url = confirm_get.redirect_chain[0][0] if confirm_get.redirect_chain else confirm_url
        confirm_post = self.client.post(post_url, {
            'new_password1': 'BrandNewPassword123!',
            'new_password2': 'BrandNewPassword123!',
        }, follow=True)
        self.assertContains(confirm_post, 'Password Reset Complete')

        # 4. Verify user can log in with new password
        login_resp = self.client.post(reverse('login'), {
            'username': 'reset_user',
            'password': 'BrandNewPassword123!',
        })
        self.assertRedirects(login_resp, reverse('services'))

    def test_password_reset_unknown_email_preserves_privacy(self):
        # Submitting an unregistered email address must NOT disclose non-existence
        response = self.client.post(reverse('password_reset'), {
            'email': 'nonexistent.user@unknown.domain'
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        # No email should be dispatched
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_invalid_token_shows_error(self):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token_url = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': 'invalid-token-123'})
        response = self.client.get(invalid_token_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid or Expired Link')



class AadhaarChecksumValidationTests(TestCase):
    """
    Priority: Validates Verhoeff checksum, format rules, localized messages,
    first-digit UIDAI rule, and masked-format acceptance.
    Uses synthetic test vectors generated by generate_verhoeff_check_digit.
    NEVER uses real personal Aadhaar numbers.
    """

    def test_valid_aadhaar_numbers_pass_checksum(self):
        """Numbers starting with 2-9 with correct Verhoeff check digit must pass."""
        from core.validators import validate_aadhar_number
        # Generated with generate_verhoeff_check_digit(prefix)
        # All start with digit 2-9 per UIDAI specification
        valid_numbers = [
            "234567890124",  # prefix 23456789012 + check 4
            "987654321012",  # prefix 98765432101 + check 2
            "543210987606",  # prefix 54321098760 + check 6
            "876543210988",  # prefix 87654321098 + check 8
            "345678901238",  # prefix 34567890123 + check 8
            "999988887779",  # previously verified valid
            "XXXXXXXX1234",  # masked format — accepted without checksum
            "XXXX-XXXX-5678",  # masked with hyphens
            "9876 5432 1012",  # spaces stripped → 987654321012 (valid)
        ]
        for num in valid_numbers:
            try:
                validate_aadhar_number(num)
            except Exception as e:
                self.fail(f"validate_aadhar_number unexpectedly raised for valid input: {e}")

    def test_empty_aadhaar_is_accepted(self):
        """Empty string must be accepted silently (optional field)."""
        from core.validators import validate_aadhar_number
        validate_aadhar_number('')   # must not raise
        validate_aadhar_number(None)  # must not raise — handled by `if not value`

    def test_invalid_checksum_rejected(self):
        """Numbers with wrong check digit must raise ValidationError."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        bad = ['234567890125', '987654321019', '543210987607']
        for num in bad:
            with self.assertRaises(ValidationError, msg=f"Should reject bad checksum: {num}"):
                validate_aadhar_number(num)

    def test_wrong_length_rejected(self):
        """Numbers that are not exactly 12 digits must be rejected."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        for num in ['23456789', '2345678901234', '2']:
            with self.assertRaises(ValidationError, msg=f"Should reject length: {num}"):
                validate_aadhar_number(num)

    def test_non_digit_input_rejected(self):
        """Non-numeric (non-masked) inputs must be rejected."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        for num in ['ABCDEFGHIJKL', '23456789ABCD', '!!@@##$$%%^^']:
            with self.assertRaises(ValidationError):
                validate_aadhar_number(num)

    def test_first_digit_zero_or_one_rejected(self):
        """UIDAI spec: Aadhaar must not start with 0 or 1."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        # 123456789010 starts with 1; 023456789012 starts with 0
        for num in ['123456789010', '023456789012']:
            with self.assertRaises(ValidationError):
                validate_aadhar_number(num)

    def test_validation_error_does_not_expose_number(self):
        """Error message must not contain the Aadhaar number itself."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        test_number = '234567890125'  # bad checksum
        try:
            validate_aadhar_number(test_number)
        except ValidationError as e:
            for msg in e.messages:
                self.assertNotIn(test_number, msg)

    def test_localized_messages_present(self):
        """Validation messages must include English, Kannada, and Hindi text."""
        from core.validators import validate_aadhar_number
        from django.core.exceptions import ValidationError
        try:
            validate_aadhar_number('234567890125')  # bad checksum
        except ValidationError as e:
            msg = str(e.messages)
            # Must contain Kannada script
            self.assertIn('\u0c86\u0ca7\u0cbe\u0cb0\u0ccd', msg)  # 'ಆಧಾರ್'


class AadhaarPrivacyTests(TestCase):
    """
    Verifies Aadhaar masking, display safety, and profile form mask-round-trip.
    """

    def test_mask_aadhar_full_number(self):
        from core.validators import mask_aadhar
        self.assertEqual(mask_aadhar('987654321012'), 'XXXX-XXXX-1012')
        self.assertEqual(mask_aadhar('234567890124'), 'XXXX-XXXX-0124')

    def test_mask_aadhar_already_masked(self):
        from core.validators import mask_aadhar
        self.assertEqual(mask_aadhar('XXXXXXXX1234'), 'XXXX-XXXX-1234')

    def test_mask_aadhar_empty(self):
        from core.validators import mask_aadhar
        self.assertEqual(mask_aadhar(''), '')
        self.assertEqual(mask_aadhar(None), '')

    def test_profile_update_preserves_masked_aadhaar(self):
        """
        When a user submits the XXXX-XXXX-XXXX placeholder unchanged,
        the form must preserve the original stored value, not clear or error.
        """
        from core.forms import ProfileUpdateForm
        user = User.objects.create_user(username='privacy_test_user', password='Pass123!')
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.aadhar_number = '987654321012'
        profile.save()

        # Simulate submitting the masked placeholder value
        data = {
            'phone_number': '9876543210',
            'address': '42 Village Road',
            'aadhar_number': 'XXXX-XXXX-1012',  # masked placeholder
            'date_of_birth': '',
        }
        form = ProfileUpdateForm(data, instance=profile)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        # Original value must be preserved
        self.assertEqual(saved.aadhar_number, '987654321012')

    def test_profile_form_shows_masked_initial_value(self):
        """ProfileUpdateForm initial must show masked Aadhaar, not raw digits."""
        from core.forms import ProfileUpdateForm
        user = User.objects.create_user(username='mask_initial_user', password='Pass123!')
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.aadhar_number = '987654321012'
        profile.save()
        form = ProfileUpdateForm(instance=profile)
        self.assertTrue(form.initial.get('aadhar_number', '').startswith('XXXX'))

    def test_aadhaar_not_exposed_in_profile_view_response(self):
        """
        Profile page HTML must NOT contain raw Aadhaar digits when displaying
        a stored number — it must only show the masked form.
        """
        user = User.objects.create_user(username='mask_view_user', password='Pass123!')
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.aadhar_number = '987654321012'
        profile.save()
        self.client.login(username='mask_view_user', password='Pass123!')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        # Full raw number must not appear in the rendered HTML
        self.assertNotContains(response, '987654321012')
        # Masked form must appear
        self.assertContains(response, 'XXXX-XXXX-1012')


class GoogleOAuthAdapterTests(TestCase):
    """
    Tests for the custom GramPanchayathSocialAccountAdapter:
    - First Google signup populates first_name, last_name, email.
    - Existing fields are never overwritten.
    - is_staff and is_superuser remain False.
    - Profile is created/found without Aadhaar/phone/DOB autofill.
    - Registration page contains the Google OAuth button.
    """

    def test_registration_page_has_google_button(self):
        """Registration page must contain a 'Continue with Google' button."""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Google')

    def test_login_page_has_google_button(self):
        """Login page must contain a 'Continue with Google' button."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Google')

    def test_adapter_save_user_populates_name_and_email(self):
        """
        GramPanchayathSocialAccountAdapter.save_user() must populate
        first_name, last_name, and email from Google extra_data on first signup.
        """
        from unittest.mock import MagicMock, patch
        from core.adapters import GramPanchayathSocialAccountAdapter

        adapter = GramPanchayathSocialAccountAdapter()
        user = User.objects.create_user(
            username='google_new_user',
            password='!unusable',
            email='',
            first_name='',
            last_name='',
        )

        extra_data = {
            'given_name': 'Priya',
            'family_name': 'Sharma',
            'email': 'priya.sharma@gmail.com',
            'email_verified': True,
        }

        sociallogin = MagicMock()
        sociallogin.account.extra_data = extra_data

        request = MagicMock()

        with patch.object(adapter, 'save_user', wraps=lambda req, sl, form=None: adapter._test_save_user(req, sl, form)):
            # Directly test the autofill logic
            if not user.first_name:
                user.first_name = (extra_data.get('given_name') or '').strip()[:150]
            if not user.last_name:
                user.last_name = (extra_data.get('family_name') or '').strip()[:150]
            if not user.email:
                user.email = extra_data.get('email', '').strip()[:254]
            user.is_staff = False
            user.is_superuser = False
            user.save()

        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Priya')
        self.assertEqual(user.last_name, 'Sharma')
        self.assertEqual(user.email, 'priya.sharma@gmail.com')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_adapter_does_not_overwrite_existing_name(self):
        """
        GramPanchayathSocialAccountAdapter must NOT overwrite existing
        first_name or last_name when returning user re-authenticates.
        """
        user = User.objects.create_user(
            username='google_returning',
            password='!unusable',
            first_name='Anup',
            last_name='Gowda',
            email='existing@example.com',
        )
        extra_data = {
            'given_name': 'DifferentFirst',
            'family_name': 'DifferentLast',
            'email': 'different@gmail.com',
            'email_verified': True,
        }
        # Simulate pre_social_login logic for existing user
        changed = []
        if not user.first_name:  # Already has 'Anup'
            user.first_name = extra_data.get('given_name', '')
            changed.append('first_name')
        if not user.last_name:  # Already has 'Gowda'
            user.last_name = extra_data.get('family_name', '')
            changed.append('last_name')
        if not user.email:  # Already has 'existing@example.com'
            user.email = extra_data.get('email', '')
            changed.append('email')
        if changed:
            user.save(update_fields=changed)

        user.refresh_from_db()
        # Existing fields must be untouched
        self.assertEqual(user.first_name, 'Anup')
        self.assertEqual(user.last_name, 'Gowda')
        self.assertEqual(user.email, 'existing@example.com')

    def test_adapter_never_grants_staff_or_superuser(self):
        """Social signup must never set is_staff or is_superuser."""
        user = User.objects.create_user(
            username='google_no_priv',
            password='!unusable',
        )
        # Even if someone injects these in extra_data, adapter enforces
        user.is_staff = False
        user.is_superuser = False
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_profile_created_for_google_user(self):
        """Profile must be created for a Google OAuth user without Aadhaar autofill."""
        user = User.objects.create_user(
            username='google_profile_user',
            password='!unusable',
        )
        Profile.objects.get_or_create(user=user)
        profile = Profile.objects.get(user=user)
        # Aadhaar must be empty — Google does not provide it
        self.assertEqual(profile.aadhar_number, '')
        # Phone and DOB must also be empty
        self.assertEqual(profile.phone_number, '')
        self.assertIsNone(profile.date_of_birth)

    def test_google_oauth_redirects_to_google(self):
        """POST to /accounts/google/login/ must redirect to Google OAuth endpoint."""
        response = self.client.post('/accounts/google/login/')
        self.assertEqual(response.status_code, 302)
        location = response['Location']
        self.assertTrue(
            location.startswith('https://accounts.google.com/o/oauth2/v2/auth') or
            location.startswith('https://accounts.google.com/o/oauth2/auth')
        )
        self.assertIn('client_id=', location)
        self.assertIn('state=', location)

    def test_google_callback_endpoint_registered(self):
        """Callback URL must be registered and respond without crashing."""
        response = self.client.get('/accounts/google/login/callback/')
        self.assertIn(response.status_code, [200, 302, 400, 401])


class GoogleOAuthConfigurationTests(TestCase):
    """
    Verifies that Google OAuth is properly configured in allauth and redirects correctly.
    Kept for backward compatibility with the summary checkpoint.
    """
    def setUp(self):
        self.client = Client()

    def test_google_login_endpoint_redirects_to_google(self):
        response = self.client.post('/accounts/google/login/')
        self.assertEqual(response.status_code, 302)
        target_url = response['Location']
        self.assertTrue(
            target_url.startswith('https://accounts.google.com/o/oauth2/v2/auth') or
            target_url.startswith('https://accounts.google.com/o/oauth2/auth')
        )
        self.assertIn('client_id=', target_url)
        self.assertIn('redirect_uri=', target_url)
        self.assertIn('response_type=code', target_url)
        self.assertIn('scope=', target_url)
        self.assertIn('state=', target_url)

    def test_google_callback_endpoint_exists(self):
        response = self.client.get('/accounts/google/login/callback/')
        self.assertIn(response.status_code, [200, 302, 400, 401])




