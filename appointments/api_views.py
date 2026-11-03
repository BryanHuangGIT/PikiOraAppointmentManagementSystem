
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Doctor, Patient, Availability, Appointment
from .serializers import (
    DoctorSerializer,
    PatientSerializer,
    AvailabilitySerializer,
    AppointmentSerializer,
)


# ==========================================
# PERMISSIONS
# ==========================================

class IsAdministrator(permissions.BasePermission):
    """
    Only Django staff users can access administrator APIs.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_staff
        )


# ==========================================
# DOCTOR API
# ==========================================

class DoctorListAPIView(generics.ListAPIView):
    serializer_class = DoctorSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Doctor.objects.filter(
            approved=True
        ).select_related("user").order_by(
            "user__first_name", "user__last_name"
        )


class DoctorDetailAPIView(generics.RetrieveAPIView):
    serializer_class = DoctorSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Doctor.objects.filter(
            approved=True
        ).select_related("user")


# ==========================================
# AVAILABILITY API
# ==========================================

class AvailabilityListAPIView(generics.ListAPIView):
    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Availability.objects.filter(
            date__gte=timezone.localdate(),
            doctor__approved=True
        ).select_related("doctor__user")

        doctor_id = self.request.query_params.get("doctor")

        if doctor_id:
            if not doctor_id.isdigit():
                raise ValidationError({
                    "doctor": "A valid doctor ID is required."
                })

            queryset = queryset.filter(
                doctor_id=int(doctor_id)
            )

        return queryset.order_by(
            "date", "start_time"
        )


# ==========================================
# PATIENT PROFILE API
# ==========================================

class PatientProfileAPIView(generics.RetrieveAPIView):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            return Patient.objects.select_related(
                "user"
            ).get(user=self.request.user)

        except Patient.DoesNotExist:
            raise PermissionDenied(
                "This account does not have a patient profile."
            )


# ==========================================
# APPOINTMENT VALIDATION
# ==========================================

def validate_appointment(data, instance=None):
    """
    Validates:
    1. Doctor approval
    2. Date and time
    3. 30-minute appointment slots
    4. Doctor availability
    5. Double booking
    """

    doctor = data.get(
        "doctor",
        instance.doctor if instance else None
    )

    appointment_date = data.get(
        "appointment_date",
        instance.appointment_date if instance else None
    )

    appointment_time = data.get(
        "appointment_time",
        instance.appointment_time if instance else None
    )

    if not doctor or not appointment_date or not appointment_time:
        raise ValidationError(
            "Doctor, appointment date and time are required."
        )

    if not doctor.approved:
        raise ValidationError(
            "This doctor has not been approved."
        )

    today = timezone.localdate()
    now = timezone.localtime()

    if appointment_date < today:
        raise ValidationError(
            "Appointments cannot be booked in the past."
        )

    if appointment_date == today:
        current_time = now.time().replace(tzinfo=None)

        if appointment_time <= current_time:
            raise ValidationError(
                "You cannot book a past appointment time."
            )

    # Appointment must start at :00 or :30
    if (
        appointment_time.minute not in (0, 30)
        or appointment_time.second != 0
        or appointment_time.microsecond != 0
    ):
        raise ValidationError(
            "Appointments must start on a 30-minute interval."
        )

    # Calculate appointment ending time
    appointment_end = (
        datetime.combine(
            appointment_date,
            appointment_time
        ) + timedelta(minutes=30)
    ).time()

    if appointment_end <= appointment_time:
        raise ValidationError(
            "Invalid appointment time."
        )

    # Check doctor availability
    availability_exists = Availability.objects.filter(
        doctor=doctor,
        date=appointment_date,
        start_time__lte=appointment_time,
        end_time__gte=appointment_end
    ).exists()

    if not availability_exists:
        raise ValidationError(
            "The doctor is unavailable at the selected time."
        )

    # Prevent double booking
    existing_bookings = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status__in=["Pending", "Confirmed"]
    )

    if instance is not None:
        existing_bookings = existing_bookings.exclude(
            pk=instance.pk
        )

    if existing_bookings.exists():
        raise ValidationError(
            "This appointment slot has already been booked."
        )


# ==========================================
# PATIENT APPOINTMENTS
# ==========================================

class AppointmentListCreateAPIView(
    generics.ListCreateAPIView
):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Appointment.objects.select_related(
            "patient__user",
            "doctor__user"
        )

        if self.request.user.is_staff:
            return queryset.order_by(
                "-appointment_date",
                "-appointment_time"
            )

        return queryset.filter(
            patient__user=self.request.user
        ).order_by(
            "-appointment_date",
            "-appointment_time"
        )

    def perform_create(self, serializer):
        try:
            patient = Patient.objects.get(
                user=self.request.user
            )
        except Patient.DoesNotExist:
            raise PermissionDenied(
                "Only registered patients can book appointments."
            )

        with transaction.atomic():
            doctor = serializer.validated_data.get("doctor")

            if doctor is None:
                raise ValidationError({
                    "doctor": "Doctor is required."
                })

            # Lock doctor row where supported
            Doctor.objects.select_for_update().get(
                pk=doctor.pk
            )

            validate_appointment(
                serializer.validated_data
            )

            serializer.save(
                patient=patient,
                status="Pending"
            )


class AppointmentDetailAPIView(
    generics.RetrieveUpdateAPIView
):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Appointment.objects.select_related(
            "patient__user",
            "doctor__user"
        )

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(
            patient__user=self.request.user
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            appointment = self.get_object()

            if appointment.status in [
                "Cancelled", "Completed"
            ]:
                raise ValidationError(
                    "This appointment cannot be edited."
                )

            if "status" in serializer.validated_data:
                raise ValidationError(
                    "Use the cancellation endpoint to cancel an appointment."
                )

            doctor = serializer.validated_data.get(
                "doctor", appointment.doctor
            )

            Doctor.objects.select_for_update().get(
                pk=doctor.pk
            )

            validate_appointment(
                serializer.validated_data,
                instance=appointment
            )

            serializer.save()


# ==========================================
# CANCEL APPOINTMENT
# ==========================================

class AppointmentCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        with transaction.atomic():
            queryset = Appointment.objects.select_for_update()

            if not request.user.is_staff:
                queryset = queryset.filter(
                    patient__user=request.user
                )

            appointment = get_object_or_404(
                queryset,
                pk=pk
            )

            if appointment.status == "Completed":
                return Response(
                    {
                        "error": (
                            "Completed appointments "
                            "cannot be cancelled."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if appointment.status == "Cancelled":
                return Response({
                    "message": "Appointment is already cancelled."
                })

            appointment.status = "Cancelled"
            appointment.save(
                update_fields=["status"]
            )

        return Response({
            "message": "Appointment cancelled successfully."
        })


# ==========================================
# ADMINISTRATOR - DOCTORS
# ==========================================

class AdminDoctorListCreateAPIView(
    generics.ListCreateAPIView
):
    serializer_class = DoctorSerializer
    permission_classes = [IsAdministrator]

    queryset = Doctor.objects.select_related(
        "user"
    ).all()

    def perform_create(self, serializer):
        raise ValidationError(
            "Doctor creation requires a linked user account. "
            "Use the doctor registration workflow."
        )


class AdminDoctorDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = DoctorSerializer
    permission_classes = [IsAdministrator]

    queryset = Doctor.objects.select_related(
        "user"
    ).all()


# ==========================================
# ADMINISTRATOR - AVAILABILITY
# ==========================================

class AdminAvailabilityListCreateAPIView(
    generics.ListCreateAPIView
):
    serializer_class = AvailabilitySerializer
    permission_classes = [IsAdministrator]

    queryset = Availability.objects.select_related(
        "doctor__user"
    ).all()


class AdminAvailabilityDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = AvailabilitySerializer
    permission_classes = [IsAdministrator]

    queryset = Availability.objects.select_related(
        "doctor__user"
    ).all()


# ==========================================
# ADMINISTRATOR - PATIENTS
# ==========================================

class AdminPatientListAPIView(
    generics.ListAPIView
):
    serializer_class = PatientSerializer
    permission_classes = [IsAdministrator]

    queryset = Patient.objects.select_related(
        "user"
    ).all()


class AdminPatientDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = PatientSerializer
    permission_classes = [IsAdministrator]

    queryset = Patient.objects.select_related(
        "user"
    ).all()


# ==========================================
# ADMINISTRATOR - APPOINTMENTS
# ==========================================

class AdminAppointmentListAPIView(
    generics.ListAPIView
):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAdministrator]

    queryset = Appointment.objects.select_related(
        "patient__user",
        "doctor__user"
    ).all()


class AdminAppointmentStatusAPIView(APIView):
    permission_classes = [IsAdministrator]

    def patch(self, request, pk):
        new_status = request.data.get("status")

        valid_statuses = [
            "Pending",
            "Confirmed",
            "Cancelled",
            "Completed"
        ]

        if new_status not in valid_statuses:
            return Response(
                {"error": "Invalid appointment status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            appointment = get_object_or_404(
                Appointment.objects.select_for_update(),
                pk=pk
            )

            if new_status in ["Pending", "Confirmed"]:
                Doctor.objects.select_for_update().get(
                    pk=appointment.doctor_id
                )

                validate_appointment(
                    {
                        "doctor": appointment.doctor,
                        "appointment_date": appointment.appointment_date,
                        "appointment_time": appointment.appointment_time,
                    },
                    instance=appointment
                )

            appointment.status = new_status
            appointment.save(
                update_fields=["status"]
            )

        return Response({
            "message": "Appointment status updated successfully.",
            "status": appointment.status
        })
