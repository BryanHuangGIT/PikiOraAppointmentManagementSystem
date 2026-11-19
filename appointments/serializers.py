
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from .models import Doctor, Patient, Availability, Appointment

from .scheduling import OPENING_TIME, CLOSING_TIME


# ==========================================
# USER SERIALIZER
# ==========================================

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email"
        ]

        read_only_fields = ["id"]


# ==========================================
# ADMIN USER SERIALIZER
# ==========================================

class AdminUserSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False
    )

    username = serializers.CharField(max_length=150)

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "is_active"
        ]

        read_only_fields = ["id"]


# ==========================================
# ADMIN ACCOUNT VALIDATION
# ==========================================

def validate_admin_user(user_data, instance=None):

    user = instance.user if instance else None

    username = user_data.get(
        "username",
        user.username if user else None
    )

    password = user_data.get("password")

    if not username:
        raise serializers.ValidationError({
            "username": "Username is required."
        })

    username = User.normalize_username(username)
    user_data["username"] = username

    existing_users = User.objects.filter(
        username=username
    )

    if user:
        existing_users = existing_users.exclude(
            pk=user.pk
        )

    if existing_users.exists():
        raise serializers.ValidationError({
            "username": "This username is already taken."
        })

    username_field = User._meta.get_field("username")

    try:
        username_field.clean(username, user)

    except DjangoValidationError as exc:
        raise serializers.ValidationError({
            "username": exc.messages
        })

    if not instance and not password:
        raise serializers.ValidationError({
            "password": "Password is required."
        })

    if password:

        candidate_user = User(
            username=username,
            first_name=user_data.get(
                "first_name",
                user.first_name if user else ""
            ),
            last_name=user_data.get(
                "last_name",
                user.last_name if user else ""
            ),
            email=user_data.get(
                "email",
                user.email if user else ""
            )
        )

        try:
            validate_password(
                password,
                candidate_user
            )

        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": exc.messages
            })


# ==========================================
# ADMIN ACCOUNT UPDATE
# ==========================================

def update_admin_user(user, user_data):

    password = user_data.pop("password", None)

    allowed_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active"
    ]

    for field in allowed_fields:

        if field in user_data:
            setattr(user, field, user_data[field])

    if password:
        user.set_password(password)

    user.save()

    if password or not user.is_active:

        Token.objects.filter(
            user=user
        ).delete()

    return user


# ==========================================
# DOCTOR SERIALIZER
# ==========================================

class DoctorSerializer(serializers.ModelSerializer):

    user = UserSerializer(read_only=True)

    doctor_name = serializers.SerializerMethodField()

    class Meta:
        model = Doctor

        fields = [
            "id",
            "user",
            "doctor_name",
            "specialization",
            "phone",
            "approved"
        ]

    def get_doctor_name(self, obj):

        return (
            f"Dr. {obj.user.first_name} "
            f"{obj.user.last_name}"
        ).strip()


# ==========================================
# ADMIN DOCTOR SERIALIZER
# ==========================================

class AdminDoctorSerializer(DoctorSerializer):

    user = AdminUserSerializer()

    def validate(self, data):

        user_data = data.get("user")

        if self.instance is None and not user_data:

            raise serializers.ValidationError({
                "user": "Doctor account information is required."
            })

        if user_data is not None:

            try:

                validate_admin_user(
                    user_data,
                    self.instance
                )

            except serializers.ValidationError as exc:

                raise serializers.ValidationError({
                    "user": exc.detail
                })

        return data

    @transaction.atomic
    def create(self, validated_data):

        user_data = validated_data.pop("user")

        user = User.objects.create_user(
            **user_data,
            is_staff=False,
            is_superuser=False
        )

        doctor = Doctor.objects.create(
            user=user,
            **validated_data
        )

        return doctor

    @transaction.atomic
    def update(self, instance, validated_data):

        user_data = validated_data.pop(
            "user",
            None
        )

        if user_data is not None:

            update_admin_user(
                instance.user,
                user_data
            )

        for field, value in validated_data.items():

            setattr(instance, field, value)

        instance.save()

        return instance


# ==========================================
# PATIENT SERIALIZER
# ==========================================

class PatientSerializer(serializers.ModelSerializer):

    user = UserSerializer(read_only=True)

    class Meta:
        model = Patient

        fields = [
            "id",
            "user",
            "phone",
            "date_of_birth"
        ]


# ==========================================
# ADMIN PATIENT SERIALIZER
# ==========================================

