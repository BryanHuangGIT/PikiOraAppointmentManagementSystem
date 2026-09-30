from django import forms
from django.contrib.auth.models import User
from .models import Doctor, Patient


class PatientRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password"]


class DoctorRegistrationForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(
        widget=forms.PasswordInput
    )

    specialization = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=20)

    class Meta:
        model = Doctor
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "specialization",
            "phone",
        ]