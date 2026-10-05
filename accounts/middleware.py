from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class SessionTimeoutMiddleware:
    """Logs an admin out after THEIR OWN configured number of inactive
    minutes (AdminUser.session_timeout_minutes) — not Django's global
    SESSION_COOKIE_AGE, which would be one fixed value for every admin.
    Every authenticated request refreshes 'last_activity' in the session;
    if too much time has passed since the last one, this ends the
    session and sends them back to login with an explanation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            last_activity_str = request.session.get("last_activity")
            if last_activity_str:
                last_activity = datetime.fromisoformat(last_activity_str)
                elapsed_minutes = (now - last_activity).total_seconds() / 60
                timeout_minutes = getattr(request.user, "session_timeout_minutes", 30)
                if elapsed_minutes > timeout_minutes:
                    logout(request)
                    messages.info(request, "You were logged out after a period of inactivity.")
                    return redirect(reverse("accounts:login"))
            request.session["last_activity"] = now.isoformat()
        return self.get_response(request)
