"""
validators_tags — Template filter for safe Aadhaar masking in templates.

Usage:
    {% load validators_tags %}
    {{ profile.aadhar_number|mask_aadhar_display }}

Security: Never renders the actual Aadhaar digits in the first 8 positions.
"""
from django import template
from core.validators import mask_aadhar

register = template.Library()


@register.filter(name='mask_aadhar_display')
def mask_aadhar_display(value):
    """
    Template filter: returns masked Aadhaar string (XXXX-XXXX-1234).
    Safe for display in HTML templates.
    """
    return mask_aadhar(value or '')
