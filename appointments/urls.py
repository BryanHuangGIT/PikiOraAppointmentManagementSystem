from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "register/patient/",
        views.register_patient,
        name="register_patient"
    ),

    path(
        "register/doctor/",
        views.register_doctor,
        name="register_doctor"
    ),

    path(
        "login/",
        views.login_view,
        name="login"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    path(
        "patient/dashboard/",
        views.patient_dashboard,
        name="patient_dashboard"
    ),

    path(
        "doctor/dashboard/",
        views.doctor_dashboard,
        name="doctor_dashboard"
    ),
    path(
        "doctors/",
        views.doctors_list,
        name="doctors_list"
    ),

    path(
        "book/<int:doctor_id>/",
        views.book_appointment,
        name="book_appointment"
    ),
    path(
        "patient/appointments/<int:appointment_id>/edit/",
        views.edit_appointment,
        name="edit_appointment"
    ),

    path(
        "patient/appointments/<int:appointment_id>/cancel/",
        views.patient_cancel_appointment,
        name="patient_cancel_appointment"
    ),

    path(
        "my-appointments/",
        views.patient_appointments,
        name="patient_appointments"
    ),

    path(
        "doctor/availability/",
        views.doctor_availability,
        name="doctor_availability"
    ),

    path(
        "doctor/availability/add/",
        views.add_availability,
        name="add_availability"
    ),

    path(
        "doctor/availability/delete/<int:availability_id>/",
        views.delete_availability,
        name="delete_availability"
    ),
    path(
        "doctor/appointments/",
        views.doctor_appointments,
        name="doctor_appointments"
    ),

    path(
        "doctor/appointments/<int:appointment_id>/confirm/",
        views.confirm_appointment,
        name="confirm_appointment"
    ),

    path(
        "doctor/appointments/<int:appointment_id>/cancel/",
        views.cancel_appointment,
        name="cancel_appointment"
    ),
    path(
    "doctor/appointments/<int:appointment_id>/complete/",
    views.complete_appointment,
    name="complete_appointment"
    ),
    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),

    path(
        "admin-dashboard/doctor/<int:doctor_id>/approve/",
        views.approve_doctor,
        name="approve_doctor"
    ),

    path(
        "admin-dashboard/doctor/<int:doctor_id>/reject/",
        views.reject_doctor,
        name="reject_doctor"
    ),

    path(
        "admin-dashboard/doctor/<int:doctor_id>/edit/",
        views.admin_edit_doctor,
        name="admin_edit_doctor"
    ),

    path(
        "admin-dashboard/doctor/<int:doctor_id>/delete/",
        views.admin_delete_doctor,
        name="admin_delete_doctor"
    ),
    path(
        "admin-dashboard/patient/<int:patient_id>/edit/",
        views.admin_edit_patient,
        name="admin_edit_patient"
    ),

    path(
        "admin-dashboard/patient/<int:patient_id>/delete/",
        views.admin_delete_patient,
        name="admin_delete_patient"
    ),
path(
    "admin-dashboard/appointment/<int:appointment_id>/edit/",
    views.admin_edit_appointment,
    name="admin_edit_appointment"
),

path(
    "admin-dashboard/appointment/<int:appointment_id>/delete/",
    views.admin_delete_appointment,
    name="admin_delete_appointment"
),
]