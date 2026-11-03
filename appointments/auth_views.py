
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction

from rest_framework import generics, permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Patient


# ==========================================
# PATIENT REGISTRATION
# ==========================================

class PatientRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    phone = serializers.CharField(
        write_only=True,
        max_length=20
    )

    date_of_birth = serializers.DateField(
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "phone",
            "date_of_birth",
        ]
        read_only_fields = ["id"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value

    def create(self, validated_data):
        phone = validated_data.pop("phone")
        date_of_birth = validated_data.pop(
            "date_of_birth", None
        )
        password = validated_data.pop("password")

        with transaction.atomic():
            user = User.objects.create_user(
                password=password,
                **validated_data
            )

            Patient.objects.create(
                user=user,
                phone=phone,
                date_of_birth=date_of_birth
            )

        return user


class PatientRegistrationAPIView(generics.CreateAPIView):
    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# ==========================================
# LOGIN
# ==========================================

class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {
                    "error": "Username and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None or not user.is_active:
            return Response(
                {
                    "error": "Invalid username or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Prevent unapproved doctors from logging in
        if hasattr(user, "doctor") and not user.doctor.approved:
            return Response(
                {
                    "error": "Your doctor account is awaiting approval."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        token, created = Token.objects.get_or_create(
            user=user
        )

        if user.is_staff:
            role = "admin"
        elif hasattr(user, "patient"):
            role = "patient"
        elif hasattr(user, "doctor"):
            role = "doctor"
        else:
            role = "other"

        return Response({
            "message": "Login successful.",
            "token": token.key,
            "role": role,
            "username": user.username
        })


# ==========================================
# CURRENT USER
# ==========================================

class CurrentUserAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_staff:
            role = "admin"
        elif hasattr(user, "patient"):
            role = "patient"
        elif hasattr(user, "doctor"):
            role = "doctor"
        else:
            role = "other"

        return Response({
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": role
        })


# ==========================================
# LOGOUT
# ==========================================

class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        request.auth.delete()

        return Response({
            "message": "Logged out successfully."
        })