class AdminPatientSerializer(PatientSerializer):

    user = AdminUserSerializer(required=False)

    def validate(self, data):

        user_data = data.get("user")

        if user_data is not None:

            try:

                validate_admin_user(
                    user_data,
                    self.instance
                )

            except serializers.ValidationError as exc:

                raise serializers.ValidationError({
                    "user": exc.detail
                })

        date_of_birth = data.get(
            "date_of_birth",
            getattr(
                self.instance,
                "date_of_birth",
                None
            )
        )

        if (
            date_of_birth
            and date_of_birth > timezone.localdate()
        ):

            raise serializers.ValidationError({
                "date_of_birth": (
                    "Date of birth cannot be in the future."
                )
            })

        return data

    @transaction.atomic
    def update(self, instance, validated_data):

        user_data = validated_data.pop(
            "user",
            None
        )

        if user_data is not None:

            update_admin_user(
                instance.user,
                user_data
            )

        for field, value in validated_data.items():

            setattr(instance, field, value)

        instance.save()

        return instance


# ==========================================
# AVAILABILITY SERIALIZER
# ==========================================

class AvailabilitySerializer(serializers.ModelSerializer):

    doctor_name = serializers.CharField(
        source="doctor.user.get_full_name",
        read_only=True
    )

    class Meta:
        model = Availability

        fields = [
            "id",
            "doctor",
            "doctor_name",
            "date",
            "start_time",
            "end_time"
        ]

    def validate(self, data):

        doctor = data.get(
            "doctor",
            getattr(self.instance, "doctor", None)
        )

        selected_date = data.get(
            "date",
            getattr(self.instance, "date", None)
        )

        start_time = data.get(
            "start_time",
            getattr(self.instance, "start_time", None)
        )

        end_time = data.get(
            "end_time",
            getattr(self.instance, "end_time", None)
        )

        # Doctor must be approved and active.
        if doctor and (
            not doctor.approved
            or not doctor.user.is_active
        ):

            raise serializers.ValidationError({
                "doctor": "Doctor must be active and approved."
            })

        # Prevent availability in the past.
        if (
            selected_date
            and selected_date < timezone.localdate()
        ):

            raise serializers.ValidationError({
                "date": "Availability cannot be in the past."
            })

        # Monday to Friday only.
        if (
            selected_date
            and selected_date.weekday() >= 5
        ):

            raise serializers.ValidationError({
                "date": "Availability must be Monday to Friday."
            })

        # End time must be later than start time.
        if start_time and end_time:

            if start_time >= end_time:

                raise serializers.ValidationError({
                    "end_time": (
                        "End time must be later than start time."
                    )
                })

            # Clinic operating hours.
            if (
                start_time < OPENING_TIME
                or end_time > CLOSING_TIME
            ):

                raise serializers.ValidationError(
                    "Availability must be between "
                    "9:00 AM and 5:00 PM."
                )

        # Require 30-minute intervals.
        for field_name, time_value in [
            ("start_time", start_time),
            ("end_time", end_time)
        ]:

            if time_value and (
                time_value.minute not in (0, 30)
                or time_value.second != 0
                or time_value.microsecond != 0
            ):

                raise serializers.ValidationError({
                    field_name: (
                        "Time must follow 30-minute intervals."
                    )
                })

        # Prevent overlapping availability.
        if (
            doctor
            and selected_date
            and start_time
            and end_time
        ):

            overlapping = Availability.objects.filter(
                doctor=doctor,
                date=selected_date,
                start_time__lt=end_time,
                end_time__gt=start_time
            )

            if self.instance:

                overlapping = overlapping.exclude(
                    pk=self.instance.pk
                )

            if overlapping.exists():

                raise serializers.ValidationError(
                    "This availability overlaps "
                    "an existing time range."
                )

        return data


# ==========================================
# APPOINTMENT SERIALIZER
# ==========================================

class AppointmentSerializer(serializers.ModelSerializer):

    doctor_name = serializers.CharField(
        source="doctor.user.get_full_name",
        read_only=True
    )

    patient_name = serializers.CharField(
        source="patient.user.get_full_name",
        read_only=True
    )

    class Meta:
        model = Appointment

        fields = [
            "id",
            "patient",
            "patient_name",
            "doctor",
            "doctor_name",
            "appointment_date",
            "appointment_time",
            "reason",
            "status",
            "created_at"
        ]

        read_only_fields = [
            "id",
            "patient",
            "patient_name",
            "doctor_name",
            "created_at"
        ]
