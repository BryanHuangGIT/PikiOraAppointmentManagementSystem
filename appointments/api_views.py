
from datetime import datetime, timedelta, date

from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Doctor, Patient, Availability, Appointment

from .scheduling import (
    get_available_slots,
    is_valid_slot,
    is_future_slot,
    is_doctor_available,
)

from .serializers import (
    DoctorSerializer,
    AdminDoctorSerializer,
    PatientSerializer,
    AdminPatientSerializer,
    AvailabilitySerializer,
    AppointmentSerializer,
)


# ==========================================
# PERMISSIONS
# ==========================================

class IsAdministrator(permissions.BasePermission):

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
            approved=True,
            user__is_active=True
        ).select_related("user").order_by(
            "user__first_name",
            "user__last_name"
        )


class DoctorDetailAPIView(generics.RetrieveAPIView):

    serializer_class = DoctorSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):

        return Doctor.objects.filter(
            approved=True,
            user__is_active=True
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
            doctor__approved=True,
            doctor__user__is_active=True
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
            "date",
            "start_time"
        )


# ==========================================
# DOCTOR AVAILABLE SLOTS
# ==========================================

class DoctorAvailableSlotsAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, doctor_id):

        doctor = get_object_or_404(
            Doctor,
            pk=doctor_id,
            approved=True,
            user__is_active=True
        )

        requested_date = request.query_params.get("date")

        if not requested_date:

            return Response(
                {"error": "Date is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            selected_date = date.fromisoformat(
                requested_date
            )

        except ValueError:

            return Response(
                {"error": "Invalid date format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        slots = get_available_slots(
            doctor,
            selected_date
        )

        return Response({
            "doctor": doctor.id,
            "date": selected_date.isoformat(),
            "slot_duration_minutes": 30,
            "available_slots": slots
        })


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

    if not all([
        doctor,
        appointment_date,
        appointment_time
    ]):

        raise ValidationError(
            "Doctor, appointment date and time are required."
        )

    doctor = get_object_or_404(
        Doctor.objects.select_related("user"),
        pk=doctor.pk
    )

    # Validate doctor account.
    if not doctor.approved or not doctor.user.is_active:

        raise ValidationError(
            "This doctor is not active and approved."
        )

    # Validate clinic operating hours.
    if not is_valid_slot(
        appointment_date,
        appointment_time
    ):

        raise ValidationError(
            "Appointments must be Monday to Friday, "
            "between 9:00 AM and 5:00 PM, "
            "in 30-minute slots, "
            "and within the next 30 days."
        )

    # Prevent appointments in the past.
    if not is_future_slot(
        appointment_date,
        appointment_time
    ):

        raise ValidationError(
            "Cannot book an appointment in the past."
        )

    # Existing appointments may have been created
    # before administrator-controlled availability.
    unchanged_slot = (
        instance is not None
        and instance.doctor_id == doctor.pk
        and instance.appointment_date == appointment_date
        and instance.appointment_time == appointment_time
        and instance.status in ["Pending", "Confirmed"]
    )

    # Require availability for every new booking
    # or appointment rescheduling.
    if not unchanged_slot:

        if not is_doctor_available(
            doctor,
            appointment_date,
            appointment_time
        ):

            raise ValidationError(
                "The doctor is not available "
                "at the selected date and time."
            )

    # Prevent double bookings.
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

    @transaction.atomic
    def perform_create(self, serializer):

        try:

            patient = Patient.objects.select_for_update().get(
                user=self.request.user
            )

        except Patient.DoesNotExist:

            raise PermissionDenied(
                "Only registered patients can book appointments."
            )

        if not patient.user.is_active:

            raise PermissionDenied(
                "Inactive patient account."
            )

        doctor = serializer.validated_data.get("doctor")

        if doctor is None:

            raise ValidationError({
                "doctor": "Doctor is required."
            })

        doctor = get_object_or_404(
            Doctor.objects.select_for_update(),
            pk=doctor.pk
        )

        serializer.validated_data["doctor"] = doctor

        validate_appointment(
            serializer.validated_data
        )

        serializer.save(
            patient=patient,
            status="Pending"
        )


# ==========================================
# APPOINTMENT DETAIL AND EDITING
# ==========================================

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

    @transaction.atomic
    def perform_update(self, serializer):

        appointment = get_object_or_404(
            Appointment.objects.select_for_update(),
            pk=self.get_object().pk
        )

        if appointment.status in [
            "Cancelled",
            "Completed"
        ]:

            raise ValidationError(
                "This appointment cannot be edited."
            )

        if "status" in serializer.validated_data:

            raise ValidationError(
                "Use the appointment status "
                "or cancellation endpoint."
            )

        doctor = serializer.validated_data.get(
            "doctor",
            appointment.doctor
        )

        # Lock both doctors when changing doctors.
        list(
            Doctor.objects.select_for_update().filter(
                pk__in=[
                    appointment.doctor_id,
                    doctor.pk
                ]
            ).order_by("pk")
        )

        doctor = get_object_or_404(
            Doctor,
            pk=doctor.pk
        )

        serializer.validated_data["doctor"] = doctor

        validate_appointment(
            serializer.validated_data,
            instance=appointment
        )

        serializer.instance = appointment

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
# ADMINISTRATOR ACCOUNT HELPERS
# ==========================================

def outstanding_bookings(profile):

    return profile.appointments.filter(
        status__in=["Pending", "Confirmed"]
    ).exists()


def check_account(profile):

    if profile.user.is_staff or profile.user.is_superuser:

        raise PermissionDenied(
            "Administrator accounts cannot be managed here."
        )

    # Prevent management of accounts with conflicting roles.
    if (
        isinstance(profile, Doctor)
        and Patient.objects.filter(
            user=profile.user
        ).exists()
    ) or (
        isinstance(profile, Patient)
        and Doctor.objects.filter(
            user=profile.user
        ).exists()
    ):

        raise ValidationError(
            "This account has multiple profiles."
        )


# ==========================================
# SAFE PROFILE MANAGEMENT
# ==========================================

class SafeProfileDetailMixin:

    @transaction.atomic
    def update(self, request, *args, **kwargs):

        profile = self.get_object()

        profile = get_object_or_404(
            type(profile).objects.select_for_update(),
            pk=profile.pk
        )

        check_account(profile)

        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=kwargs.get("partial", False)
        )

        serializer.is_valid(
            raise_exception=True
        )

        disabling = (
            serializer.validated_data.get(
                "user", {}
            ).get("is_active") is False
        )

        revoking = (
            serializer.validated_data.get(
                "approved"
            ) is False
        )

        if (
            disabling or revoking
        ) and outstanding_bookings(profile):

            raise ValidationError(
                "Resolve pending and confirmed bookings first."
            )

        serializer.save()

        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):

        profile = self.get_object()

        profile = get_object_or_404(
            type(profile).objects.select_for_update(),
            pk=profile.pk
        )

        check_account(profile)

        if outstanding_bookings(profile):

            raise ValidationError(
                "Resolve pending and confirmed bookings first."
            )

        user = profile.user

        # Preserve historical appointments.
        if profile.appointments.exists():

            user.is_active = False

            user.save(
                update_fields=["is_active"]
            )

            Token.objects.filter(
                user=user
            ).delete()

            if isinstance(profile, Doctor):

                profile.approved = False

                profile.save(
                    update_fields=["approved"]
                )

            return Response({
                "message": (
                    "Account deactivated; "
                    "appointment history preserved."
                )
            })

        # Delete accounts without appointment history.
        user.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


