from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Profile, Complaint, Application, Service
from .validators import validate_complaint_attachment, validate_aadhar_number, mask_aadhar

class CustomUserCreationForm(UserCreationForm):
    """
    Public registration form for citizens.
    Explicitly restricts fields to prevent privilege escalation (cannot set is_staff, is_superuser, groups).
    Enforces strong password validation.
    """
    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['username', 'email', 'password1', 'password2']:
            if field in self.fields:
                self.fields[field].widget.attrs.update({
                    'class': 'block w-full px-3 py-2.5 text-xs sm:text-sm bg-[#FAF6EE] dark:bg-[#1E1E19] text-ink dark:text-paper border border-[#D8CDBB] dark:border-[#3E3E34] rounded-none focus:border-rust transition-colors placeholder:text-stone',
                })
        self.fields['username'].widget.attrs['placeholder'] = 'Enter your username'
        self.fields['email'].widget.attrs['placeholder'] = 'Enter your email address'
        self.fields['password1'].widget.attrs['placeholder'] = 'Create strong password (min 8 characters)'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm your password'

    def save(self, commit=True):
        user = super().save(commit=False)
        # Enforce that public self-registration CAN NEVER grant privileged roles
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            Profile.objects.get_or_create(user=user)
        return user


class UserUpdateForm(forms.ModelForm):
    """
    User update form restricted to non-sensitive profile attributes.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'block w-full px-3 py-2.5 text-xs sm:text-sm bg-[#FAF6EE] dark:bg-[#1E1E19] text-ink dark:text-paper border border-[#D8CDBB] dark:border-[#3E3E34] rounded-none focus:border-rust transition-colors'
            })


class ProfileUpdateForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    aadhar_number = forms.CharField(
        max_length=20,
        required=False,
        label="Aadhaar Reference Number",
        help_text=(
            "12-digit Aadhaar number. Spaces and hyphens are accepted. "
            "ಆಧಾರ್ ಸಂಖ್ಯೆ. आधार संख्या।"
        ),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'id': 'id_aadhar_number',
        }),
    )

    class Meta:
        model = Profile
        fields = ['phone_number', 'address', 'aadhar_number', 'date_of_birth']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'block w-full px-3 py-2.5 text-xs sm:text-sm bg-[#FAF6EE] dark:bg-[#1E1E19] text-ink dark:text-paper border border-[#D8CDBB] dark:border-[#3E3E34] rounded-none focus:border-rust transition-colors'
            })
        # Show masked Aadhaar in the input when an existing value is stored
        if self.instance and self.instance.pk and self.instance.aadhar_number:
            self.initial['aadhar_number'] = mask_aadhar(self.instance.aadhar_number)

    def clean_aadhar_number(self):
        aadhar = self.cleaned_data.get('aadhar_number', '').strip()
        # If user submitted the masked placeholder unchanged, keep existing value
        if aadhar and aadhar.startswith('XXXX') and self.instance and self.instance.pk:
            existing = self.instance.aadhar_number
            if existing:
                return existing  # Return persisted real value unchanged
        if aadhar:
            # Normalise separators before validation
            validate_aadhar_number(aadhar)
        return aadhar


class ComplaintForm(forms.ModelForm):
    """
    Citizen complaint submission form with file upload security checks.
    """
    class Meta:
        model = Complaint
        fields = ['category', 'subject', 'location', 'description', 'attachment']

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_complaint_attachment(attachment)
        return attachment


class ServiceApplicationForm(forms.Form):
    full_name = forms.CharField(max_length=100, required=True)
    aadhar_number = forms.CharField(max_length=20, required=True)
    address = forms.CharField(widget=forms.Textarea, required=True)

    def clean_aadhar_number(self):
        aadhar = self.cleaned_data.get('aadhar_number', '').strip()
        validate_aadhar_number(aadhar)
        return aadhar