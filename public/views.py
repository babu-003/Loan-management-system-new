from django.contrib import messages
from django.shortcuts import redirect, render


def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


'''
def contact(request):
    if request.method == "POST":
        # Wire this up to however you want enquiries handled —
        # e.g. save a ContactEnquiry model, or email the branch.
        messages.success(request, "Thanks — we'll be in touch within one business day.")
        return redirect("public:contact")
    return render(request, "contact.html")
'''
from django.core.mail import send_mail
from django.conf import settings

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        mobile = request.POST.get("mobile")
        email = request.POST.get("email")
        loan_type = request.POST.get("loan_type")
        message = request.POST.get("message")

        subject = f"New Contact Enquiry - {loan_type}"

        body = f"""
New enquiry received

Name: {name}
Mobile: {mobile}
Email: {email}
Loan Type: {loan_type}

Message:
{message}
"""

        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,      # From
            ["babubala2004@gmail.com"],        # Your receiving email
            fail_silently=False,
        )

        messages.success(request, "Thanks! Your message has been sent.")
        return redirect("public:contact")

    return render(request, "contact.html")