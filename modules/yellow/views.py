from django.shortcuts import render
from modules.green.models import (
    Member, Staf, Maskapai, Bandara,
    ClaimMissingMiles, Pengguna
)

# Create your views here.

def page_view(request):
    members = Member.objects.all()
    staf = Staf.objects.all()
    maskapai = Maskapai.objects.all()
    bandara = Bandara.objects.all()
    claim_missing_miles = ClaimMissingMiles.objects.all()
    pengguna = Pengguna.objects.all()

    context = {
        'members': members,
        'staf': staf,
        'maskapai': maskapai,
        'bandara': bandara,
        'claim_missing_miles': claim_missing_miles,
        'pengguna': pengguna,
    }
    return render(request, 'yellow/page.html', context)

def form_view(request):
    if request.method == 'POST':
        pass

    return render(request, 'yellow/form.html')
