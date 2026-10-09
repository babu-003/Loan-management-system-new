from django.urls import path

from . import views


app_name = "accounting"


urlpatterns = [

    path(
        "",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "vouchers/",
        views.voucher_list,
        name="voucher_list"
    ),

    path(
        "vouchers/add/",
        views.voucher_add,
        name="voucher_add"
    ),

    path(
        "vouchers/<int:pk>/",
        views.voucher_detail,
        name="voucher_detail"
    ),

    path(
        "ledgers/",
        views.ledger_list,
        name="ledger_list"
    ),

    path(
        "ledgers/<int:pk>/",
        views.ledger_detail,
        name="ledger_detail"
    ),

    path(
        "categories/",
        views.category_list,
        name="categories"
    ),
    
    path(
    "vouchers/<int:pk>/download/",
    views.download_voucher,
    name="download_voucher",
),
]