# ==========================================
# ADMINISTRATOR - DOCTOR MANAGEMENT
# ==========================================

class AdminDoctorListCreateAPIView(
    generics.ListCreateAPIView
):

    serializer_class = AdminDoctorSerializer
    permission_classes = [IsAdministrator]

    queryset = Doctor.objects.select_related(
        "user"
    ).order_by("id")


class AdminDoctorDetailAPIView(
    SafeProfileDetailMixin,
    generics.RetrieveUpdateDestroyAPIView
):

    serializer_class = AdminDoctorSerializer
    permission_classes = [IsAdministrator]

    queryset = Doctor.objects.select_related(
        "user"
    ).all()


# ==========================================
# PROTECT EXISTING APPOINTMENTS
# ==========================================

def protect_availability(record, replacement=None):

    bookings = Appointment.objects.filter(
        doctor=record.doctor,
        appointment_date=record.date,
        appointment_time__gte=record.start_time,
        appointment_time__lt=record.end_time,
        status__in=["Pending", "Confirmed"]
    )

    for booking in bookings:

        start = datetime.combine(
            booking.appointment_date,
            booking.appointment_time
        )

        end = start + timedelta(minutes=30)

        if (
            replacement
            and replacement["doctor"].pk == record.doctor_id
            and replacement["date"] == record.date
        ):

            replacement_start = datetime.combine(
                record.date,
                replacement["start_time"]
            )

            replacement_end = datetime.combine(
                record.date,
                replacement["end_time"]
            )

            if (
                replacement_start <= start
                and end <= replacement_end
            ):

                continue

        raise ValidationError(
            "Resolve existing bookings before "
            "changing this availability."
        )


