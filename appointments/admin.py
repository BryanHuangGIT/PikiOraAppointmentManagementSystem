from django.contrib import admin
from .models import Doctor, Patient, Appointment, Availability


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialization",
        "phone",
        "approved",
    )

    list_filter = ("approved", "specialization")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "phone",
        "date_of_birth",
    )


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "doctor",
        "appointment_date",
        "appointment_time",
        "status",
    )

    list_filter = ("status", "appointment_date")

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "date",
        "start_time",
        "end_time",
    )

    list_filter = (
        "date",
        "doctor",
    )