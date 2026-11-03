from django.urls import path

from .api_views import (
    DoctorListAPIView,
    DoctorDetailAPIView,
    AvailabilityListAPIView,
    PatientProfileAPIView,
    AppointmentListCreateAPIView,
    AppointmentDetailAPIView,
    AppointmentCancelAPIView,
    AdminDoctorListCreateAPIView,
    AdminDoctorDetailAPIView,
    AdminAvailabilityListCreateAPIView,
    AdminAvailabilityDetailAPIView,
    AdminPatientListAPIView,
    AdminPatientDetailAPIView,
    AdminAppointmentListAPIView,
    AdminAppointmentStatusAPIView
)

urlpatterns = [

    # Public doctor information
    path(
        "doctors/",
        DoctorListAPIView.as_view(),
        name="api-doctors"
    ),
    path(
        "doctors/<int:pk>/",
        DoctorDetailAPIView.as_view(),
        name="api-doctor-detail"
    ),

    # Public availability
    path(
        "availability/",
        AvailabilityListAPIView.as_view(),
        name="api-availability"
    ),

    # Patient
    path(
        "patient/profile/",
        PatientProfileAPIView.as_view(),
        name="api-patient-profile"
    ),

    # Appointments
    path(
        "appointments/",
        AppointmentListCreateAPIView.as_view(),
        name="api-appointments"
    ),
    path(
        "appointments/<int:pk>/",
        AppointmentDetailAPIView.as_view(),
        name="api-appointment-detail"
    ),
    path(
        "appointments/<int:pk>/cancel/",
        AppointmentCancelAPIView.as_view(),
        name="api-appointment-cancel"
    ),

    # Administrator - Doctors
    path(
        "admin/doctors/",
        AdminDoctorListCreateAPIView.as_view(),
        name="api-admin-doctors"
    ),
    path(
        "admin/doctors/<int:pk>/",
        AdminDoctorDetailAPIView.as_view(),
        name="api-admin-doctor-detail"
    ),

    # Administrator - Availability
    path(
        "admin/availability/",
        AdminAvailabilityListCreateAPIView.as_view(),
        name="api-admin-availability"
    ),
    path(
        "admin/availability/<int:pk>/",
        AdminAvailabilityDetailAPIView.as_view(),
        name="api-admin-availability-detail"
    ),

    # Administrator - Patients
    path(
        "admin/patients/",
        AdminPatientListAPIView.as_view(),
        name="api-admin-patients"
    ),
    path(
        "admin/patients/<int:pk>/",
        AdminPatientDetailAPIView.as_view(),
        name="api-admin-patient-detail"
    ),

    # Administrator - Appointments
    path(
        "admin/appointments/",
        AdminAppointmentListAPIView.as_view(),
        name="api-admin-appointments"
    ),
    path(
        "admin/appointments/<int:pk>/status/",
        AdminAppointmentStatusAPIView.as_view(),
        name="api-admin-appointment-status"
    ),
]
