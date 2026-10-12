"""
Validators for Digital Gram Panchayath.

Security & Privacy notes
------------------------
- Aadhaar numbers are NEVER logged, serialised to URLs, or included in
  unguarded error messages.
- Masked display ("XXXXXXXX1234") is the only safe way to show a stored
  Aadhaar on-screen.
- validate_aadhar_number() accepts an empty string (returns silently) so
  the field can remain optional. Callers that require a value must add
  required=True or assert it before calling.
- Verhoeff validation rejects numbers that are structurally invalid
  according to the published UIDAI algorithm test vectors; it is NOT a
  live UIDAI lookup and does NOT confirm identity.
"""

import os
import logging

from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_ATTACHMENT_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE', 5 * 1024 * 1024)


def validate_complaint_attachment(file_obj):
    """
    Validates file extension and size to prevent malicious file execution
    and storage exhaustion.
    """
    if not file_obj:
        return

    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}."
        )

    if file_obj.size > MAX_ATTACHMENT_SIZE:
        max_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
        raise ValidationError(
            f"File size exceeds the {max_mb:.0f}MB limit. Uploaded file is {file_obj.size / (1024 * 1024):.1f}MB."
        )


# ============================================================================
# Verhoeff Checksum Algorithm (UIDAI Aadhaar standard)
# Reference: https://en.wikipedia.org/wiki/Verhoeff_algorithm
# Test vectors: generated with the published multiplication/permutation tables.
# ============================================================================

# Dihedral group D5 multiplication table
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def validate_verhoeff(num_str: str) -> bool:
    """
    Validates a numeric string against the Verhoeff checksum algorithm.
    Returns True if the full number (including check digit) is valid, False otherwise.
    Treats any non-digit character as invalid.
    """
    c = 0
    for i, digit_char in enumerate(reversed(str(num_str))):
        if not digit_char.isdigit():
            return False
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit_char)]]
    return c == 0


def generate_verhoeff_check_digit(num_str: str) -> str:
    """
    Calculates the Verhoeff check digit for an n-digit numerical prefix.
    Useful for generating valid test numbers in unit tests.
    """
    c = 0
    for i, digit_char in enumerate(reversed(str(num_str))):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(digit_char)]]
    return str(_VERHOEFF_INV[c])


# ---------------------------------------------------------------------------
# Localised validation error messages (English / Kannada / Hindi)
# ---------------------------------------------------------------------------

_MSG_REQUIRED = _(
    "Aadhaar number is required. / "
    "ಆಧಾರ್ ಸಂಖ್ಯೆ ಅಗತ್ಯವಿದೆ. / "
    "आधार संख्या आवश्यक है।"
)

_MSG_DIGITS_ONLY = _(
    "Aadhaar number must contain only numeric digits. / "
    "ಆಧಾರ್ ಸಂಖ್ಯೆ ಕೇವಲ ಅಂಕಿಗಳನ್ನು ಹೊಂದಿರಬೇಕು. / "
    "आधार संख्या केवल अंकों से बनी होनी चाहिए।"
)

_MSG_LENGTH = _(
    "Aadhaar number must be exactly 12 digits. / "
    "ಆಧಾರ್ ಸಂಖ್ಯೆ ನಿಖರವಾಗಿ 12 ಅಂಕಿಗಳನ್ನು ಹೊಂದಿರಬೇಕು. / "
    "आधार संख्या ठीक 12 अंकों की होनी चाहिए।"
)

_MSG_CHECKSUM = _(
    "Invalid Aadhaar number: checksum verification failed. "
    "Please double-check the number and try again. / "
    "ಅಮಾನ್ಯ ಆಧಾರ್ ಸಂಖ್ಯೆ: ಚೆಕ್‌ಸಮ್ ಪರಿಶೀಲನೆ ವಿಫಲಗೊಂಡಿದೆ. / "
    "अमान्य आधार संख्या: चेकसम सत्यापन विफल हुआ।"
)

_MSG_MASKED_INVALID = _(
    "Invalid masked Aadhaar format. Must be XXXXXXXX1234. / "
    "ಅಮಾನ್ಯ ಮರೆಮಾಡಲಾದ ಆಧಾರ್ ಫಾರ್ಮ್ಯಾಟ್. XXXXXXXX1234 ಆಗಿರಬೇಕು. / "
    "अमान्य मास्क किया गया आधार फ़ॉर्मेट। XXXXXXXX1234 होना चाहिए।"
)

_MSG_FIRST_DIGIT = _(
    "Aadhaar number cannot start with 0 or 1. / "
    "ಆಧಾರ್ ಸಂಖ್ಯೆ 0 ಅಥವಾ 1 ರಿಂದ ಪ್ರಾರಂಭವಾಗಬಾರದು. / "
    "आधार संख्या 0 या 1 से शुरू नहीं हो सकती।"
)


def validate_aadhar_number(value):
    """
    Validates an Aadhaar number with the following rules:
      1. Optional field — empty string is accepted silently (use required=True for mandatory).
      2. Spaces and hyphens are stripped (the profile form supports these as separators).
      3. Masked format (XXXXXXXX1234 or XXXX-XXXX-1234) is accepted without checksum.
      4. Full numbers must be exactly 12 digits.
      5. First digit must not be 0 or 1 (UIDAI specification).
      6. Must pass the Verhoeff checksum algorithm.

    Security: ValidationError messages never include the submitted value.
    Logging: Number is never logged at any level.
    """
    if not value:
        # Field is optional; callers requiring a value must enforce it separately
        return

    cleaned = str(value).strip().replace(" ", "").replace("-", "")

    # ── Masked Aadhaar (XXXXXXXX1234) ──────────────────────────────────────
    if len(cleaned) == 12:
        prefix = cleaned[:8].upper()
        suffix = cleaned[8:]
        if prefix in ("XXXXXXXX", "XXXXXXXX", "XXXXXXXX") or prefix[0] in ('X', 'x', '*'):
            if prefix.upper() in ("XXXXXXXX", "XXXXXXXX") and suffix.isdigit():
                return  # Valid masked format — accept
            raise ValidationError(_MSG_MASKED_INVALID)

    # ── Digits only ────────────────────────────────────────────────────────
    if not cleaned.isdigit():
        raise ValidationError(_MSG_DIGITS_ONLY)

    # ── Length ─────────────────────────────────────────────────────────────
    if len(cleaned) != 12:
        raise ValidationError(_MSG_LENGTH)

    # ── First digit rule (UIDAI: must be 2–9) ─────────────────────────────
    if cleaned[0] in ('0', '1'):
        raise ValidationError(_MSG_FIRST_DIGIT)

    # ── Verhoeff checksum ─────────────────────────────────────────────────
    if not validate_verhoeff(cleaned):
        raise ValidationError(_MSG_CHECKSUM)


def mask_aadhar(value: str) -> str:
    """
    Returns a masked representation of an Aadhaar number for safe display.
    Masks the first 8 digits regardless of original masking state.

    e.g. "987654321012" → "XXXX-XXXX-1012"
         "" → ""
         "XXXXXXXX1234" → "XXXX-XXXX-1234"

    Never raises; always returns a string.
    """
    if not value:
        return ""
    cleaned = str(value).strip().replace(" ", "").replace("-", "")
    if len(cleaned) < 4:
        return "XXXX-XXXX-XXXX"
    last4 = cleaned[-4:] if cleaned[-4:].isdigit() else "XXXX"
    return f"XXXX-XXXX-{last4}"
