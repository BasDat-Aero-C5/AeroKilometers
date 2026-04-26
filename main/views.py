from django.shortcuts import render

# Create your views here.
def homepage(request):
    return render(request, 'homepage.html')

def login(request):
    return render(request, 'login.html')

def register(request):
    # test
    return render(request, 'register.html')
