
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Doctor, Patient, Availability, Appointment


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
        start_time = data.get(
            "start_time",
            getattr(self.instance, "start_time", None)
        )

        end_time = data.get(
            "end_time",
            getattr(self.instance, "end_time", None)
        )

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                "End time must be later than start time."
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
