from django.shortcuts import render

# Create your views here.
def homepage(request):
    return render(request, 'homepage.html')

def login(request):
    return render(request, 'login.html')

def register(request):
    # test
    return render(request, 'register.html')

def dashboard_member(request):
    user_data = {
        "name": "Mr. John William Doe",
        "email": "john@example.com",
        "phone": "+62 81234567890",
        "nationality": "Indonesia",
        "birthdate": "1990-05-15",
        "joined": "2024-01-15"
    }

    member_data = {
        "member_id": "M0001",
        "tier": "Gold",
        "total_miles": 45000,
        "award_miles": 32000,
        "transactions": [
            {"type": "Transfer", "date": "2025-01-15", "miles": "-5000"},
            {"type": "Redeem", "date": "2025-01-20", "miles": "-3000"},
            {"type": "Package", "date": "2025-03-01", "miles": "+10000"},
        ]
    }

    return render(request, "dashboard_member.html", {
        "role": "member",
        "user": user_data,
        "member": member_data,
    })


def dashboard_staff(request):
    user_data = {
        "name": "Mr. Admin Aero",
        "email": "admin@aeromiles.com",
        "phone": "+62 811111111",
        "nationality": "Indonesia",
        "birthdate": "1988-01-01",
        "joined": "2023-01-01"
    }

    staff_data = {
        "staff_id": "S0001",
        "airline": "Garuda Indonesia",
        "pending": 2,
        "approved": 1,
        "rejected": 1
    }

    return render(request, "dashboard_staff.html", {
        "role": "staff",
        "user": user_data,
        "staff": staff_data,
    })
