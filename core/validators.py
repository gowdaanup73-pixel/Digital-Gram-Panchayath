import os
from django.core.exceptions import ValidationError
from django.conf import settings

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

def validate_aadhar_number(value):
    """
    Validates that an Aadhar number is 12 digits (or masked 12-digit string).
    """
    cleaned = str(value).strip().replace(" ", "").replace("-", "")
    if not cleaned.isdigit() or len(cleaned) != 12:
        raise ValidationError("Aadhar number must be exactly 12 digits.")
