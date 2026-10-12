"""
Django-allauth Social Account Adapter for Digital Gram Panchayath.

Responsibilities:
  - On first Google signup: populate first_name, last_name, email from Google's
    verified profile data.
  - For returning Google users: preserve all existing manually-edited fields;
    only refresh email if the stored one is still blank.
  - Never autofill Aadhaar, mobile number, date of birth, address, or any field
    that is unavailable from Google's standard profile scope.
  - Create or find an associated Profile record using get_or_create.
  - Never expose OAuth tokens or raw social-account data in logs.
"""

import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)


class GramPanchayathSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom allauth SocialAccountAdapter.

    Called when a user authenticates via a social provider (Google).
    We hook into `save_user` to populate User fields from verified
    Google profile data on first signup, and `pre_social_login` for
    returning-user data refresh.
    """

    def save_user(self, request, sociallogin, form=None):
        """
        Called when a new social account is created (first-time signup via Google).
        Populates first_name, last_name, email from Google's verified token data.
        Never touches Aadhaar, phone, DOB, or address — these are not available
        from Google's basic profile+email scopes.
        """
        user = super().save_user(request, sociallogin, form)
        extra_data = sociallogin.account.extra_data or {}

        # Only autofill fields that are still empty to avoid overwriting manual edits
        if not user.first_name:
            user.first_name = (extra_data.get('given_name') or '').strip()[:150]
        if not user.last_name:
            user.last_name = (extra_data.get('family_name') or '').strip()[:150]
        if not user.email:
            verified_email = extra_data.get('email', '')
            if extra_data.get('email_verified', False) or extra_data.get('verified_email', False):
                user.email = verified_email.strip()[:254]

        # Ensure is_staff and is_superuser are never set via social signup
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=['first_name', 'last_name', 'email', 'is_staff', 'is_superuser'])

        # Ensure a Profile exists (no Aadhaar/phone/DOB/address autofill)
        from core.models import Profile
        Profile.objects.get_or_create(user=user)

        # Sanitised log — no token data, no email content logged
        logger.info(
            "Google OAuth signup completed for user id=%d; profile created.",
            user.id,
        )
        return user

    def pre_social_login(self, request, sociallogin):
        """
        Called before completing a social login (both new and returning users).
        For returning users: refresh email only if it is currently blank.
        Never overwrite existing manual data.
        """
        super().pre_social_login(request, sociallogin)

        # Only act when connecting to an existing account
        if not sociallogin.is_existing:
            return

        user = sociallogin.user
        extra_data = sociallogin.account.extra_data or {}
        changed = []

        # Refresh only a blank email from verified Google email
        if not user.email:
            verified_email = extra_data.get('email', '')
            if (extra_data.get('email_verified', False) or extra_data.get('verified_email', False)) \
                    and verified_email:
                user.email = verified_email.strip()[:254]
                changed.append('email')

        # Back-fill first/last name only if they are blank
        if not user.first_name:
            given = (extra_data.get('given_name') or '').strip()[:150]
            if given:
                user.first_name = given
                changed.append('first_name')

        if not user.last_name:
            family = (extra_data.get('family_name') or '').strip()[:150]
            if family:
                user.last_name = family
                changed.append('last_name')

        if changed:
            user.save(update_fields=changed)

        # Ensure Profile exists for returning social users
        from core.models import Profile
        Profile.objects.get_or_create(user=user)


class GramPanchayathAccountAdapter(DefaultAccountAdapter):
    """
    Standard account adapter override.
    Ensures public registration never grants privileged roles.
    """

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user
