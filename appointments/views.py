from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Doctor, Patient, Appointment, Availability

from .forms import (
    PatientRegistrationForm,
    DoctorRegistrationForm
)
from django.utils import timezone
from datetime import datetime
from django.contrib import messages


def home(request):
    return render(request, "appointments/home.html")


def register_patient(request):
    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            Patient.objects.create(
                user=user,
                phone=""
            )

            return redirect("login")

    else:
        form = PatientRegistrationForm()

    return render(
        request,
        "appointments/register_patient.html",
        {"form": form}
    )


def register_doctor(request):
    if request.method == "POST":
        form = DoctorRegistrationForm(request.POST)

        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"]
            )

            Doctor.objects.create(
                user=user,
                specialization=form.cleaned_data["specialization"],
                phone=form.cleaned_data["phone"],
                approved=False
            )

            return redirect("login")

    else:
        form = DoctorRegistrationForm()

    return render(
        request,
        "appointments/register_doctor.html",
        {"form": form}
    )


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            # Check if the user is a doctor
            try:
                doctor = Doctor.objects.get(user=user)

                if not doctor.approved:
                    return render(
                        request,
                        "appointments/login.html",
                        {
                            "error": "Your doctor account is waiting for admin approval."
                        }
                    )

            except Doctor.DoesNotExist:
                pass

            login(request, user)

            # Send admin to admin dashboard
            if user.is_staff:
                return redirect("admin_dashboard")

            # Send doctor to doctor dashboard
            if hasattr(user, "doctor"):
                return redirect("doctor_dashboard")

            # Send patient to patient dashboard
            if hasattr(user, "patient"):
                return redirect("patient_dashboard")

            return redirect("home")

        return render(
            request,
            "appointments/login.html",
            {"error": "Invalid username or password."}
        )

    return render(request, "appointments/login.html")


def logout_view(request):
    logout(request)
    return redirect("home")


def patient_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")

    return render(
        request,
        "appointments/patient_dashboard.html"
    )


def doctor_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")

    return render(
        request,
        "appointments/doctor_dashboard.html"
    )

@login_required
def doctors_list(request):
    doctors = Doctor.objects.filter(approved=True)

    return render(
        request,
        "appointments/doctor_list.html",
        {"doctors": doctors}
    )


