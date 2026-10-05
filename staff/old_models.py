from django.core.validators import RegexValidator
from django.db import models


mobile_validator = RegexValidator(
    regex=r"^[6-9]\d{9}$",
    message="Enter a valid 10-digit mobile number.",
)


class Staff(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    employee_id = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=10, validators=[mobile_validator])
    email = models.EmailField(blank=True)
    joining_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.employee_id} — {self.full_name}"

    @property
    def total_assigned_loans(self):
        return self.loans.count()

    @property
    def active_loan_count(self):
        return self.loans.filter(status="active").count()

    @property
    def completed_loan_count(self):
        return self.loans.filter(status="completed").count()

    @property
    def closed_loan_count(self):
        return self.loans.filter(status="closed").count()

    @property
    def total_collected(self):
        from django.db.models import Sum
        return self.loans.aggregate(total=Sum("payments__amount_paid"))["total"] or 0

    @property
    def total_outstanding(self):
        from decimal import Decimal
        return sum((loan.total_outstanding for loan in self.loans.all()), Decimal("0"))
