
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Appointment, Availability


# ==========================================
# SCHEDULING CONFIGURATION
# ==========================================

OPENING_TIME = time(9, 0)
CLOSING_TIME = time(17, 0)

SLOT_MINUTES = 30
BOOKING_DAYS_AHEAD = 30

ACTIVE_STATUSES = ["Pending", "Confirmed"]


# ==========================================
# VALIDATE WORKING HOURS
# ==========================================

def is_valid_slot(appointment_date, appointment_time):

    """
    Validate the clinic's default working schedule.
    """

    today = timezone.localdate()

    # Prevent bookings in the past.
    if appointment_date < today:
        return False

    # Limit bookings to the next 30 days.
    if appointment_date > today + timedelta(
        days=BOOKING_DAYS_AHEAD
    ):
        return False

    # Monday to Friday only.
    if appointment_date.weekday() >= 5:
        return False

    # Validate 30-minute intervals.
    if (
        appointment_time.second != 0
        or appointment_time.microsecond != 0
        or appointment_time.minute not in (0, 30)
    ):
        return False

    start = datetime.combine(
        appointment_date,
        appointment_time
    )

    end = start + timedelta(
        minutes=SLOT_MINUTES
    )

    opening = datetime.combine(
        appointment_date,
        OPENING_TIME
    )

    closing = datetime.combine(
        appointment_date,
        CLOSING_TIME
    )

    return (
        start >= opening
        and end <= closing
    )


# ==========================================
# VALIDATE FUTURE APPOINTMENTS
# ==========================================

def is_future_slot(appointment_date, appointment_time):

    """
    Prevent bookings for appointment times
    that have already passed.
    """

    naive_start = datetime.combine(
        appointment_date,
        appointment_time
    )

    start = timezone.make_aware(
        naive_start,
        timezone.get_current_timezone()
    )

    return start > timezone.now()


# ==========================================
# VALIDATE DOCTOR AVAILABILITY
# ==========================================

def is_doctor_available(
    doctor,
    appointment_date,
    appointment_time
):

    """
    Check whether an appointment fits entirely
    within an administrator-created availability.
    """

    if not doctor.approved:
        return False

    if not doctor.user.is_active:
        return False

    if not is_valid_slot(
        appointment_date,
        appointment_time
    ):
        return False

    start = datetime.combine(
        appointment_date,
        appointment_time
    )

    end = start + timedelta(
        minutes=SLOT_MINUTES
    )

    return Availability.objects.filter(
        doctor=doctor,
        date=appointment_date,
        start_time__lte=appointment_time,
        end_time__gte=end.time()
    ).exists()


# ==========================================
# GENERATE AVAILABLE APPOINTMENT SLOTS
# ==========================================

def get_available_slots(doctor, appointment_date):

    """
    Return available 30-minute appointment slots
    based on administrator-managed availability.
    """

    if not doctor.approved:
        return []

    if not doctor.user.is_active:
        return []

    today = timezone.localdate()

    if appointment_date < today:
        return []

    if appointment_date > today + timedelta(
        days=BOOKING_DAYS_AHEAD
    ):
        return []

    if appointment_date.weekday() >= 5:
        return []

    # Retrieve availability created by the administrator.
    availabilities = Availability.objects.filter(
        doctor=doctor,
        date=appointment_date
    ).order_by("start_time")

    # No availability means no appointment slots.
    if not availabilities.exists():
        return []

    # Retrieve existing active appointment bookings.
    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            status__in=ACTIVE_STATUSES
        ).values_list(
            "appointment_time",
            flat=True
        )
    )

    slots = set()

    # Generate appointment slots for each
    # administrator-created availability period.
    for availability in availabilities:

        current = datetime.combine(
            appointment_date,
            max(
                availability.start_time,
                OPENING_TIME
            )
        )

        closing = datetime.combine(
            appointment_date,
            min(
                availability.end_time,
                CLOSING_TIME
            )
        )

        # Align legacy availability records
        # to the next valid 30-minute interval.
        aligned = current.replace(
            minute=(current.minute // SLOT_MINUTES)
            * SLOT_MINUTES,
            second=0,
            microsecond=0
        )

        if aligned < current:
            aligned += timedelta(
                minutes=SLOT_MINUTES
            )

        current = aligned

        while current + timedelta(
            minutes=SLOT_MINUTES
        ) <= closing:

            slot_time = current.time()

            if (
                is_valid_slot(
                    appointment_date,
                    slot_time
                )
                and is_future_slot(
                    appointment_date,
                    slot_time
                )
                and slot_time not in booked_times
            ):

                slots.add(
                    slot_time.strftime("%H:%M")
                )

            current += timedelta(
                minutes=SLOT_MINUTES
            )

    # Remove duplicates and return chronological times.
    return sorted(slots)
