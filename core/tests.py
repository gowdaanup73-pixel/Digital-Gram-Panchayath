import io
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

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
