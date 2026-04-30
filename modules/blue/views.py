from django.shortcuts import render

def redeem_hadiah(request):
    tab = request.GET.get("tab", "katalog")

    rewards = [
        {
            "code": "RWD-005",
            "partner": "Garuda Indonesia",
            "name": "Upgrade Business Class",
            "miles": 15000,
            "desc": "Upgrade dari economy ke business class",
            "period": "2026-01-01 - 2027-01-01",
        },
        {
            "code": "RWD-010",
            "partner": "Traveloka",
            "name": "Voucher Hotel",
            "miles": 8000,
            "desc": "Voucher hotel bintang 5",
            "period": "2026-01-01 - 2026-12-31",
        },
    ]

    history = [
        {
            "name": "Akses Lounge 1x",
            "date": "2025-01-20 16:00",
            "miles": -3000
        }
    ]

    return render(request, "hadiah/redeem_hadiah.html", {
        "tab": tab,
        "rewards": rewards,
        "history": history,
        "user_miles": 32000
    })

def package_list(request):
    packages = [
        {"code": "AMP-001", "miles": 1000, "price": 150000},
        {"code": "AMP-002", "miles": 5000, "price": 650000},
        {"code": "AMP-003", "miles": 10000, "price": 1200000},
        {"code": "AMP-004", "miles": 25000, "price": 2750000},
    ]

    return render(request, "hadiah/package_list.html", {
        "packages": packages,
        "user_miles": 32000
    })
