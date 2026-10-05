from .signals import set_current_user


class CurrentUserMiddleware:
    """Makes the logged-in admin visible to model signals for the
    duration of one request, so AuditLog entries know WHO made a change
    — signals alone have no access to the request/user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, "user", None))
        try:
            response = self.get_response(request)
        finally:
            set_current_user(None)
        return response
