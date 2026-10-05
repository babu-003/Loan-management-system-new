from django import forms

from .models import AdminUser


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = AdminUser
        fields = ["full_name", "email", "session_timeout_minutes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = True
        self.fields["email"].required = True