@login_required
def book_appointment(request, doctor_id):

    if not hasattr(request.user, "patient"):
        return redirect("home")

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id,
        approved=True
    )

    patient = request.user.patient

    from datetime import datetime, timedelta

    selected_date = request.GET.get("date")
    available_slots = []


    # ROUND TIME UP TO THE NEXT :00 OR :30
    def round_time_up(time_value):

        total_minutes = (
            time_value.hour * 60
            + time_value.minute
        )

        rounded_minutes = (
            (total_minutes + 29) // 30
        ) * 30

        hours = rounded_minutes // 60
        minutes = rounded_minutes % 60

        if hours >= 24:
            return None

        return time_value.replace(
            hour=hours,
            minute=minutes,
            second=0,
            microsecond=0
        )

    # ROUND TIME DOWN TO THE PREVIOUS :00 OR :30
    def round_time_down(time_value):

        total_minutes = (
            time_value.hour * 60
            + time_value.minute
        )

        rounded_minutes = (
            total_minutes // 30
        ) * 30

        hours = rounded_minutes // 60
        minutes = rounded_minutes % 60

        if hours >= 24:
            return None

        return time_value.replace(
            hour=hours,
            minute=minutes,
            second=0,
            microsecond=0
        )

    # --------------------------------------------------
    # SHOW AVAILABLE SLOTS
    # --------------------------------------------------
    if selected_date:

        try:
            selected_date_obj = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            selected_date_obj = None

        if selected_date_obj:

            if selected_date_obj >= timezone.localdate():

                availabilities = Availability.objects.filter(
                    doctor=doctor,
                    date=selected_date_obj
                ).order_by("start_time")

                for availability in availabilities:

                    # Round start UP
                    current_time = round_time_up(
                        availability.start_time
                    )

                    # Round end DOWN
                    rounded_end_time = round_time_down(
                        availability.end_time
                    )

                    if (
                        current_time is None
                        or rounded_end_time is None
                    ):
                        continue

                    while current_time <= rounded_end_time:

                        # ------------------------------------------
                        # CHECK IF DOCTOR ALREADY HAS AN APPOINTMENT
                        # ------------------------------------------
                        doctor_already_booked = Appointment.objects.filter(
                            doctor=doctor,
                            appointment_date=selected_date_obj,
                            appointment_time=current_time,
                            status__in=["Pending", "Confirmed"]
                        ).exists()

                        # ------------------------------------------
                        # CHECK IF PATIENT ALREADY HAS AN APPOINTMENT
                        # AT THE SAME DATE AND TIME
                        # ------------------------------------------
                        patient_already_booked = Appointment.objects.filter(
                            patient=patient,
                            appointment_date=selected_date_obj,
                            appointment_time=current_time,
                            status__in=["Pending", "Confirmed"]
                        ).exists()

                        if (
                            not doctor_already_booked
                            and not patient_already_booked
                        ):
                            available_slots.append(current_time)

                        current_datetime = datetime.combine(
                            selected_date_obj,
                            current_time
                        )

                        current_datetime += timedelta(
                            minutes=30
                        )

                        current_time = current_datetime.time()

    # --------------------------------------------------
    # BOOK APPOINTMENT
    # --------------------------------------------------
    if request.method == "POST":

        appointment_date = request.POST.get(
            "appointment_date"
        )

        appointment_time = request.POST.get(
            "appointment_time"
        )

        reason = request.POST.get(
            "reason",
            ""
        )

        if not appointment_date or not appointment_time:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "Please select a date and appointment time."
                }
            )

        try:

            appointment_date_obj = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).date()

            appointment_time_obj = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time()

        except ValueError:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "error": "Invalid date or time."
                }
            )

        # --------------------------------------------------
        # PREVENT BOOKING IN THE PAST
        # --------------------------------------------------
        if appointment_date_obj < timezone.localdate():

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "You cannot book an appointment in the past."
                }
            )

        # --------------------------------------------------
        # MAKE SURE TIME IS :00 OR :30
        # --------------------------------------------------
        if appointment_time_obj.minute not in [0, 30]:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "Appointment times must be on the hour or half hour."
                }
            )

        # --------------------------------------------------
        # CHECK THAT THE TIME IS INSIDE DOCTOR AVAILABILITY
        # --------------------------------------------------
        valid_slot = False

        availabilities = Availability.objects.filter(
            doctor=doctor,
            date=appointment_date_obj
        )

        for availability in availabilities:

            rounded_start = round_time_up(
                availability.start_time
            )

            rounded_end = round_time_down(
                availability.end_time
            )

            if (
                rounded_start is None
                or rounded_end is None
            ):
                continue

            current_time = rounded_start

            while current_time <= rounded_end:

                if current_time == appointment_time_obj:

                    valid_slot = True
                    break

                current_datetime = datetime.combine(
                    appointment_date_obj,
                    current_time
                )

                current_datetime += timedelta(
                    minutes=30
                )

                current_time = current_datetime.time()

            if valid_slot:
                break

        if not valid_slot:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "That is not a valid appointment time."
                }
            )

        # --------------------------------------------------
        # PREVENT DOCTOR FROM BEING DOUBLE BOOKED BY 2 PATIENTS AT SAME TIME
        # --------------------------------------------------
        doctor_already_booked = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=["Pending", "Confirmed"]
        ).exists()

        if doctor_already_booked:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "That appointment time has already been booked."
                }
            )

        # --------------------------------------------------
        # PREVENT PATIENT DOUBLE BOOKING TWO BOOKINGS AT SAME TIME
        # WITH ANOTHER DOCTOR
        # --------------------------------------------------
        patient_already_booked = Appointment.objects.filter(
            patient=patient,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=["Pending", "Confirmed"]
        ).exists()

        if patient_already_booked:

            return render(
                request,
                "appointments/book_appointment.html",
                {
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "error": "You already have an appointment at this date and time."
                }
            )

        # --------------------------------------------------
        # CREATE APPOINTMENT
        # --------------------------------------------------
        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            reason=reason,
            status="Pending"
        )

        # --------------------------------------------------
        # SHOW SUCCESS NOTIFICATION (MESSAGE)
        # --------------------------------------------------
        return render(
            request,
            "appointments/patient_appointments.html",
            {
                "appointments": Appointment.objects.filter(
                    patient=patient
                ).select_related(
                    "doctor",
                    "doctor__user"
                ),
                "booking_success": (
                    "Booking was booked successfully, "
                    "please wait for approval from the doctor."
                )
            }
        )

    # --------------------------------------------------
    # DISPLAY BOOKING PAGE
    # --------------------------------------------------
    return render(
        request,
        "appointments/book_appointment.html",
        {
            "doctor": doctor,
            "selected_date": selected_date,
            "available_slots": available_slots
        }
    )


