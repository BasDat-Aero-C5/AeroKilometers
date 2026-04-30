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

def tier_info(request):
    current_miles = 45000
    current_tier = "Gold"

    tiers = [
        {
            "name": "Blue",
            "min_flight": 0,
            "min_miles": 0,
            "benefits": ["Akumulasi miles dasar", "Akses penawaran member"]
        },
        {
            "name": "Silver",
            "min_flight": 10,
            "min_miles": 15000,
            "benefits": ["Bonus miles 25%", "Priority check-in"]
        },
        {
            "name": "Gold",
            "min_flight": 25,
            "min_miles": 40000,
            "benefits": ["Bonus miles 50%", "Priority boarding", "Akses lounge"]
        },
        {
            "name": "Platinum",
            "min_flight": 50,
            "min_miles": 80000,
            "benefits": ["Bonus miles 100%", "Upgrade gratis", "Dedicated hotline"]
        },
    ]

    # cari next tier
    next_tier = None
    for t in tiers:
        if current_miles < t["min_miles"]:
            next_tier = t
            break

    return render(request, "hadiah/tier.html", {
        "tiers": tiers,
        "current_tier": current_tier,
        "current_miles": current_miles,
        "next_tier": next_tier
    })

def report_view(request):
    tab = request.GET.get("tab", "riwayat")

    transactions = [
        {"type": "Transfer", "user": "John W. Doe", "email": "john@example.com", "miles": -5000, "date": "2025-01-15 10:30"},
        {"type": "Redeem", "user": "John W. Doe", "email": "john@example.com", "miles": -3000, "date": "2025-01-20 16:00"},
        {"type": "Package", "user": "Jane Smith", "email": "jane@example.com", "miles": 5000, "date": "2025-02-01 09:15"},
        {"type": "Klaim", "user": "Budi A.", "email": "budi@example.com", "miles": 2500, "date": "2025-02-05 11:45"},
    ]

    top_members = [
        {"name": "John W. Doe", "total": 45000},
        {"name": "Jane Smith", "total": 40000},
    ]

    summary = {
        "total_miles": 27500,
        "redeem": 3000,
        "klaim": 2500
    }

    return render(request, "transfer/report.html", {
        "transactions": transactions,
        "summary": summary,
        "tab": tab,
        "top_members": top_members
    })
