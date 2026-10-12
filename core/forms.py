from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Profile, Complaint, Application, Service
from .validators import validate_complaint_attachment, validate_aadhar_number

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
                    'class': 'block w-full pl-11 pr-3 py-2 sm:text-sm border-gray-300 dark:border-gray-600 rounded-md focus:ring-primary focus:border-primary dark:bg-gray-700 dark:text-white dark:placeholder-gray-400',
                })
        self.fields['username'].widget.attrs['placeholder'] = 'Enter your username'
        self.fields['email'].widget.attrs['placeholder'] = 'Enter your email address'
        self.fields['password1'].widget.attrs['placeholder'] = 'Create a strong password (min 8 characters)'
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
                'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-white'
            })


class ProfileUpdateForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    
    class Meta:
        model = Profile
        fields = ['phone_number', 'address', 'aadhar_number', 'date_of_birth']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-white'
            })

    def clean_aadhar_number(self):
        aadhar = self.cleaned_data.get('aadhar_number', '').strip()
        if aadhar:
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