@login_required
def patient_appointments(request):
    if not hasattr(request.user, "patient"):
        return redirect("home")

    appointments = Appointment.objects.filter(
        patient=request.user.patient
    ).order_by(
        "appointment_date",
        "appointment_time"
    )

    return render(
        request,
        "appointments/patient_appointments.html",
        {"appointments": appointments}
    )

@login_required
def edit_appointment(request, appointment_id):
    if not hasattr(request.user, "patient"):
        return redirect("home")

    patient = request.user.patient

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=patient
    )

    # Don't allow editing completed or cancelled appointments
    if appointment.status in ["Completed", "Cancelled"]:
        return redirect("patient_appointments")

    doctor = appointment.doctor

    selected_date = request.GET.get(
        "date",
        appointment.appointment_date.strftime("%Y-%m-%d")
    )

    available_slots = []

    from datetime import datetime, timedelta

    try:
        selected_date_obj = datetime.strptime(
            selected_date,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        selected_date_obj = appointment.appointment_date

    # Don't allow past dates
    if selected_date_obj >= timezone.localdate():

        availabilities = Availability.objects.filter(
            doctor=doctor,
            date=selected_date_obj
        ).order_by("start_time")

        for availability in availabilities:

            current_time = availability.start_time

            while current_time < availability.end_time:

                # Don't count the current appointment as a booking
                already_booked = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=selected_date_obj,
                    appointment_time=current_time,
                    status__in=["Pending", "Confirmed"]
                ).exclude(
                    id=appointment.id
                ).exists()

                if not already_booked:
                    available_slots.append(current_time)

                current_datetime = datetime.combine(
                    selected_date_obj,
                    current_time
                )

                current_datetime += timedelta(minutes=30)

                current_time = current_datetime.time()

    if request.method == "POST":

        appointment_date = request.POST.get(
            "appointment_date"
        )

        appointment_time = request.POST.get(
            "appointment_time"
        )

        reason = request.POST.get(
            "reason",
            ""
        )

        if not appointment_date or not appointment_time:

            return render(
                request,
                "appointments/edit_appointment.html",
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "available_slots": available_slots,
                    "error": "Please select a date and time."
                }
            )

        try:

            appointment_date_obj = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).date()

            appointment_time_obj = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time()

        except ValueError:

            return render(
                request,
                "appointments/edit_appointment.html",
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "available_slots": available_slots,
                    "error": "Invalid date or time."
                }
            )

        # Prevent past dates
        if appointment_date_obj < timezone.localdate():

            return render(
                request,
                "appointments/edit_appointment.html",
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "available_slots": available_slots,
                    "error": "You cannot select a date in the past."
                }
            )

        # Check that the selected time is a valid 30-minute slot
        valid_slot = False

        availabilities = Availability.objects.filter(
            doctor=doctor,
            date=appointment_date_obj
        )

        for availability in availabilities:

            current_time = availability.start_time

            while current_time < availability.end_time:

                if current_time == appointment_time_obj:
                    valid_slot = True
                    break

                current_datetime = datetime.combine(
                    appointment_date_obj,
                    current_time
                )

                current_datetime += timedelta(minutes=30)

                current_time = current_datetime.time()

            if valid_slot:
                break

        if not valid_slot:

            return render(
                request,
                "appointments/edit_appointment.html",
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "available_slots": available_slots,
                    "error": "That is not a valid appointment time."
                }
            )

        # Prevent double booking
        already_booked = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=["Pending", "Confirmed"]
        ).exclude(
            id=appointment.id
        ).exists()

        if already_booked:

            return render(
                request,
                "appointments/edit_appointment.html",
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "selected_date": appointment_date,
                    "available_slots": available_slots,
                    "error": "That appointment time has already been booked."
                }
            )

        # Update appointment
        appointment.appointment_date = appointment_date_obj
        appointment.appointment_time = appointment_time_obj
        appointment.reason = reason

        # Editing sends it back to Pending
        appointment.status = "Pending"

        appointment.save()

        return redirect("patient_appointments")

    return render(
        request,
        "appointments/edit_appointment.html",
        {
            "appointment": appointment,
            "doctor": doctor,
            "selected_date": selected_date,
            "available_slots": available_slots
        }
    )

@login_required
def patient_cancel_appointment(request, appointment_id):
    if not hasattr(request.user, "patient"):
        return redirect("home")

    patient = request.user.patient

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=patient
    )

    if request.method == "POST":

        if appointment.status in ["Pending", "Confirmed"]:
            appointment.status = "Cancelled"
            appointment.save()

    return redirect("patient_appointments")

