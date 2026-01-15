from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages

# REGISTER
def register_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )

        login(request, user)

        if next_url:
            return redirect(next_url)

        return redirect("/dashboard/")

    return render(request, "register.html", {"next": next_url})


# LOGIN


def login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            # ✅ redirect to next if exists
            if next_url:
                return redirect(next_url)

            return redirect("/dashboard/")
        else:
            messages.error(request, "Invalid email or password")

    return render(request, "login.html", {"next": next_url})



# LOGOUT
def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("/login/")