# ==========================================
# ADMINISTRATOR - CREATE AVAILABILITY
# ==========================================

class AdminAvailabilityListCreateAPIView(
    generics.ListCreateAPIView
):

    serializer_class = AvailabilitySerializer
    permission_classes = [IsAdministrator]

    queryset = Availability.objects.select_related(
        "doctor__user"
    ).order_by(
        "date",
        "start_time"
    )

    @transaction.atomic
    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        doctor = get_object_or_404(
            Doctor.objects.select_for_update(),
            pk=serializer.validated_data["doctor"].pk
        )

        # Revalidate after acquiring the doctor lock.
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(doctor=doctor)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


# ==========================================
# ADMINISTRATOR - EDIT AND REMOVE AVAILABILITY
# ==========================================

class AdminAvailabilityDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):

    serializer_class = AvailabilitySerializer
    permission_classes = [IsAdministrator]

    queryset = Availability.objects.select_related(
        "doctor__user"
    ).all()

    @transaction.atomic
    def update(self, request, *args, **kwargs):

        record = get_object_or_404(
            Availability.objects.select_for_update(),
            pk=self.get_object().pk
        )

        serializer = self.get_serializer(
            record,
            data=request.data,
            partial=kwargs.get("partial", False)
        )

        serializer.is_valid(
            raise_exception=True
        )

        new_doctor = serializer.validated_data.get(
            "doctor",
            record.doctor
        )

        list(
            Doctor.objects.select_for_update().filter(
                pk__in=[
                    record.doctor_id,
                    new_doctor.pk
                ]
            ).order_by("pk")
        )

        serializer = self.get_serializer(
            record,
            data=request.data,
            partial=kwargs.get("partial", False)
        )

        serializer.is_valid(
            raise_exception=True
        )

        replacement = {

            field: serializer.validated_data.get(
                field,
                getattr(record, field)
            )

            for field in [
                "doctor",
                "date",
                "start_time",
                "end_time"
            ]
        }

        protect_availability(
            record,
            replacement
        )

        serializer.save()

        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):

        record = get_object_or_404(
            Availability.objects.select_for_update(),
            pk=self.get_object().pk
        )

        get_object_or_404(
            Doctor.objects.select_for_update(),
            pk=record.doctor_id
        )

        protect_availability(record)

        record.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


# ==========================================
# ADMINISTRATOR - PATIENT MANAGEMENT
# ==========================================

class AdminPatientListAPIView(
    generics.ListAPIView
):

    serializer_class = AdminPatientSerializer
    permission_classes = [IsAdministrator]

    queryset = Patient.objects.select_related(
        "user"
    ).order_by("id")


class AdminPatientDetailAPIView(
    SafeProfileDetailMixin,
    generics.RetrieveUpdateDestroyAPIView
):

    serializer_class = AdminPatientSerializer
    permission_classes = [IsAdministrator]

    queryset = Patient.objects.select_related(
        "user"
    ).all()


# ==========================================
# ADMINISTRATOR - ALL APPOINTMENTS
# ==========================================