@login_required
def doctor_availability(request):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    availabilities = Availability.objects.filter(
        doctor=doctor
    ).order_by(
        "date",
        "start_time"
    )

    return render(
        request,
        "appointments/doctor_availability.html",
        {
            "availabilities": availabilities
        }
    )

@login_required
def add_availability(request):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    if request.method == "POST":
        date = request.POST["date"]
        start_time = request.POST["start_time"]
        end_time = request.POST["end_time"]

        Availability.objects.create(
            doctor=doctor,
            date=date,
            start_time=start_time,
            end_time=end_time
        )

        return redirect("doctor_availability")

    return render(
        request,
        "appointments/add_availability.html"
    )


@login_required
def delete_availability(request, availability_id):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    availability = get_object_or_404(
        Availability,
        id=availability_id,
        doctor=request.user.doctor
    )

    availability.delete()

    return redirect("doctor_availability")

@login_required
def doctor_appointments(request):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    appointments = Appointment.objects.filter(
        doctor=doctor
    ).select_related(
        "patient",
        "patient__user"
    ).order_by(
        "appointment_date",
        "appointment_time"
    )

    return render(
        request,
        "appointments/doctor_appointments.html",
        {
            "appointments": appointments
        }
    )


@login_required
def confirm_appointment(request, appointment_id):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor=doctor
    )

    if request.method == "POST":

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )

        current_datetime = timezone.localtime(
            timezone.now()
        ).replace(tzinfo=None)

        # Don't confirm an appointment that has already happened
        if appointment_datetime <= current_datetime:
            return redirect("doctor_appointments")

        # Only Pending appointments can be confirmed
        if appointment.status == "Pending":
            appointment.status = "Confirmed"
            appointment.save()

    return redirect("doctor_appointments")


@login_required
def cancel_appointment(request, appointment_id):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor=doctor
    )

    if request.method == "POST":

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )

        current_datetime = timezone.localtime(
            timezone.now()
        ).replace(tzinfo=None)

        # Don't cancel an appointment that has already happened
        if appointment_datetime <= current_datetime:
            return redirect("doctor_appointments")

        # Only Pending or Confirmed appointments can be cancelled
        if appointment.status in ["Pending", "Confirmed"]:
            appointment.status = "Cancelled"
            appointment.save()

    return redirect("doctor_appointments")

@login_required
def complete_appointment(request, appointment_id):
    if not hasattr(request.user, "doctor"):
        return redirect("home")

    doctor = request.user.doctor

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor=doctor
    )

    if request.method == "POST":

        appointment_datetime = datetime.combine(
            appointment.appointment_date,
            appointment.appointment_time
        )

        # Current Auckland time
        current_datetime = timezone.localtime(
            timezone.now()
        ).replace(tzinfo=None)

        # Appointment must have already happened
        if appointment_datetime <= current_datetime:

            if appointment.status == "Confirmed":
                appointment.status = "Completed"
                appointment.save()

    return redirect("doctor_appointments")

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect("home")

    doctors = Doctor.objects.select_related(
        "user"
    ).order_by(
        "approved",
        "user__last_name"
    )

    patients = Patient.objects.select_related(
        "user"
    ).order_by(
        "user__last_name"
    )

    appointments = Appointment.objects.select_related(
        "patient__user",
        "doctor__user"
    ).order_by(
        "-appointment_date",
        "-appointment_time"
    )

    return render(
        request,
        "appointments/admin_dashboard.html",
        {
            "doctors": doctors,
            "patients": patients,
            "appointments": appointments,
        }
    )


@login_required
def approve_doctor(request, doctor_id):
    if not request.user.is_staff:
        return redirect("home")

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    if request.method == "POST":
        doctor.approved = True
        doctor.save()

    return redirect("admin_dashboard")


@login_required
def reject_doctor(request, doctor_id):
    if not request.user.is_staff:
        return redirect("home")

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    if request.method == "POST":
        doctor.user.delete()

    return redirect("admin_dashboard")

@login_required
def admin_edit_doctor(request, doctor_id):
    if not request.user.is_staff:
        return redirect("home")

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    user = doctor.user

    if request.method == "POST":

        user.first_name = request.POST.get(
            "first_name"
        )

        user.last_name = request.POST.get(
            "last_name"
        )

        user.email = request.POST.get(
            "email"
        )

        doctor.specialization = request.POST.get(
            "specialization"
        )

        doctor.phone = request.POST.get(
            "phone"
        )

        doctor.approved = (
            request.POST.get("approved") == "on"
        )

        user.save()
        doctor.save()

        return redirect("admin_dashboard")

    return render(
        request,
        "appointments/admin_edit_doctor.html",
        {
            "doctor": doctor
        }
    )


