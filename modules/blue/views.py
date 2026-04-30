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
