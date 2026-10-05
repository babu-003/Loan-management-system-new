from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import AdminProfileForm


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
    return render(request, "accounts/profile.html", {"form": form})
