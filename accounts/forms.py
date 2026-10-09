from django import forms
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError

from .models import AdminUser, MasterRecovery


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = AdminUser
        fields = ["full_name", "email", "session_timeout_minutes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = True
        self.fields["email"].required = True


class RecoveryCodeForm(forms.ModelForm):
    recovery_code = forms.CharField(
        label="Recovery Code",
        required=False,
        min_length=6,
        max_length=64,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Set a private code that you can use if you forget your login credentials.",
    )

    class Meta:
        model = AdminUser
        fields = []

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_recovery_code(self):
        code = self.cleaned_data.get("recovery_code", "").strip()
        if code:
            if len(code) < 6:
                raise ValidationError("Recovery code must contain at least 6 characters.")
            self.instance.recovery_code_hash = make_password(code)
        return code


class AccountRecoveryForm(forms.Form):
    current_username = forms.CharField(
        label="Current Username (optional)",
        required=False,
        max_length=150,
        help_text="Leave blank if you also forgot the username.",
    )
    recovery_code = forms.CharField(
        label="Recovery Code",
        max_length=64,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
    )
    new_username = forms.CharField(label="New Username", max_length=150)
    new_password = forms.CharField(
        label="New Password",
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")

        username = (cleaned.get("new_username") or "").strip()
        current_username = (cleaned.get("current_username") or "").strip()
        if username and (not current_username or username.lower() != current_username.lower()):
            existing = AdminUser.objects.filter(username__iexact=username).first()
            if existing:
                self.add_error("new_username", "That username is already in use.")
        return cleaned

    def find_user(self):
        """Return the account whose personal recovery code matches."""
        code = self.cleaned_data["recovery_code"]
        supplied_username = (self.cleaned_data.get("current_username") or "").strip()

        if supplied_username:
            candidates = AdminUser.objects.filter(username__iexact=supplied_username)
        else:
            candidates = AdminUser.objects.filter(is_active=True)

        for user in candidates:
            if user.recovery_code_hash and check_password(code, user.recovery_code_hash):
                return user
        return None


class MasterAccountRecoveryForm(AccountRecoveryForm):
    recovery_code = forms.CharField(
        label="Master Recovery Code",
        max_length=64,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
        help_text="Enter the master code supplied separately by the application owner/developer.",
    )

    def find_user(self):
        master = MasterRecovery.objects.first()
        if not master or not master.code_hash or not master.check_code(self.cleaned_data["recovery_code"]):
            return None

        supplied_username = (self.cleaned_data.get("current_username") or "").strip()
        if supplied_username:
            return AdminUser.objects.filter(username__iexact=supplied_username, is_active=True).first()

        # With one active admin, the master code alone is enough even when
        # the username has also been forgotten. If multiple admins exist,
        # require the username so the master code cannot choose an account.
        active_users = AdminUser.objects.filter(is_active=True)
        if active_users.count() == 1:
            return active_users.first()
        return None
