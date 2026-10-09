from django import forms

from .models import (
    LedgerAccount,
    Voucher,
    VoucherCategory,
)


class VoucherForm(forms.Form):

    STANDARD_TYPES = [
        (Voucher.TYPE_EXPENSE, "Expense"),
        (Voucher.TYPE_INVESTMENT, "Investment"),
        (Voucher.TYPE_INCOME, "Income"),
    ]

    voucher_type = forms.ChoiceField(
        choices=STANDARD_TYPES
    )

    voucher_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "min": "1900-01-01",
                "max": "9999-12-31",
            }
        )
    )

    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0.01
    )

    payment_mode = forms.ChoiceField(
        choices=Voucher.MODE_CHOICES
    )

    transaction_id = forms.CharField(
        max_length=100,
        required=False
    )

    category = forms.ModelChoiceField(
        queryset=VoucherCategory.objects.none(),
        required=True
    )

    narration = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 3}
        ),
        required=False
    )

    def __init__(
        self,
        *args,
        **kwargs
    ):

        super().__init__(
            *args,
            **kwargs
        )

        voucher_type = (
            self.data.get("voucher_type")
            or self.initial.get("voucher_type")
            or Voucher.TYPE_EXPENSE
        )

        self.fields["category"].queryset = (
            VoucherCategory.objects
            .filter(
                is_active=True,
                voucher_type=voucher_type
            )
            .select_related("ledger_account")
        )

    def clean(self):

        cleaned = super().clean()

        voucher_type = cleaned.get(
            "voucher_type"
        )

        category = cleaned.get(
            "category"
        )

        if category and category.voucher_type != voucher_type:

            self.add_error(
                "category",
                "Category does not belong to the selected voucher type."
            )

        mode = cleaned.get(
            "payment_mode"
        )

        transaction_id = cleaned.get(
            "transaction_id",
            ""
        ).strip()

        if mode in {
            Voucher.MODE_ONLINE,
            Voucher.MODE_UPI,
            Voucher.MODE_CHEQUE,
        }:

            if not transaction_id:

                self.add_error(
                    "transaction_id",
                    "Transaction ID / reference is required for Online, UPI or Cheque payments."
                )

        if mode == Voucher.MODE_CASH:

            cleaned["transaction_id"] = ""

        return cleaned


class VoucherCategoryForm(forms.ModelForm):

    class Meta:

        model = VoucherCategory

        fields = [
            "name",
            "voucher_type",
            "is_active",
        ]


class LedgerAccountForm(forms.ModelForm):

    class Meta:

        model = LedgerAccount

        fields = [
            "name",
            "account_type",
            "is_active",
        ]