@login_required
def admin_delete_doctor(request, doctor_id):
    if not request.user.is_staff:
        return redirect("home")

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id
    )

    if request.method == "POST":
        doctor.user.delete()

    return redirect("admin_dashboard")

@login_required
def admin_edit_patient(request, patient_id):
    if not request.user.is_staff:
        return redirect("home")

    patient = get_object_or_404(
        Patient,
        id=patient_id
    )

    user = patient.user

    if request.method == "POST":

        user.first_name = request.POST.get(
            "first_name",
            ""
        )

        user.last_name = request.POST.get(
            "last_name",
            ""
        )

        user.email = request.POST.get(
            "email",
            ""
        )

        patient.phone = request.POST.get(
            "phone",
            ""
        )

        date_of_birth = request.POST.get(
            "date_of_birth"
        )

        if date_of_birth:
            patient.date_of_birth = date_of_birth
        else:
            patient.date_of_birth = None

        user.save()
        patient.save()

        return redirect("admin_dashboard")

    return render(
        request,
        "appointments/admin_edit_patient.html",
        {
            "patient": patient
        }
    )


@login_required
def admin_delete_patient(request, patient_id):
    if not request.user.is_staff:
        return redirect("home")

    patient = get_object_or_404(
        Patient,
        id=patient_id
    )

    if request.method == "POST":
        patient.user.delete()

    return redirect("admin_dashboard")

@login_required
def admin_edit_appointment(request, appointment_id):
    if not request.user.is_staff:
        return redirect("home")

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id
    )

    patients = Patient.objects.select_related(
        "user"
    ).order_by(
        "user__last_name"
    )

    doctors = Doctor.objects.filter(
        approved=True
    ).select_related(
        "user"
    ).order_by(
        "user__last_name"
    )

    if request.method == "POST":

        patient_id = request.POST.get("patient")
        doctor_id = request.POST.get("doctor")
        appointment_date = request.POST.get("appointment_date")
        appointment_time = request.POST.get("appointment_time")
        reason = request.POST.get("reason", "")
        status = request.POST.get("status")

        if not all([
            patient_id,
            doctor_id,
            appointment_date,
            appointment_time,
            status
        ]):
            return render(
                request,
                "appointments/admin_edit_appointment.html",
                {
                    "appointment": appointment,
                    "patients": patients,
                    "doctors": doctors,
                    "error": "Please fill in all required fields."
                }
            )

        try:
            appointment_date_obj = datetime.strptime(
                appointment_date,
                "%Y-%m-%d"
            ).date()

            appointment_time_obj = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time()

        except ValueError:
            return render(
                request,
                "appointments/admin_edit_appointment.html",
                {
                    "appointment": appointment,
                    "patients": patients,
                    "doctors": doctors,
                    "error": "Invalid date or time."
                }
            )

        patient = get_object_or_404(
            Patient,
            id=patient_id
        )

        doctor = get_object_or_404(
            Doctor,
            id=doctor_id,
            approved=True
        )

        # Prevent another appointment from using
        # the same doctor, date and time.
        doctor_conflict = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=["Pending", "Confirmed"]
        ).exclude(
            id=appointment.id
        ).exists()

        if doctor_conflict:
            return render(
                request,
                "appointments/admin_edit_appointment.html",
                {
                    "appointment": appointment,
                    "patients": patients,
                    "doctors": doctors,
                    "error": "That doctor already has an appointment at this date and time."
                }
            )

        # Prevent the same patient from having
        # two appointments at the same date and time.
        patient_conflict = Appointment.objects.filter(
            patient=patient,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=["Pending", "Confirmed"]
        ).exclude(
            id=appointment.id
        ).exists()

        if patient_conflict:
            return render(
                request,
                "appointments/admin_edit_appointment.html",
                {
                    "appointment": appointment,
                    "patients": patients,
                    "doctors": doctors,
                    "error": "That patient already has an appointment at this date and time."
                }
            )

        appointment.patient = patient
        appointment.doctor = doctor
        appointment.appointment_date = appointment_date_obj
        appointment.appointment_time = appointment_time_obj
        appointment.reason = reason
        appointment.status = status

        appointment.save()

        return redirect("admin_dashboard")

    return render(
        request,
        "appointments/admin_edit_appointment.html",
        {
            "appointment": appointment,
            "patients": patients,
            "doctors": doctors
        }
    )


@login_required
def admin_delete_appointment(request, appointment_id):
    if not request.user.is_staff:
        return redirect("home")

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id
    )

    if request.method == "POST":
        appointment.delete()

    return redirect("admin_dashboard")