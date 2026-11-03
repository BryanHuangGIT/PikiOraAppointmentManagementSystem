from django.urls import path

# Authentication views
from .auth_views import (
    PatientRegistrationAPIView,
    LoginAPIView,
    CurrentUserAPIView,
    LogoutAPIView,
)

# Application API views
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
    AdminAppointmentStatusAPIView,
)


urlpatterns = [

    # ==========================================
    # AUTHENTICATION
    # ==========================================

    path(
        "auth/register/",
        PatientRegistrationAPIView.as_view(),
        name="api-register"
    ),

    path(
        "auth/login/",
        LoginAPIView.as_view(),
        name="api-login"
    ),

    path(
        "auth/me/",
        CurrentUserAPIView.as_view(),
        name="api-current-user"
    ),

    path(
        "auth/logout/",
        LogoutAPIView.as_view(),
        name="api-logout"
    ),
    # ==========================================
    # DOCTORS
    # ==========================================

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

    # ==========================================
    # AVAILABILITY
    # ==========================================

    path(
        "availability/",
        AvailabilityListAPIView.as_view(),
        name="api-availability"
    ),

    # ==========================================
    # PATIENT PROFILE
    # ==========================================

    path(
        "patient/profile/",
        PatientProfileAPIView.as_view(),
        name="api-patient-profile"
    ),

    # ==========================================
    # APPOINTMENTS
    # ==========================================

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

    # ==========================================
    # ADMIN - DOCTORS
    # ==========================================

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

    # ==========================================
    # ADMIN - AVAILABILITY
    # ==========================================

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

    # ==========================================
    # ADMIN - PATIENTS
    # ==========================================

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

    # ==========================================
    # ADMIN - APPOINTMENTS
    # ==========================================

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
