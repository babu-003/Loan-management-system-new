from .models import get_setting


def system_settings(request):
    """Makes company_name available in every template (e.g. the top bar)
    without every view having to fetch it manually."""
    return {"company_name": get_setting("company_name")}
