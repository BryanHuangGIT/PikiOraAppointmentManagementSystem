from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Appointment


OPENING_TIME = time(9, 0)
CLOSING_TIME = time(17, 0)

SLOT_MINUTES = 30
BOOKING_DAYS_AHEAD = 30

ACTIVE_STATUSES = ["Pending", "Confirmed"]


def is_valid_slot(appointment_date, appointment_time):
    """Check the default working schedule."""

    today = timezone.localdate()

    if appointment_date < today:
        return False

    if appointment_date > today + timedelta(
        days=BOOKING_DAYS_AHEAD
    ):
        return False

    # Monday = 0, Sunday = 6
    if appointment_date.weekday() >= 5:
        return False

    if (
        appointment_time.second != 0
        or appointment_time.microsecond != 0
        or appointment_time.minute not in (0, 30)
    ):
        return False

    start = datetime.combine(
        appointment_date, appointment_time
    )

    end = start + timedelta(minutes=SLOT_MINUTES)

    return (
        appointment_time >= OPENING_TIME
        and end.time() <= CLOSING_TIME
    )


def is_future_slot(appointment_date, appointment_time):
    """Use the Django project's local timezone."""

    naive_start = datetime.combine(
        appointment_date, appointment_time
    )

    start = timezone.make_aware(
        naive_start,
        timezone.get_current_timezone()
    )

    return start > timezone.now()


def get_available_slots(doctor, appointment_date):
    """Return unbooked 30-minute start times."""

    if not doctor.approved:
        return []

    if appointment_date.weekday() >= 5:
        return []

    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            status__in=ACTIVE_STATUSES
        ).values_list(
            "appointment_time", flat=True
        )
    )

    slots = []

    current = datetime.combine(
        appointment_date, OPENING_TIME
    )

    closing = datetime.combine(
        appointment_date, CLOSING_TIME
    )

    while current + timedelta(
        minutes=SLOT_MINUTES
    ) <= closing:

        slot_time = current.time()

        if (
            is_valid_slot(appointment_date, slot_time)
            and is_future_slot(
                appointment_date, slot_time
            )
            and slot_time not in booked_times
        ):
            slots.append(
                slot_time.strftime("%H:%M")
            )

        current += timedelta(
            minutes=SLOT_MINUTES
        )

    return slots
