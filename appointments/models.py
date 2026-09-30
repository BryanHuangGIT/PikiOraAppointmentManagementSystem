from django.db import models
from django.contrib.auth.models import User


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

class Availability(models.Model):
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="availabilities"
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return (
            f"Dr. {self.doctor.user.first_name} "
            f"{self.doctor.user.last_name} - "
            f"{self.date} "
            f"{self.start_time} - {self.end_time}"
        )

class Appointment(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Cancelled", "Cancelled"),
        ("Completed", "Completed"),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    appointment_date = models.DateField()
    appointment_time = models.TimeField()

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.patient} - Dr. {self.doctor} "
            f"- {self.appointment_date} {self.appointment_time}"
        )