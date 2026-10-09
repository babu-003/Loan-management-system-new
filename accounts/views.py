from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import AdminUser, MasterRecovery
from django.shortcuts import redirect, render

from .forms import (
    AccountRecoveryForm,
    AdminProfileForm,
    MasterAccountRecoveryForm,
    RecoveryCodeForm,
)


@login_required
def profile(request):
    if request.method == "POST":
        form = AdminProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = AdminProfileForm(instance=request.user)

    recovery_form = RecoveryCodeForm(instance=request.user)
    return render(
        request,
        "accounts/profile.html",
        {"form": form, "recovery_form": recovery_form},
    )


@login_required
def set_recovery_code(request):
    if request.method != "POST":
        return redirect("accounts:profile")

    form = RecoveryCodeForm(request.POST, instance=request.user, user=request.user)
    if form.is_valid():
        code = form.cleaned_data.get("recovery_code", "")
        if code:
            form.save()
            messages.success(request, "Recovery code updated successfully.")
        else:
            messages.error(request, "Please enter a recovery code.")
    else:
        for error in form.errors.values():
            messages.error(request, error.as_text().replace("* ", "").strip())
    return redirect("accounts:profile")


def recover_account(request):
    if request.method == "POST":
        form = AccountRecoveryForm(request.POST)
        if form.is_valid():
            user = form.find_user()
            if user is None:
                form.add_error("recovery_code", "Invalid recovery details.")
            else:
                user.username = form.cleaned_data["new_username"].strip()
                user.set_password(form.cleaned_data["new_password"])
                user.save(update_fields=["username", "password"])
                # Do not automatically log the user in after credential recovery.
                messages.success(request, "Username and password changed. Please log in with your new credentials.")
                return redirect("accounts:login")
    else:
        form = AccountRecoveryForm()

    return render(request, "accounts/recover_account.html", {"form": form})


def recover_account_master(request):
    if request.method == "POST":
        form = MasterAccountRecoveryForm(request.POST)
        if form.is_valid():
            user = form.find_user()
            if user is None:
                if not MasterRecovery.objects.exists():
                    form.add_error("recovery_code", "Master recovery has not been configured yet.")
                elif AdminUser.objects.filter(is_active=True).count() > 1 and not (form.cleaned_data.get("current_username") or "").strip():
                    form.add_error("current_username", "Enter the current username because multiple active admin accounts exist.")
                else:
                    form.add_error("recovery_code", "Invalid master recovery details.")
            else:
                user.username = form.cleaned_data["new_username"].strip()
                user.set_password(form.cleaned_data["new_password"])
                user.save(update_fields=["username", "password"])
                messages.success(request, "Username and password changed. Please log in with your new credentials.")
                return redirect("accounts:login")
    else:
        form = MasterAccountRecoveryForm()

    return render(request, "accounts/master_recovery.html", {"form": form})