class AdminAppointmentListAPIView(
    generics.ListAPIView
):

    serializer_class = AppointmentSerializer
    permission_classes = [IsAdministrator]

    queryset = Appointment.objects.select_related(
        "patient__user",
        "doctor__user"
    ).order_by(
        "-appointment_date",
        "-appointment_time"
    )


# ==========================================
# ADMINISTRATOR - APPOINTMENT STATUS
# ==========================================

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

            transitions = {
                "Pending": [
                    "Confirmed",
                    "Cancelled"
                ],
                "Confirmed": [
                    "Completed",
                    "Cancelled"
                ],
                "Cancelled": [],
                "Completed": []
            }

            if new_status == appointment.status:

                return Response({
                    "status": appointment.status,
                    "message": "Status unchanged."
                })

            if new_status not in transitions.get(
                appointment.status,
                []
            ):

                raise ValidationError(
                    "Invalid appointment status transition."
                )

            if new_status == "Completed" and is_future_slot(
                appointment.appointment_date,
                appointment.appointment_time
            ):

                raise ValidationError(
                    "Cannot complete an appointment before it starts."
                )

            if new_status == "Confirmed":

                get_object_or_404(
                    Doctor.objects.select_for_update(),
                    pk=appointment.doctor_id
                )

                validate_appointment(
                    {
                        "doctor": appointment.doctor,
                        "appointment_date": appointment.appointment_date,
                        "appointment_time": appointment.appointment_time
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


# ==========================================
# DOCTOR DASHBOARD - VIEW APPOINTMENTS
# ==========================================

class DoctorAppointmentsAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):

        try:

            doctor = Doctor.objects.select_related(
                "user"
            ).get(
                user=request.user,
                approved=True,
                user__is_active=True
            )

        except Doctor.DoesNotExist:

            return Response(
                {
                    "detail": "Approved doctor account not found."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        appointments = Appointment.objects.filter(
            doctor=doctor
        ).select_related(
            "patient__user",
            "doctor__user"
        ).order_by(
            "appointment_date",
            "appointment_time"
        )

        serializer = AppointmentSerializer(
            appointments,
            many=True
        )

        return Response({
            "doctor_name": doctor.user.get_full_name(),
            "appointments": serializer.data
        })


# ==========================================
# DOCTOR - UPDATE APPOINTMENT STATUS
# ==========================================

class DoctorAppointmentStatusAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):

        new_status = request.data.get("status")

        if new_status not in [
            "Confirmed",
            "Completed"
        ]:

            return Response(
                {
                    "error": (
                        "Doctors can only confirm or "
                        "complete appointments."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():

            try:

                doctor = Doctor.objects.get(
                    user=request.user,
                    approved=True,
                    user__is_active=True
                )

            except Doctor.DoesNotExist:

                return Response(
                    {
                        "error": "Approved doctor account required."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            appointment = get_object_or_404(
                Appointment.objects.select_for_update(),
                pk=pk,
                doctor=doctor
            )

            # Refresh doctor status after locking.
            doctor = get_object_or_404(
                Doctor.objects.select_for_update(),
                pk=doctor.pk,
                approved=True,
                user__is_active=True
            )

            current_status = appointment.status

            if new_status == "Confirmed":

                if current_status != "Pending":

                    raise ValidationError(
                        "Only pending appointments can be confirmed."
                    )

                validate_appointment(
                    {
                        "doctor": doctor,
                        "appointment_date": appointment.appointment_date,
                        "appointment_time": appointment.appointment_time
                    },
                    instance=appointment
                )

            elif new_status == "Completed":

                if current_status != "Confirmed":

                    raise ValidationError(
                        "Only confirmed appointments can be completed."
                    )

                appointment_start = timezone.make_aware(
                    datetime.combine(
                        appointment.appointment_date,
                        appointment.appointment_time
                    ),
                    timezone.get_current_timezone()
                )

                if appointment_start > timezone.now():

                    raise ValidationError(
                        "A consultation cannot be "
                        "completed before it starts."
                    )

            appointment.status = new_status

            appointment.save(
                update_fields=["status"]
            )

        return Response({
            "message": "Appointment status updated successfully.",
            "appointment_id": appointment.id,
            "status": appointment.status
        })
