# Sai Health Care - Hospital Management System
# *** FINAL VERSION: Integrated Twilio Verify API for real OTP via SMS. ***
# *** FINAL VERSION: Added a dedicated /payment_success route and template. ***
# *** NEW FEATURE: Added /doctor_monthly_stats route and helper functions. ***
# *** NEW FEATURE: Added /patient_history route and template. ***
# *** NEW FEATURE: Added variable prescription fees. ***
# *** MODIFIED: Appointment status set to 'Completed' upon prescription creation. ***
# *** MODIFIED: Redesigned HOME_HTML for patient dashboard. ***

from flask import Flask, render_template_string, request, redirect, url_for, session, make_response
from datetime import datetime, timedelta
import os
import secrets
from flask_bcrypt import Bcrypt
import random # Kept for mock fallback
import json

import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client

# --- Twilio Configuration (UPDATED WITH YOUR CREDENTIALS) ---
TWILIO_ACCOUNT_SID = 'ACe4e5ac754874739f1eb3e55b1b75eaf0'
TWILIO_AUTH_TOKEN = '1d58013d204f8e129ed98a5f0343127a'
TWILIO_VERIFY_SERVICE_SID = 'VA759256ff22e07433fab4c330f31a9992' # <<< YOUR SERVICE SID ADDED
# -------------------------------------------------------------------------

# Your downloaded service account key file
SERVICE_ACCOUNT_KEY_PATH = 'hospitalsystem-2d1a0-firebase-adminsdk-fbsvc-cd28eac6d3.json'

# Load credentials from the JSON file
try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK successfully initialized.")
    db = firestore.client()
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    db = None
    print("Falling back to in-memory database simulation.")


# --- CONFIGURATION: PRE-DEFINED PROFILE PICTURES (The "Store Memory") ---
PROFILE_PIC_CHOICES = {
    'default': 'https://placehold.co/128x128/42a5f5/ffffff?text=User',
    'avatar_1': 'https://i.imgur.com/8Q8pYvM.png', # Generic Person 1
    'avatar_2': 'https://i.imgur.com/v4XyYwT.png', # Generic Person 2
    'avatar_3': 'https://i.imgur.com/vB1h5tF.png', # Generic Person 3
    'medical_icon': 'https://i.imgur.com/s6zB1pZ.png', # Medical Icon
}


# --- In-Memory Fallback "Database" ---
in_memory_db = {
    'users': [],
    'appointments': [],
    'prescriptions': [],
    'payments': []
}
PATIENT_ID_COUNTER = 1000
DOCTOR_ID_COUNTER = 2000
DEFAULT_PRESCRIPTION_FEE = 200 # New constant for default fee

# --- Twilio OTP Helper Functions ---

def send_otp_via_twilio(phone_number, channel='sms'):
    """Sends OTP via Twilio Verify API. Fallback to mock if Twilio fails."""
    
    # Check if credentials are placeholders or invalid for security/testing
    if not TWILIO_VERIFY_SERVICE_SID or TWILIO_VERIFY_SERVICE_SID.startswith('VAx'):
        print("\n--- MOCK OTP ALERT (Using mock mode) ---")
        mock_otp = str(random.randint(100000, 999999))
        session['mock_otp'] = mock_otp
        session['otp_phone_number'] = phone_number
        print(f"MOCK OTP for {phone_number}: {mock_otp}")
        print(f"-----------------------------------------\n")
        return True
        
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        verification = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
            .verifications \
            .create(to=phone_number, channel=channel)
        
        session['otp_phone_number'] = phone_number
        print(f"Twilio SMS sent to {phone_number}. Status: {verification.status}")
        return verification.status == 'pending'
    except Exception as e:
        print(f"Error sending OTP via Twilio: {e}. Check E.164 format (+CCNNNNNNNNN) and Twilio balance.")
        return False

def check_otp_via_twilio(phone_number, otp_code):
    """Checks OTP via Twilio Verify API. Handles mock fallback."""
    if 'mock_otp' in session: # Handle mock fallback check
        if otp_code == session.get('mock_otp') and phone_number == session.get('otp_phone_number'):
            session.pop('mock_otp')
            session.pop('otp_phone_number')
            return True
        return False

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        verification_check = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID) \
            .verification_checks \
            .create(to=phone_number, code=otp_code)
        
        if verification_check.status == 'approved':
            session.pop('otp_phone_number', None)
            return True
        return False
    except Exception as e:
        print(f"Error checking OTP via Twilio: {e}")
        return False


# --- HTML Templates (UPDATED HOME_HTML) ---

LOGIN_REGISTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Login/Register</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f4c81;
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .logo-text { font-weight: 800; }
        .container {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .btn-primary {
            background-color: #0f4c81;
            transition: all 0.3s ease;
            transform: scale(1);
        }
        .btn-primary:hover {
            background-color: #125591;
            transform: scale(1.02);
        }
        .btn-secondary {
            background-color: #42b883;
            transition: all 0.3s ease;
            transform: scale(1);
        }
        .btn-secondary:hover {
            background-color: #3aa675;
            transform: scale(1.02);
        }
        .input-field {
            border: 2px solid #ddd;
            transition: border-color 0.3s ease;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container rounded-2xl w-full max-w-lg p-8 sm:p-12">
        <div class="text-center mb-8">
            <h1 class="text-4xl logo-text text-[#0f4c81] mb-2">SAI HEALTH CARE</h1>
            <p class="text-lg text-gray-600">Bringing Care to Life</p>
        </div>

        <div id="login-form-container">
            <h2 class="text-2xl font-bold text-center text-gray-800 mb-6">Login</h2>
            <form action="/login_register" method="post" class="space-y-6">
                <input type="hidden" name="form_type" value="login">
                <div>
                    <label for="login_email" class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input type="email" id="login_email" name="email" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div>
                    <label for="login_password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                    <input type="password" id="login_password" name="password" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div class="flex justify-center">
                    <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg">
                        Log In
                    </button>
                </div>
            </form>
            <p class="text-center text-gray-600 mt-6">
                Don't have an account? <a href="#" id="toggle-register" class="text-[#42b883] hover:underline font-bold">Register here</a>
            </p>
        </div>

        <div id="register-form-container" class="hidden">
            <h2 class="text-2xl font-bold text-center text-gray-800 mb-6">New User Registration</h2>
            <form action="/login_register" method="post" class="space-y-6">
                <input type="hidden" name="form_type" value="register">
                <div>
                    <label for="reg_name" class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                    <input type="text" id="reg_name" name="name" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div>
                    <label for="reg_email" class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input type="email" id="reg_email" name="email" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div>
                    <label for="reg_password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                    <input type="password" id="reg_password" name="password" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div>
                    <label for="reg_phone" class="block text-sm font-medium text-gray-700 mb-1">Phone Number (Use E.164: +CCNNNNNNNNN)</label>
                    <input type="tel" id="reg_phone" name="phone" required class="input-field w-full px-4 py-2 rounded-lg">
                </div>
                <div>
                    <label for="reg_role" class="block text-sm font-medium text-gray-700 mb-1">Register As</label>
                    <select id="reg_role" name="role" class="input-field w-full px-4 py-2 rounded-lg">
                        <option value="patient">Patient</option>
                        <option value="doctor">Doctor</option>
                    </select>
                </div>
                <div id="doctor-fields" class="hidden space-y-4">
                    <div>
                        <label for="reg_specialty" class="block text-sm font-medium text-gray-700 mb-1">Specialty</label>
                        <input type="text" id="reg_specialty" name="specialty" class="input-field w-full px-4 py-2 rounded-lg">
                    </div>
                </div>
                <div class="flex justify-center">
                    <button type="submit" class="btn-secondary w-full text-white font-bold py-3 px-6 rounded-lg">
                        Register (Requires OTP)
                    </button>
                </div>
            </form>
            <p class="text-center text-gray-600 mt-6">
                Already have an account? <a href="#" id="toggle-login" class="text-[#0f4c81] hover:underline font-bold">Login here</a>
            </p>
        </div>
    </div>
    <script type="module">
        // Frontend-only UI logic
        const loginContainer = document.getElementById('login-form-container');
        const registerContainer = document.getElementById('register-form-container');
        const toggleRegisterBtn = document.getElementById('toggle-register');
        const toggleLoginBtn = document.getElementById('toggle-login');
        const mainContainer = document.querySelector('.container');
        const regRoleSelect = document.getElementById('reg_role');
        const doctorFields = document.getElementById('doctor-fields');

        regRoleSelect.addEventListener('change', (e) => {
            if (e.target.value === 'doctor') {
                doctorFields.classList.remove('hidden');
            } else {
                doctorFields.classList.add('hidden');
            }
        });

        toggleRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            loginContainer.classList.add('hidden');
            registerContainer.classList.remove('hidden');
        });

        toggleLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            registerContainer.classList.add('hidden');
            loginContainer.classList.remove('hidden');
        });
    </script>
</body>
</html>
"""

OTP_REGISTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Confirm Registration</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f4c81;
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .container {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .btn-secondary {
            background-color: #42b883;
            transition: all 0.3s ease;
        }
        .btn-secondary:hover {
            background-color: #3aa675;
        }
        .input-field {
            border: 2px solid #ddd;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container rounded-2xl w-full max-w-md p-8 sm:p-10 text-center">
        <h2 class="text-3xl font-bold text-gray-800 mb-4">Confirm Registration</h2>
        <p class="text-gray-600 mb-2">A 6-digit verification code has been sent to **{{ phone_number }}**.</p>
        <p class="text-sm text-red-500 mb-6">If using the mock mode, check your terminal for the code.</p>
        {% if error %}
            <p class="text-red-500 font-bold mb-4">{{ error }}</p>
        {% endif %}
        <form action="/confirm_otp_register" method="post" class="space-y-6">
            <div>
                <label for="otp_code" class="block text-sm font-medium text-gray-700 mb-1">Enter OTP Code</label>
                <input type="text" id="otp_code" name="otp_code" required maxlength="6" class="input-field w-full px-4 py-3 text-center text-2xl tracking-widest rounded-lg">
            </div>
            <button type="submit" class="btn-secondary w-full text-white font-bold py-3 px-6 rounded-lg">
                Verify and Complete Registration
            </button>
        </form>
    </div>
</body>
</html>
"""

OTP_APPOINTMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Confirm Appointment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f4c81;
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .container {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .btn-secondary {
            background-color: #42b883;
            transition: all 0.3s ease;
        }
        .btn-secondary:hover {
            background-color: #3aa675;
        }
        .input-field {
            border: 2px solid #ddd;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container rounded-2xl w-full max-w-md p-8 sm:p-10 text-center">
        <h2 class="text-3xl font-bold text-gray-800 mb-4">Confirm Appointment</h2>
        <p class="text-gray-600 mb-2">Enter the verification code sent to your phone number **{{ phone_number }}** to confirm your booking.</p>
        <p class="text-sm text-red-500 mb-6">If using the mock mode, check your terminal for the code.</p>
        {% if error %}
            <p class="text-red-500 font-bold mb-4">{{ error }}</p>
        {% endif %}
        <form action="/confirm_otp_appointment" method="post" class="space-y-6">
            <div>
                <label for="otp_code" class="block text-sm font-medium text-gray-700 mb-1">Enter OTP Code</label>
                <input type="text" id="otp_code" name="otp_code" required maxlength="6" class="input-field w-full px-4 py-3 text-center text-2xl tracking-widest rounded-lg">
            </div>
            <button type="submit" class="btn-secondary w-full text-white font-bold py-3 px-6 rounded-lg">
                Verify and Book
            </button>
        </form>
    </div>
</body>
</html>
"""

PAYMENT_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Payment Successful</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .bg-success { background-color: #42b883; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-12 rounded-2xl shadow-xl w-full max-w-lg text-center border-t-8 border-t-green-500">
        <svg class="w-20 h-20 text-green-500 mx-auto mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <h1 class="text-3xl font-bold text-gray-800 mb-2">Payment Successful!</h1>
        <p class="text-gray-600 mb-6">Thank you, your payment of **₹{{ amount }}** has been successfully processed.</p>
        
        <div class="bg-gray-100 p-4 rounded-lg mb-8">
            <p class="text-sm font-semibold text-gray-700">Transaction Date: {{ datetime_now }}</p>
        </div>

        <a href="/home" class="bg-green-500 hover:bg-green-600 text-white font-bold py-3 px-8 rounded-full shadow-lg transition duration-200">
            Go to Home Dashboard
        </a>
    </div>
</body>
</html>
"""

HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Home Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .header-bg {
            background-color: #0f4c81; /* Dark Blue */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .classic-font {
            font-family: 'Playfair Display', serif;
            letter-spacing: -0.05em;
        }
        .action-block {
            background-color: white;
            transition: all 0.3s ease;
        }
        .action-block:hover {
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            transform: translateY(-4px);
        }
        .icon-color { color: #42b883; }
        .patient-name-color { color: #125591; }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="header-bg text-white p-4 flex justify-between items-center shadow-lg sticky top-0 z-10">
        <div class="flex items-center space-x-4">
            <h1 class="text-xl sm:text-2xl font-extrabold">SAI HEALTH CARE</h1>
        </div>
        <nav class="flex items-center space-x-4">
            <a href="/profile" class="text-white hover:text-gray-200 transition-colors duration-200 hidden sm:inline">Profile</a>
            <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-1 px-3 rounded-full shadow-md transition-transform duration-200 hover:scale-105 text-sm">Log Out</a>
        </nav>
    </header>
    
    <main class="flex-grow flex flex-col items-center p-4 sm:p-8">
        <!-- Dashboard Header Block -->
        <div class="header-bg text-white w-full max-w-6xl rounded-xl p-8 sm:p-12 mb-8 h-48 sm:h-64 flex flex-col justify-center">
            <p class="text-2xl sm:text-3xl font-semibold mb-1 opacity-90 classic-font">Welcome back,</p>
            <h2 class="text-4xl sm:text-6xl font-black classic-font text-white">
                <span class="patient-name-color bg-white px-2 py-1 rounded-lg inline-block shadow-md">
                    {{ session['user_name'] }}
                </span>
            </h2>
        </div>

        <!-- Action Blocks -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-6xl">
            
            <!-- 1. View Profile Block -->
            <a href="/profile" class="action-block rounded-2xl p-8 flex flex-col items-center text-center border border-gray-100">
                <svg class="w-12 h-12 icon-color mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                <h3 class="text-xl font-bold text-[#0f4c81] mb-2">View Profile</h3>
                <p class="text-sm text-gray-500">Manage personal details, age, gender, and picture preferences.</p>
            </a>

            <!-- 2. Book Appointment Block -->
            <a href="/book_appointment" class="action-block rounded-2xl p-8 flex flex-col items-center text-center border border-gray-100">
                <svg class="w-12 h-12 icon-color mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                <h3 class="text-xl font-bold text-[#0f4c81] mb-2">Book Appointment</h3>
                <p class="text-sm text-gray-500">Schedule a consultation with an available specialist instantly.</p>
            </a>

            <!-- 3. Pending Payments Block -->
            <a href="/pending_payments" class="action-block rounded-2xl p-8 flex flex-col items-center text-center border border-gray-100">
                <svg class="w-12 h-12 icon-color mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m4 0h6m-6 0h-2m8-4v2m-4-2H9m-2 4h4"></path></svg>
                <h3 class="text-xl font-bold text-[#0f4c81] mb-2">Pending Payments</h3>
                <p class="text-sm text-gray-500">View outstanding fees and settle prescription costs quickly.</p>
            </a>
            
            <!-- Additional Action: Medical History -->
            <div class="md:col-span-3 text-center mt-4">
                <a href="/patient_history" class="text-[#42b883] hover:underline font-semibold text-lg py-2 px-4 rounded-lg transition-colors">
                    View Full Medical History →
                </a>
            </div>
        </div>
    </main>
</body>
</html>
"""

OTP_REGISTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Confirm Registration</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f4c81;
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .container {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .btn-secondary {
            background-color: #42b883;
            transition: all 0.3s ease;
        }
        .btn-secondary:hover {
            background-color: #3aa675;
        }
        .input-field {
            border: 2px solid #ddd;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container rounded-2xl w-full max-w-md p-8 sm:p-10 text-center">
        <h2 class="text-3xl font-bold text-gray-800 mb-4">Confirm Registration</h2>
        <p class="text-gray-600 mb-2">A 6-digit verification code has been sent to **{{ phone_number }}**.</p>
        <p class="text-sm text-red-500 mb-6">If using the mock mode, check your terminal for the code.</p>
        {% if error %}
            <p class="text-red-500 font-bold mb-4">{{ error }}</p>
        {% endif %}
        <form action="/confirm_otp_register" method="post" class="space-y-6">
            <div>
                <label for="otp_code" class="block text-sm font-medium text-gray-700 mb-1">Enter OTP Code</label>
                <input type="text" id="otp_code" name="otp_code" required maxlength="6" class="input-field w-full px-4 py-3 text-center text-2xl tracking-widest rounded-lg">
            </div>
            <button type="submit" class="btn-secondary w-full text-white font-bold py-3 px-6 rounded-lg">
                Verify and Complete Registration
            </button>
        </form>
    </div>
</body>
</html>
"""

OTP_APPOINTMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Confirm Appointment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0f4c81;
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .container {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .btn-secondary {
            background-color: #42b883;
            transition: all 0.3s ease;
        }
        .btn-secondary:hover {
            background-color: #3aa675;
        }
        .input-field {
            border: 2px solid #ddd;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="container rounded-2xl w-full max-w-md p-8 sm:p-10 text-center">
        <h2 class="text-3xl font-bold text-gray-800 mb-4">Confirm Appointment</h2>
        <p class="text-gray-600 mb-2">Enter the verification code sent to your phone number **{{ phone_number }}** to confirm your booking.</p>
        <p class="text-sm text-red-500 mb-6">If using the mock mode, check your terminal for the code.</p>
        {% if error %}
            <p class="text-red-500 font-bold mb-4">{{ error }}</p>
        {% endif %}
        <form action="/confirm_otp_appointment" method="post" class="space-y-6">
            <div>
                <label for="otp_code" class="block text-sm font-medium text-gray-700 mb-1">Enter OTP Code</label>
                <input type="text" id="otp_code" name="otp_code" required maxlength="6" class="input-field w-full px-4 py-3 text-center text-2xl tracking-widest rounded-lg">
            </div>
            <button type="submit" class="btn-secondary w-full text-white font-bold py-3 px-6 rounded-lg">
                Verify and Book
            </button>
        </form>
    </div>
</body>
</html>
"""

PAYMENT_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Payment Successful</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .bg-success { background-color: #42b883; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-12 rounded-2xl shadow-xl w-full max-w-lg text-center border-t-8 border-t-green-500">
        <svg class="w-20 h-20 text-green-500 mx-auto mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <h1 class="text-3xl font-bold text-gray-800 mb-2">Payment Successful!</h1>
        <p class="text-gray-600 mb-6">Thank you, your payment of **₹{{ amount }}** has been successfully processed.</p>
        
        <div class="bg-gray-100 p-4 rounded-lg mb-8">
            <p class="text-sm font-semibold text-gray-700">Transaction Date: {{ datetime_now }}</p>
        </div>

        <a href="/home" class="bg-green-500 hover:bg-green-600 text-white font-bold py-3 px-8 rounded-full shadow-lg transition duration-200">
            Go to Home Dashboard
        </a>
    </div>
</body>
</html>
"""

APPOINTMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Book Appointment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
        .btn-primary { background-color: #42b883; transition: all 0.3s ease; transform: scale(1); }
        .btn-primary:hover { background-color: #3aa675; transform: scale(1.02); }
        .input-field { border: 2px solid #ddd; transition: border-color 0.3s ease; }
        .input-field:focus { border-color: #42b883; outline: none; box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <nav class="flex items-center space-x-4">
            <a href="/profile" class="text-white hover:text-gray-200 transition-colors duration-200">Profile</a>
            <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
        </nav>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-2xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-6">Book an Appointment</h1>
            <p class="text-gray-600 text-center mb-8">Select an available doctor and a suitable time slot.</p>
            
            <div class="space-y-6">
                {% for doctor in doctors %}
                <div class="bg-gray-50 p-6 rounded-xl shadow-sm">
                    <h2 class="text-xl font-semibold text-gray-800">{{ doctor.name }}</h2>
                    <p class="text-gray-500 mb-4">{{ doctor.specialty }}</p>
                    
                    <form action="/book_appointment" method="post" class="space-y-4">
                        <input type="hidden" name="doctor_id" value="{{ doctor.id }}">
                        <div>
                            <label for="date-{{ doctor.id }}" class="block text-sm font-medium text-gray-700 mb-1">Date</label>
                            <input type="date" id="date-{{ doctor.id }}" name="date" required class="input-field w-full px-4 py-2 rounded-lg">
                        </div>
                        <div>
                            <label for="time-{{ doctor.id }}" class="block text-sm font-medium text-gray-700 mb-1">Time</label>
                            <input type="time" id="time-{{ doctor.id }}" name="time" required class="input-field w-full px-4 py-2 rounded-lg">
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg shadow-md">
                                Book Now (Requires OTP)
                            </button>
                        </div>
                    </form>
                </div>
                {% else %}
                <p class="text-gray-500 text-center">No doctors are currently available for booking.</p>
                {% endfor %}
            </div>
            
            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
</body>
</html>
"""

PENDING_PAYMENTS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Pending Payments</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-4xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-6">Pending Payments</h1>
            <p class="text-gray-600 text-center mb-8">You have **{{ prescriptions|length }}** outstanding payment(s) for prescriptions.</p>

            <div class="space-y-4">
                {% if prescriptions %}
                    {% for prescription in prescriptions %}
                    <div class="bg-gray-50 p-6 rounded-xl shadow-md border-l-4 border-red-500">
                        <p class="text-sm text-gray-500 mb-1">Prescription Date: **{{ prescription.date }}**</p>
                        <p class="font-semibold text-gray-800 mb-4">Doctor: **{{ prescription.doctor_name }}**</p>
                        
                        <div class="flex justify-between items-center">
                            <span class="text-2xl font-bold text-red-600">₹{{ prescription.amount }} DUE</span>
                            <form action="/payment" method="get">
                                <input type="hidden" name="prescription_id" value="{{ prescription._id }}">
                                <button type="submit" class="bg-[#0f4c81] hover:bg-[#125591] text-white font-bold py-2 px-6 rounded-full transition duration-200">
                                    Pay Now
                                </button>
                            </form>
                        </div>
                        <ul class="list-disc list-inside text-gray-600 mt-4 pl-4 text-sm">
                            <li>**Notes:** {{ prescription.notes }}</li>
                        </ul>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="bg-green-100 p-6 rounded-xl shadow-md text-center">
                        <p class="text-green-700 font-semibold">🎉 No pending payments at this time. You are all caught up!</p>
                    </div>
                {% endif %}
            </div>

            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
</body>
</html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Profile</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-4xl mt-8">
            <div class="flex flex-col sm:flex-row items-center space-y-6 sm:space-y-0 sm:space-x-8 mb-8">
                <div class="flex-shrink-0">
                    <img id="profile-img" class="h-32 w-32 rounded-full object-cover border-4 border-[#42b883]" src="{{ user.profile_pic_url }}" alt="User Profile Image">
                </div>
                <div class="text-center sm:text-left">
                    <h1 class="text-4xl font-bold text-gray-800">{{ user.name }}</h1>
                    <p class="text-lg text-gray-500">Patient ID: <span class="font-bold text-[#0f4c81]">{{ user.patient_id }}</span></p>
                </div>
            </div>

            <hr class="my-6 border-t border-gray-200">

            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 text-gray-700">
                <div class="bg-gray-50 p-6 rounded-xl shadow-inner">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Personal Information</h2>
                    <form action="/update_profile" method="post" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Email</label>
                            <span class="text-lg font-semibold text-gray-900">{{ user.email }}</span>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Phone</label>
                            <span class="text-lg font-semibold text-gray-900">{{ user.phone }}</span>
                        </div>
                        <div>
                            <label for="age" class="block text-sm font-medium text-gray-700 mb-1">Age</label>
                            <input type="number" id="age" name="age" value="{{ user.age }}" class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]">
                        </div>
                        <div>
                            <label for="gender" class="block text-sm font-medium text-gray-700 mb-1">Gender</label>
                            <select id="gender" name="gender" class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]">
                                <option value="Not specified" {% if user.gender == 'Not specified' %}selected{% endif %}>Prefer not to say</option>
                                <option value="Male" {% if user.gender == 'Male' %}selected{% endif %}>Male</option>
                                <option value="Female" {% if user.gender == 'Female' %}selected{% endif %}>Female</option>
                            </select>
                        </div>
                        <div>
                            <label for="profile_pic_url" class="block text-sm font-medium text-gray-700 mb-1">Select Profile Picture (Store)</label>
                            <select id="profile_pic_url" name="profile_pic_url" class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]">
                                {% for key, url in pic_choices.items() %}
                                    <option value="{{ url }}" {% if user.profile_pic_url == url %}selected{% endif %}>
                                        {{ key | replace('_', ' ') | capitalize }}
                                    </option>
                                {% endfor %}
                            </select>
                            <p class="text-xs text-gray-500 mt-1">Picture will update instantly below.</p>
                        </div>
                        <button type="submit" class="w-full bg-[#42b883] hover:bg-[#3aa675] text-white font-bold py-2 px-4 rounded-lg transition duration-200">
                            Update Profile
                        </button>
                    </form>
                </div>
                
                <div class="bg-gray-50 p-6 rounded-xl shadow-inner">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Prescription History (Summary)</h2>
                    {% if prescriptions %}
                    <div class="space-y-4">
                        {% for prescription in prescriptions %}
                        <div class="bg-white p-4 rounded-lg shadow-sm border-l-4 {% if prescription.payment_status == 'pending' %} border-red-500 {% else %} border-green-500 {% endif %}">
                            <p class="text-sm text-gray-500 mb-1">Date: {{ prescription.date }}</p>
                            <p class="font-semibold text-gray-800">Doctor: {{ prescription.doctor_name }}</p>
                            <p class="text-sm font-bold mt-2 {% if prescription.payment_status == 'pending' %} text-red-600 {% else %} text-green-600 {% endif %}">
                                Payment: {{ prescription.payment_status | capitalize }} (₹{{ prescription.amount }})
                            </p>
                            <a href="/patient_history" class="text-xs text-[#0f4c81] hover:underline mt-1 block">View Full History</a>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="text-gray-500 text-center">No prescriptions available.</p>
                    {% endif %}
                </div>
            </div>
            
            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
    <script>
        document.getElementById('profile_pic_url').addEventListener('change', function() {
            document.getElementById('profile-img').src = this.value;
        });
    </script>
</body>
</html>
"""

APPOINTMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Book Appointment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
        .btn-primary { background-color: #42b883; transition: all 0.3s ease; transform: scale(1); }
        .btn-primary:hover { background-color: #3aa675; transform: scale(1.02); }
        .input-field { border: 2px solid #ddd; transition: border-color 0.3s ease; }
        .input-field:focus { border-color: #42b883; outline: none; box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <nav class="flex items-center space-x-4">
            <a href="/profile" class="text-white hover:text-gray-200 transition-colors duration-200">Profile</a>
            <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
        </nav>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-2xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-6">Book an Appointment</h1>
            <p class="text-gray-600 text-center mb-8">Select an available doctor and a suitable time slot.</p>
            
            <div class="space-y-6">
                {% for doctor in doctors %}
                <div class="bg-gray-50 p-6 rounded-xl shadow-sm">
                    <h2 class="text-xl font-semibold text-gray-800">{{ doctor.name }}</h2>
                    <p class="text-gray-500 mb-4">{{ doctor.specialty }}</p>
                    
                    <form action="/book_appointment" method="post" class="space-y-4">
                        <input type="hidden" name="doctor_id" value="{{ doctor.id }}">
                        <div>
                            <label for="date-{{ doctor.id }}" class="block text-sm font-medium text-gray-700 mb-1">Date</label>
                            <input type="date" id="date-{{ doctor.id }}" name="date" required class="input-field w-full px-4 py-2 rounded-lg">
                        </div>
                        <div>
                            <label for="time-{{ doctor.id }}" class="block text-sm font-medium text-gray-700 mb-1">Time</label>
                            <input type="time" id="time-{{ doctor.id }}" name="time" required class="input-field w-full px-4 py-2 rounded-lg">
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg shadow-md">
                                Book Now (Requires OTP)
                            </button>
                        </div>
                    </form>
                </div>
                {% else %}
                <p class="text-gray-500 text-center">No doctors are currently available for booking.</p>
                {% endfor %}
            </div>
            
            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
</body>
</html>
"""

PAYMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Make a Payment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .bg-gradient {
            background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%);
        }
        .input-field {
            border: 2px solid #ddd;
            transition: border-color 0.3s ease;
        }
        .input-field:focus {
            border-color: #42b883;
            outline: none;
            box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.2);
        }
        .btn-primary {
            background-color: #42b883;
            transition: all 0.3s ease;
            transform: scale(1);
        }
        .btn-primary:hover {
            background-color: #3aa675;
            transform: scale(1.02);
        }
        .tab-btn {
            border-bottom: 3px solid transparent;
            transition: border-color 0.3s ease;
        }
        .tab-btn.active {
            border-bottom: 3px solid #42b883;
            color: #42b883;
        }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <nav class="flex items-center space-x-4">
            <a href="/profile" class="text-white hover:text-gray-200 transition-colors duration-200">Profile</a>
            <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
        </nav>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-2xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-2">Make a Payment</h1>
            <p class="text-center font-bold text-gray-800 mb-6">Amount to Pay: ₹{{ prescription.amount }}</p>
            <p class="text-center font-bold text-gray-800 mb-6">Payment for Prescription ID: <span class="text-[#0f4c81]">{{ prescription._id }}</span></p>


            <input type="hidden" id="prescription-id" value="{{ prescription._id }}">
            <input type="hidden" id="amount" value="{{ prescription.amount }}">
            <input type="hidden" id="doctor-id" value="{{ prescription.doctor_id }}">
            
            <div class="flex justify-around border-b border-gray-200 mb-6">
                <button id="card-tab" class="tab-btn active px-4 py-2 font-semibold text-gray-600 hover:text-gray-800 transition-colors duration-200">
                    Card
                </button>
                <button id="upi-tab" class="tab-btn px-4 py-2 font-semibold text-gray-600 hover:text-gray-800 transition-colors duration-200">
                    UPI
                </button>
                <button id="net-banking-tab" class="tab-btn px-4 py-2 font-semibold text-gray-600 hover:text-gray-800 transition-colors duration-200">
                    Net Banking
                </button>
            </div>

            <div id="payment-content">
                <div id="card-payment-form" class="payment-form">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">Pay with Card</h2>
                    <form action="/process_payment" method="post" class="space-y-6">
                        <input type="hidden" name="payment_method" value="Card">
                        <input type="hidden" name="amount" value="{{ prescription.amount }}">
                        <input type="hidden" name="prescription_id" value="{{ prescription._id }}">
                        <div>
                            <label for="card_number" class="block text-sm font-medium text-gray-700 mb-1">Card Number</label>
                            <input type="text" id="card_number" name="card_number" required class="input-field w-full px-4 py-2 rounded-lg" placeholder="XXXX XXXX XXXX XXXX">
                        </div>
                        <div>
                            <label for="card_name" class="block text-sm font-medium text-gray-700 mb-1">Name on Card</label>
                            <input type="text" id="card_name" name="card_name" required class="input-field w-full px-4 py-2 rounded-lg" placeholder="Full Name">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label for="expiry" class="block text-sm font-medium text-gray-700 mb-1">Expiry Date</label>
                                <input type="text" id="expiry" name="expiry" required class="input-field w-full px-4 py-2 rounded-lg" placeholder="MM/YY">
                            </div>
                            <div>
                                <label for="cvv" class="block text-sm font-medium text-gray-700 mb-1">CVV</label>
                                <input type="text" id="cvv" name="cvv" required class="input-field w-full px-4 py-2 rounded-lg" placeholder="123">
                            </div>
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg shadow-md">
                                Pay Now
                            </button>
                        </div>
                    </form>
                </div>

                <div id="upi-payment-form" class="payment-form hidden">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">Pay with UPI</h2>
                    <form action="/process_payment" method="post" class="space-y-6">
                        <input type="hidden" name="payment_method" value="UPI">
                        <input type="hidden" name="amount" value="{{ prescription.amount }}">
                        <input type="hidden" name="prescription_id" value="{{ prescription._id }}">
                        <div>
                            <label for="upi_id" class="block text-sm font-medium text-gray-700 mb-1">Your UPI ID</label>
                            <input type="text" id="upi_id" name="upi_id" required class="input-field w-full px-4 py-2 rounded-lg" placeholder="username@bank">
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg shadow-md">
                                Pay Now
                            </button>
                        </div>
                    </form>
                </div>

                <div id="net-banking-form" class="payment-form hidden">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">Pay with Net Banking</h2>
                    <form action="/process_payment" method="post" class="space-y-6">
                        <input type="hidden" name="payment_method" value="Net Banking">
                        <input type="hidden" name="amount" value="{{ prescription.amount }}">
                        <input type="hidden" name="prescription_id" value="{{ prescription._id }}">
                        <div>
                            <label for="bank" class="block text-sm font-medium text-gray-700 mb-1">Select Your Bank</label>
                            <select id="bank" name="bank" required class="input-field w-full px-4 py-2 rounded-lg">
                                <option value="">Select a Bank</option>
                                <option value="HDFC">HDFC Bank</option>
                                <option value="ICICI">ICICI Bank</option>
                                <option value="SBI">State Bank of India</option>
                                <option value="AXIS">Axis Bank</option>
                            </select>
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn-primary w-full text-white font-bold py-3 px-6 rounded-lg shadow-md">
                                Pay Now
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const tabs = document.querySelectorAll('.tab-btn');
            const forms = document.querySelectorAll('.payment-form');

            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    tabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    forms.forEach(form => form.classList.add('hidden'));
                    const targetFormId = tab.id.replace('-tab', '-payment-form');
                    document.getElementById(targetFormId).classList.remove('hidden');
                });
            });
        });
    </script>
</body>
</html>
"""

DOCTOR_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Doctor Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-5xl mt-8">
            <div class="flex flex-col sm:flex-row items-center space-y-6 sm:space-y-0 sm:space-x-8 mb-8">
                <div class="flex-shrink-0">
                    <img class="h-32 w-32 rounded-full object-cover border-4 border-[#42b883]" src="https://placehold.co/128x128/42a5f5/ffffff?text=Doctor" alt="Doctor Profile Image">
                </div>
                <div class="text-center sm:text-left">
                    <h1 class="text-4xl font-bold text-gray-800">{{ doctor.name }}</h1>
                    <p class="text-lg text-gray-500">{{ doctor.specialty }}</p>
                </div>
                <div class="flex-grow text-right mt-4 sm:mt-0 space-y-2">
                    <form action="/toggle_availability" method="post">
                        <input type="hidden" name="doctor_id" value="{{ doctor.id }}">
                        <button type="submit" class="font-bold py-2 px-6 rounded-full shadow-md transition-transform duration-200 hover:scale-105
                            {% if doctor.available %} bg-green-500 text-white {% else %} bg-red-500 text-white {% endif %}">
                            {% if doctor.available %}
                                Available
                            {% else %}
                                Unavailable
                            {% endif %}
                        </button>
                    </form>
                    <a href="/doctor_monthly_stats" class="bg-[#42b883] hover:bg-[#3aa675] text-white font-bold py-2 px-6 rounded-full shadow-md transition-transform duration-200 hover:scale-105 inline-block mt-2">
                        View Monthly Earnings
                    </a>
                    </div>
            </div>

            <hr class="my-6 border-t-2 border-gray-200">

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div>
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Upcoming Appointments ({{ appointments_booked|length }})</h2>
                    <div class="overflow-x-auto rounded-xl shadow-sm">
                        <table class="min-w-full bg-white rounded-xl">
                            <thead class="bg-gray-200">
                                <tr>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Date</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Time</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Patient Name</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Status</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for appointment in appointments_booked %}
                                <tr class="border-b border-gray-200 hover:bg-gray-50">
                                    <td class="px-4 py-3 text-sm text-gray-600">{{ appointment.date }}</td>
                                    <td class="px-4 py-3 text-sm text-gray-600">{{ appointment.time }}</td>
                                    <td class="px-4 py-3 text-sm text-gray-600">{{ appointment.patient_name }}</td>
                                    <td class="px-4 py-3 text-sm font-semibold text-yellow-600">{{ appointment.status }}</td>
                                    <td class="px-4 py-3 text-sm text-gray-600">
                                        <button onclick="showPrescriptionForm('{{ appointment.patient_id }}', '{{ appointment._id }}')" class="text-[#0f4c81] hover:underline font-semibold">Write Prescription</button>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% if not appointments_booked %}
                        <p class="text-gray-500 text-center py-4">No upcoming appointments.</p>
                        {% endif %}
                    </div>
    
                    <div id="prescription-form-container" class="hidden mt-8 bg-gray-100 p-6 rounded-xl shadow-inner">
                        <h3 class="text-xl font-bold text-gray-800 mb-4">Write Prescription for Patient <span id="patient-id-display" class="text-[#42b883] font-bold"></span></h3>
                        <form action="/add_prescription" method="post" class="space-y-4">
                            <input type="hidden" id="prescription-patient-id" name="patient_id">
                            <input type="hidden" id="appointment-doc-id" name="appointment_doc_id">
                            <div>
                                <label for="medication" class="block text-sm font-medium text-gray-700 mb-1">Medication (comma-separated)</label>
                                <input type="text" id="medication" name="medication" required class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]">
                            </div>
                            <div>
                                <label for="notes" class="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                                <textarea id="notes" name="notes" rows="4" required class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]"></textarea>
                            </div>
                            <div>
                                <label for="fee" class="block text-sm font-medium text-gray-700 mb-1">Prescription Fee (₹)</label>
                                <input type="number" id="fee" name="fee" value="{{ DEFAULT_PRESCRIPTION_FEE }}" min="100" required class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#42b883]">
                            </div>
                            <div class="flex justify-end space-x-2">
                                <button type="button" onclick="hidePrescriptionForm()" class="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded-lg">Cancel</button>
                                <button type="submit" class="bg-[#42b883] hover:bg-[#3aa675] text-white font-bold py-2 px-4 rounded-lg">Submit</button>
                            </div>
                        </form>
                    </div>

                    <h2 class="text-2xl font-bold text-gray-800 mt-8 mb-4">Completed Appointments ({{ appointments_completed|length }})</h2>
                    <div class="overflow-x-auto rounded-xl shadow-sm">
                        <table class="min-w-full bg-white rounded-xl">
                            <thead class="bg-gray-200">
                                <tr>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Date</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Patient Name</th>
                                    <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for appointment in appointments_completed %}
                                <tr class="border-b border-gray-200 hover:bg-gray-50">
                                    <td class="px-4 py-3 text-sm text-gray-600">{{ appointment.date }}</td>
                                    <td class="px-4 py-3 text-sm text-gray-600">{{ appointment.patient_name }}</td>
                                    <td class="px-4 py-3 text-sm font-semibold text-green-600">{{ appointment.status }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% if not appointments_completed %}
                        <p class="text-gray-500 text-center py-4">No completed appointments yet.</p>
                        {% endif %}
                    </div>
                </div>
    
                <div>
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Doctor's Statistics</h2>
                    <div class="bg-gray-100 p-6 rounded-xl shadow-sm">
                        <p class="text-lg font-semibold text-gray-700 mb-2">Total Patients Assigned: <span class="text-xl font-bold text-[#0f4c81]">{{ stats.patients_assigned }}</span></p>
                        <p class="text-lg font-semibold text-gray-700 mb-2">Prescriptions Written: <span class="text-xl font-bold text-[#0f4c81]">{{ stats.prescriptions_written }}</span></p>
                        <p class="text-lg font-semibold text-gray-700 mb-2">Appointments Completed: <span class="text-xl font-bold text-[#0f4c81]">{{ stats.appointments_completed }}</span></p>
                    </div>

                    <hr class="my-6 border-t-2 border-gray-200">

                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Payment Details (Today)</h2>
                    <div class="bg-gray-100 p-6 rounded-xl shadow-sm">
                        <p class="text-lg font-semibold text-gray-700 mb-4">Total Earnings: <span class="text-xl font-bold text-[#42b883]">₹{{ stats.total_earnings }}</span></p>
                        <div class="mb-6">
                            <h3 class="text-lg font-semibold text-gray-800 mb-2">Earnings by Hour</h3>
                            <canvas id="todayEarningsChart" height="120"></canvas>
                        </div>
                        <div class="overflow-x-auto rounded-xl shadow-sm">
                            <table class="min-w-full bg-white rounded-xl">
                                <thead class="bg-gray-200">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Patient Name</th>
                                        <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Amount</th>
                                        <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Payment Method</th>
                                        <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Time</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for payment in today_payments %}
                                    <tr class="border-b border-gray-200 hover:bg-gray-50">
                                        <td class="px-4 py-3 text-sm text-gray-600">{{ payment.patient_name }}</td>
                                        <td class="px-4 py-3 text-sm text-gray-600">₹{{ payment.amount }}</td>
                                        <td class="px-4 py-3 text-sm text-gray-600">{{ payment.payment_method }}</td>
                                        <td class="px-4 py-3 text-sm text-gray-600">{{ payment.timestamp.split(' ')[1] }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                            {% if not today_payments %}
                            <p class="text-gray-500 text-center py-4">No payments recorded today.</p>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>

            <div class="mt-8 text-center">
                <a href="/logout" class="text-[#0f4c81] hover:underline font-semibold">Log Out</a>
            </div>
        </div>
    </main>
    <script>
        function showPrescriptionForm(patientId, appointmentDocId) {
            document.getElementById('prescription-form-container').classList.remove('hidden');
            document.getElementById('prescription-patient-id').value = patientId;
            document.getElementById('appointment-doc-id').value = appointmentDocId; // Pass the appointment ID
            document.getElementById('patient-id-display').textContent = patientId;
        }
        function hidePrescriptionForm() {
            document.getElementById('prescription-form-container').classList.add('hidden');
            document.getElementById('prescription-patient-id').value = '';
            document.getElementById('appointment-doc-id').value = '';
        }
        // Render today's earnings chart
        document.addEventListener('DOMContentLoaded', function () {
            var ctx = document.getElementById('todayEarningsChart');
            if (ctx) {
                var chart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: {{ today_chart_labels | tojson }},
                        datasets: [{
                            label: 'Earnings (₹) by Hour',
                            data: {{ today_chart_values | tojson }},
                            backgroundColor: 'rgba(66, 184, 131, 0.5)',
                            borderColor: 'rgba(66, 184, 131, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }
        });
    </script>
</body>
</html>
"""

DOCTOR_MONTHLY_STATS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Monthly Earnings</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Bringing Care to Life</span>
        </div>
        <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-5xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-2">Monthly Earnings for Dr. {{ doctor.name }}</h1>
            <p class="text-gray-600 text-center mb-8">This report summarizes your earnings from completed prescription payments.</p>
            
            <hr class="my-6 border-t-2 border-gray-200">

            <h2 class="text-2xl font-bold text-gray-800 mb-4">Summary Table</h2>
            <div class="overflow-x-auto rounded-xl shadow-md mb-8">
                <table class="min-w-full bg-white">
                    <thead class="bg-gray-200">
                        <tr>
                            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Month</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Year</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Prescriptions Count</th>
                            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Total Earning (₹)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for stat in monthly_stats %}
                        <tr class="border-b border-gray-200 hover:bg-gray-50">
                            <td class="px-4 py-3 text-sm font-medium text-gray-700">{{ stat.month_year.split('-')[1] }}</td>
                            <td class="px-4 py-3 text-sm font-medium text-gray-700">{{ stat.month_year.split('-')[0] }}</td>
                            <td class="px-4 py-3 text-sm text-center text-gray-600">{{ stat.count }}</td>
                            <td class="px-4 py-3 text-lg font-bold text-[#42b883]">₹{{ stat.total_earnings }}</td>
                        </tr>
                        {% endfor %}
                        {% if not monthly_stats %}
                        <tr class="border-b border-gray-200">
                            <td colspan="4" class="px-4 py-4 text-center text-gray-500">No payment data recorded yet.</td>
                        </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>

            <hr class="my-6 border-t-2 border-gray-200">

            <h2 class="text-2xl font-bold text-gray-800 mb-4">Monthly Earnings Chart</h2>
            <div class="bg-white p-6 rounded-xl shadow-sm mb-8">
                <canvas id="monthlyEarningsChart" height="140"></canvas>
            </div>

            <div class="mt-8 text-center">
                <form action="/export_monthly_stats" method="get" class="inline-block">
                    <button type="submit" class="bg-[#0f4c81] hover:bg-[#125591] text-white font-bold py-3 px-6 rounded-full shadow-md transition-transform duration-200 hover:scale-105">
                        Download CSV
                    </button>
                </form>
                <a href="/doctor_dashboard" class="text-[#42b883] hover:underline font-semibold ml-4">Go back to Dashboard</a>
            </div>
        </div>
    </main>
    <script>
        // Prepare data for monthly chart
        const monthLabels = {{ monthly_chart_labels | tojson }};
        const monthValues = {{ monthly_chart_values | tojson }};
        const ctx = document.getElementById('monthlyEarningsChart');
        if (ctx) {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: monthLabels,
                    datasets: [{
                        label: 'Total Earnings (₹) per Month',
                        data: monthValues,
                        backgroundColor: 'rgba(15, 76, 129, 0.5)',
                        borderColor: 'rgba(15, 76, 129, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    scales: { y: { beginAtZero: true } }
                }
            });
        }
    </script>
</body>
</html>
"""

PATIENT_HISTORY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sai Health Care | Medical History</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #f3f4f6; }
        .bg-gradient { background-image: linear-gradient(135deg, #0f4c81 0%, #2980b9 100%); }
    </style>
</head>
<body class="flex flex-col min-h-screen">
    <header class="bg-gradient text-white p-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-4">
            <h1 class="text-2xl sm:text-3xl font-extrabold">SAI HEALTH CARE</h1>
            <span class="text-sm opacity-80 hidden sm:block">Medical History</span>
        </div>
        <a href="/logout" class="bg-white text-[#0f4c81] font-semibold py-2 px-4 rounded-full shadow-md transition-transform duration-200 hover:scale-105">Log Out</a>
    </header>
    <main class="flex-grow flex flex-col items-center p-6">
        <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-5xl mt-8">
            <h1 class="text-3xl font-bold text-center text-[#0f4c81] mb-2">Patient Medical History</h1>
            <p class="text-gray-600 text-center mb-8">Comprehensive record for **{{ patient.name }}** ({{ patient.patient_id }}).</p>

            <hr class="my-6 border-t-2 border-gray-200">

            <h2 class="text-2xl font-bold text-gray-800 mb-4">Prescription & Payment History ({{ history|length }} Records)</h2>
            <div class="space-y-6">
                {% if history %}
                    {% for record in history %}
                    <div class="bg-gray-50 p-6 rounded-xl shadow-md border-l-4 border-[#0f4c81]">
                        <div class="flex justify-between items-center border-b pb-2 mb-3">
                            <h3 class="text-xl font-semibold text-gray-800">Visit Date: {{ record.date }}</h3>
                            <span class="text-sm font-medium bg-indigo-100 text-indigo-800 px-3 py-1 rounded-full">Doctor: {{ record.doctor_name }}</span>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <p class="font-bold text-gray-700 mb-2">Prescription Details:</p>
                                <ul class="list-disc list-inside text-gray-600 ml-4 space-y-1">
                                    {% for item in record.medication %}
                                        <li>{{ item }}</li>
                                    {% endfor %}
                                </ul>
                                <p class="text-sm text-gray-500 mt-2">Notes: {{ record.notes }}</p>
                            </div>
                            <div>
                                <p class="font-bold text-gray-700 mb-2">Payment Status:</p>
                                <p class="text-lg font-bold {% if record.payment_status == 'pending' %} text-red-600 {% else %} text-green-600 {% endif %}">
                                    Status: {{ record.payment_status | capitalize }} (₹{{ record.amount }})
                                </p>
                                {% if record.payment_status == 'completed' %}
                                    <p class="text-sm text-gray-500">Paid via {{ record.payment.payment_method }} on {{ record.payment.timestamp }}</p>
                                {% else %}
                                    <a href="{{ url_for('payment', prescription_id=record._id) }}" class="text-sm text-red-500 hover:underline font-semibold mt-2 inline-block">Complete Payment Now</a>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="bg-yellow-100 p-6 rounded-xl shadow-md text-center">
                        <p class="text-yellow-700 font-semibold">No medical history records found for this patient.</p>
                    </div>
                {% endif %}
            </div>

            <div class="mt-8 text-center">
                <a href="/home" class="text-[#0f4c81] hover:underline font-semibold">Go back to Home</a>
            </div>
        </div>
    </main>
</body>
</html>
"""


# --- Routes ---

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
bcrypt = Bcrypt(app)

@app.route('/')
def root():
    return redirect(url_for('login_register'))

@app.route('/login_register', methods=['GET', 'POST'])
def login_register():
    global PATIENT_ID_COUNTER, DOCTOR_ID_COUNTER

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        email = request.form.get('email')
        
        if form_type == 'login':
            password = request.form.get('password')
            user_data = get_user(email)
            if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
                session['user_id'] = user_data['id']
                session['user_name'] = user_data['name']
                session['user_role'] = user_data['role']
                if user_data['role'] == 'patient':
                    return redirect(url_for('home'))
                elif user_data['role'] == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
            return "Login failed. Incorrect email or password."

        elif form_type == 'register':
            name = request.form.get('name')
            password = request.form.get('password')
            phone = request.form.get('phone')
            role = request.form.get('role')
            specialty = request.form.get('specialty') if role == 'doctor' else None

            if get_user(email):
                return "Registration failed. User with this email already exists."
            
            password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            
            user_data = {
                'id': email,
                'name': name,
                'email': email,
                'phone': phone,
                'password_hash': password_hash,
                'role': role,
                'specialty': specialty
            }

            session['pending_registration'] = user_data 
            
            if send_otp_via_twilio(phone):
                return redirect(url_for('confirm_otp_register'))
            else:
                session.pop('pending_registration', None)
                return "Registration failed. Could not send OTP. Check phone format (E.164: +CCNNNNNNNNN) or Twilio setup."

    return render_template_string(LOGIN_REGISTER_HTML)


@app.route('/confirm_otp_register', methods=['GET', 'POST'])
def confirm_otp_register():
    global PATIENT_ID_COUNTER, DOCTOR_ID_COUNTER
    
    user_data = session.get('pending_registration')
    if not user_data:
        return redirect(url_for('login_register'))

    phone_number = user_data['phone']

    if request.method == 'POST':
        user_otp = request.form.get('otp_code')
        
        if check_otp_via_twilio(phone_number, user_otp):
            if user_data['role'] == 'patient':
                patient_id = f"PAT-{PATIENT_ID_COUNTER}"
                PATIENT_ID_COUNTER += 1
                user_data.update({
                    'patient_id': patient_id,
                    'age': 'Not specified',
                    'gender': 'Not specified',
                    # Set default profile picture from the store
                    'profile_pic_url': PROFILE_PIC_CHOICES['default'] 
                })
            elif user_data['role'] == 'doctor':
                doctor_id = f"DOC-{DOCTOR_ID_COUNTER}"
                DOCTOR_ID_COUNTER += 1
                user_data.update({
                    'doctor_id': doctor_id,
                    'available': True,
                    'profile_pic_url': PROFILE_PIC_CHOICES['default']
                })

            save_user(user_data)
            print(f"User {user_data['name']} registered as {user_data['role']} after OTP verification.")

            session.pop('pending_registration', None)

            return redirect(url_for('login_register'))
        else:
            return render_template_string(OTP_REGISTER_HTML, phone_number=phone_number, error="Invalid OTP. Please try again.")

    return render_template_string(OTP_REGISTER_HTML, phone_number=phone_number)

@app.route('/home')
def home():
    if 'user_id' in session and session['user_role'] == 'patient':
        return render_template_string(HOME_HTML)
    return redirect(url_for('login_register'))

@app.route('/pending_payments')
def pending_payments():
    if 'user_id' in session and session['user_role'] == 'patient':
        user = get_user(session['user_id'])
        pending_prescriptions = get_pending_prescriptions_for_patient(user['patient_id'])
        return render_template_string(PENDING_PAYMENTS_HTML, prescriptions=pending_prescriptions)
    return redirect(url_for('login_register'))

@app.route('/profile')
def profile():
    if 'user_id' in session and session['user_role'] == 'patient':
        user = get_user(session['user_id'])
        user['age'] = user.get('age', 'Not specified')
        user['gender'] = user.get('gender', 'Not specified')
        # Ensure profile_pic_url is set, defaulting if missing
        user['profile_pic_url'] = user.get('profile_pic_url', PROFILE_PIC_CHOICES['default'])
        
        prescriptions = get_prescriptions_for_patient(user['patient_id'])
        
        # Pass the map of choices to the template
        return render_template_string(PROFILE_HTML, user=user, prescriptions=prescriptions, pic_choices=PROFILE_PIC_CHOICES)
    return redirect(url_for('login_register'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' in session and session['user_role'] == 'patient':
        user = get_user(session['user_id'])
        age = request.form.get('age')
        gender = request.form.get('gender')
        # Retrieve the selected URL from the dropdown
        profile_pic_url = request.form.get('profile_pic_url') 

        user['age'] = age
        user['gender'] = gender
        user['profile_pic_url'] = profile_pic_url # Update with selected URL

        if db:
            user_ref = db.collection('users').document(user['id'])
            user_ref.update({'age': age, 'gender': gender, 'profile_pic_url': profile_pic_url})
        
        return redirect(url_for('profile'))
    return "Error: Could not update profile."


@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' in session and session['user_role'] == 'patient':
        if request.method == 'POST':
            doctor_email = request.form.get('doctor_id')
            date = request.form.get('date')
            time = request.form.get('time')
            doctor = get_user(doctor_email)
            
            if doctor and doctor.get('available'):
                patient = get_user(session['user_id'])
                
                new_appointment = {
                    'patient_id': patient['patient_id'],
                    'doctor_id': doctor.get('doctor_id', doctor['id']),
                    'patient_name': patient['name'],
                    'date': date,
                    'time': time,
                    'status': 'Booked' # Status is set to 'Booked'
                }
                
                session['pending_appointment'] = new_appointment
                
                patient_phone = patient.get('phone')
                if patient_phone and send_otp_via_twilio(patient_phone):
                    return redirect(url_for('confirm_otp_appointment'))
                else:
                    session.pop('pending_appointment', None)
                    return "Appointment failed. Could not send OTP. Check your phone number format (E.164) or Twilio setup."
            
            return "Doctor is not available or not found."

        doctors = get_available_doctors()
        return render_template_string(APPOINTMENT_HTML, doctors=doctors)
    return redirect(url_for('login_register'))


@app.route('/confirm_otp_appointment', methods=['GET', 'POST'])
def confirm_otp_appointment():
    
    appointment_data = session.get('pending_appointment')
    if not appointment_data:
        return redirect(url_for('book_appointment'))

    patient = get_user(session['user_id']) 
    patient_phone = patient.get('phone')

    if request.method == 'POST':
        user_otp = request.form.get('otp_code')
        
        if patient_phone and check_otp_via_twilio(patient_phone, user_otp):
            save_appointment(appointment_data)
            print(f"Appointment confirmed and saved after OTP verification: {appointment_data}")

            session.pop('pending_appointment', None)
            
            return redirect(url_for('profile'))
        else:
            return render_template_string(OTP_APPOINTMENT_HTML, phone_number=patient_phone, error="Invalid OTP. Please try again.")

    return render_template_string(OTP_APPOINTMENT_HTML, phone_number=patient_phone)


@app.route('/payment', methods=['GET'])
def payment():
    if 'user_id' in session and session['user_role'] == 'patient':
        prescription_id = request.args.get('prescription_id')
        if not prescription_id:
            return redirect(url_for('pending_payments'))
        
        prescription = get_prescription_by_id(prescription_id)
        if not prescription:
            return "Error: Prescription not found."
            
        return render_template_string(PAYMENT_HTML, prescription=prescription)
    return redirect(url_for('login_register'))

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'user_id' in session and session['user_role'] == 'patient':
        patient = get_user(session['user_id'])
        prescription_id = request.form.get('prescription_id')
        amount = int(request.form.get('amount')) # Capture the variable amount
        payment_method = request.form.get('payment_method')
        
        prescription = get_prescription_by_id(prescription_id)
        if not prescription or prescription.get('amount') != amount: # Safety check
            return "Error: Prescription not found or amount mismatch."

        doctor_id = prescription.get('doctor_id')
        
        # NOTE: Appointment completion logic has been moved to /add_prescription.
        # This route only handles marking the payment status.

        payment_data = {
            'patient_id': patient['patient_id'],
            'patient_name': patient['name'],
            'amount': amount,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'doctor_id': doctor_id,
            'payment_method': payment_method,
            'status': 'Completed'
        }
        
        save_payment(payment_data)
        update_prescription_payment_status(prescription_id, 'completed')
        
        return redirect(url_for('payment_success', amount=amount)) # Pass amount to success page 
    return "Error: Could not process payment."

@app.route('/payment_success')
def payment_success():
    """Renders the payment successful confirmation page."""
    if 'user_id' in session and session['user_role'] == 'patient':
        # Safely retrieve the amount from URL args, defaulting if missing or invalid
        try:
            amount = int(request.args.get('amount', DEFAULT_PRESCRIPTION_FEE))
        except ValueError:
            amount = DEFAULT_PRESCRIPTION_FEE
            
        return render_template_string(PAYMENT_SUCCESS_HTML, datetime_now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount=amount)
    return redirect(url_for('login_register'))


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' in session and session['user_role'] == 'doctor':
        doctor = get_user(session['user_id'])
        doctor_id = doctor.get('doctor_id', doctor['id'])
        
        appointments = get_appointments_for_doctor(doctor_id)
        
        # Separate appointments into Booked and Completed
        appointments_booked = [a for a in appointments if a['status'] == 'Booked']
        appointments_completed = [a for a in appointments if a['status'] == 'Completed']
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_payments = get_payments_by_doctor_and_date(doctor_id, today)
        total_earnings = sum(p['amount'] for p in today_payments)

        # Build hourly earnings for today's chart (00-23)
        hourly_map = {f"{h:02d}": 0 for h in range(24)}
        for p in today_payments:
            try:
                hour = p['timestamp'].split(' ')[1].split(':')[0]
                hourly_map[hour] = hourly_map.get(hour, 0) + p.get('amount', 0)
            except Exception:
                pass
        today_chart_labels = list(hourly_map.keys())
        today_chart_values = [hourly_map[h] for h in today_chart_labels]

        stats = {
            'patients_assigned': len(get_patients_for_doctor(doctor_id)),
            'prescriptions_written': len(get_prescriptions_by_doctor(doctor_id)),
            'appointments_completed': len(appointments_completed), # Use the separated list
            'total_earnings': total_earnings
        }
        
        return render_template_string(
            DOCTOR_DASHBOARD_HTML,
            doctor=doctor,
            appointments_booked=appointments_booked, # Pass separated lists
            appointments_completed=appointments_completed, # Pass separated lists
            stats=stats,
            today_payments=today_payments,
            today_chart_labels=today_chart_labels,
            today_chart_values=today_chart_values,
            DEFAULT_PRESCRIPTION_FEE=DEFAULT_PRESCRIPTION_FEE
        )
    return redirect(url_for('login_register'))

@app.route('/doctor_monthly_stats')
def doctor_monthly_stats():
    if 'user_id' in session and session['user_role'] == 'doctor':
        doctor = get_user(session['user_id'])
        doctor_id = doctor.get('doctor_id', doctor['id'])
        
        # Get the aggregated monthly stats
        monthly_stats = get_monthly_payments_for_doctor(doctor_id)

        # Prepare chart arrays
        monthly_chart_labels = [s['month_year'] for s in monthly_stats]
        monthly_chart_values = [s['total_earnings'] for s in monthly_stats]
        
        return render_template_string(
            DOCTOR_MONTHLY_STATS_HTML,
            doctor=doctor,
            monthly_stats=monthly_stats,
            monthly_chart_labels=monthly_chart_labels,
            monthly_chart_values=monthly_chart_values
        )
    return redirect(url_for('login_register'))


@app.route('/toggle_availability', methods=['POST'])
def toggle_availability():
    if 'user_id' in session and session['user_role'] == 'doctor':
        doctor = get_user(session['user_id'])
        if doctor:
            new_availability = not doctor.get('available', True)
            doctor['available'] = new_availability
            if db:
                doc_ref = db.collection('users').document(doctor['id'])
                doc_ref.update({'available': new_availability})
            return redirect(url_for('doctor_dashboard'))
    return "Error: Could not toggle availability."


@app.route('/add_prescription', methods=['POST'])
def add_prescription():
    if 'user_id' in session and session['user_role'] == 'doctor':
        patient_id = request.form.get('patient_id')
        appointment_doc_id = request.form.get('appointment_doc_id') # New field
        medication_str = request.form.get('medication')
        notes = request.form.get('notes')
        
        # Safely convert fee to integer
        try:
            fee = int(request.form.get('fee', DEFAULT_PRESCRIPTION_FEE))
        except ValueError:
            fee = DEFAULT_PRESCRIPTION_FEE
            
        doctor = get_user(session['user_id'])
        doctor_id = doctor.get('doctor_id', doctor['id'])
        
        new_prescription = {
            'patient_id': patient_id,
            'doctor_id': doctor_id,
            'doctor_name': doctor['name'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'medication': [med.strip() for med in medication_str.split(',')],
            'notes': notes,
            'amount': fee, # Store the fee with the prescription
            'payment_status': 'pending'
        }
        
        save_prescription(new_prescription)
        
        # --- LOGIC SHIFT: Mark Appointment as Completed immediately upon writing Rx ---
        if appointment_doc_id:
            update_appointment_status_by_id(appointment_doc_id, 'Completed')
            print(f"Appointment {appointment_doc_id} marked as Completed by doctor's action (Prescription issued).")
        # --- END LOGIC SHIFT ---
        
        return redirect(url_for('doctor_dashboard'))
    return "Error: Could not add prescription."

@app.route('/patient_history')
def patient_history():
    if 'user_id' in session and session['user_role'] == 'patient':
        patient = get_user(session['user_id'])
        
        # Fetch detailed history
        history = get_full_patient_history(patient['patient_id'])
        
        return render_template_string(PATIENT_HISTORY_HTML, patient=patient, history=history)
    return redirect(url_for('login_register'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_register'))


# --- Database Helper Functions (UPDATED FOR APPOINTMENT STATUS BY ID) ---

def get_user(email):
    if db:
        user_ref = db.collection('users').document(email)
        doc = user_ref.get()
        if doc.exists:
            return doc.to_dict()
    for user in in_memory_db['users']:
        if user['email'] == email:
            return user
    return None

def save_user(user_data):
    if db:
        user_ref = db.collection('users').document(user_data['email'])
        data_to_save = user_data.copy()
        data_to_save.pop('specialty', None)
        user_ref.set(data_to_save)
        print(f"User {user_data['name']} saved to Firestore.")
    else:
        existing_index = next((i for i, user in enumerate(in_memory_db['users']) if user['email'] == user_data['email']), -1)
        if existing_index != -1:
            in_memory_db['users'][existing_index] = user_data
        else:
            if user_data['role'] == 'patient' and 'profile_pic_url' not in user_data:
                user_data['profile_pic_url'] = PROFILE_PIC_CHOICES['default']
            in_memory_db['users'].append(user_data)
        print(f"User {user_data['name']} saved to in-memory database.")

def get_doctor(doctor_id):
    if db:
        docs = db.collection('users').where('doctor_id', '==', doctor_id).where('role', '==', 'doctor').limit(1).stream()
        for doc in docs:
            return doc.to_dict()
    for user in in_memory_db['users']:
        if user.get('doctor_id') == doctor_id and user['role'] == 'doctor':
            return user
    return None

def get_available_doctors():
    if db:
        docs = db.collection('users').where('role', '==', 'doctor').where('available', '==', True).stream()
        return [doc.to_dict() for doc in docs]
    return [user for user in in_memory_db['users'] if user['role'] == 'doctor' and user.get('available') == True]

def get_appointments_for_doctor(doctor_id):
    if db:
        appointments = db.collection('appointments').where('doctor_id', '==', doctor_id).stream()
        # Include the document ID for update purposes
        return [{'_id': a.id, **a.to_dict()} for a in appointments]
    return [a for a in in_memory_db['appointments'] if a.get('doctor_id') == doctor_id]

def get_patients_for_doctor(doctor_id):
    appointments = get_appointments_for_doctor(doctor_id)
    patient_ids = {a['patient_id'] for a in appointments}
    
    patients = []
    for pid in patient_ids:
        if db:
            patient_docs = db.collection('users').where('patient_id', '==', pid).where('role', '==', 'patient').limit(1).stream()
            for doc in patient_docs:
                patients.append(doc.to_dict())
        else:
            for user in in_memory_db['users']:
                if user.get('patient_id') == pid and user['role'] == 'patient':
                    patients.append(user)
                    break
    return patients


def get_prescriptions_for_patient(patient_id):
    if db:
        docs = db.collection('prescriptions').where('patient_id', '==', patient_id).stream()
        # Ensure amount is an integer, default to 200 if missing
        return [{'_id': doc.id, 'amount': int(doc.to_dict().get('amount', DEFAULT_PRESCRIPTION_FEE)), **doc.to_dict()} for doc in docs]
    # Handle in-memory fallback
    return [{**p, 'amount': int(p.get('amount', DEFAULT_PRESCRIPTION_FEE))} for p in in_memory_db['prescriptions'] if p['patient_id'] == patient_id]

def get_pending_prescriptions_for_patient(patient_id):
    if db:
        docs = db.collection('prescriptions').where('patient_id', '==', patient_id).where('payment_status', '==', 'pending').stream()
        # Ensure amount is an integer, default to 200 if missing
        return [{'_id': doc.id, 'amount': int(doc.to_dict().get('amount', DEFAULT_PRESCRIPTION_FEE)), **doc.to_dict()} for doc in docs]
    # Handle in-memory fallback
    return [{**p, 'amount': int(p.get('amount', DEFAULT_PRESCRIPTION_FEE))} for p in in_memory_db['prescriptions'] if p['patient_id'] == patient_id and p.get('payment_status') == 'pending']
    
def get_prescription_by_id(prescription_id):
    if db:
        doc_ref = db.collection('prescriptions').document(prescription_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data['amount'] = int(data.get('amount', DEFAULT_PRESCRIPTION_FEE))
            return {'_id': doc.id, **data}
    for p in in_memory_db['prescriptions']:
        if p.get('_id') == prescription_id:
            p['amount'] = int(p.get('amount', DEFAULT_PRESCRIPTION_FEE))
            return p
    return None

def get_payments_for_prescription(prescription_id):
    if db:
        # For simplicity, we assume the first completed payment for the doctor on the prescription date is the correct one.
        prescription = get_prescription_by_id(prescription_id)
        if not prescription: return None
        
        docs = db.collection('payments')\
                 .where('patient_id', '==', prescription['patient_id'])\
                 .where('doctor_id', '==', prescription['doctor_id'])\
                 .where('date', '==', prescription['date'])\
                 .where('status', '==', 'Completed')\
                 .limit(1).stream()
        for doc in docs:
            return doc.to_dict()
    
    # In-memory lookup/mock
    prescription = get_prescription_by_id(prescription_id)
    if prescription and prescription.get('payment_status') == 'completed':
        for p in in_memory_db['payments']:
            if p.get('patient_id') == prescription['patient_id'] and \
               p.get('doctor_id') == prescription['doctor_id'] and \
               p.get('date') == prescription['date'] and \
               p.get('amount') == prescription['amount']:
                return p
        
        # Fallback Mock record
        return {
            'payment_method': 'Unknown (In-Memory)',
            'timestamp': prescription['date'] + ' 12:00:00',
            'amount': prescription['amount']
        }
    return None


def get_full_patient_history(patient_id):
    """Combines prescription data with payment data for history view."""
    prescriptions = get_prescriptions_for_patient(patient_id)
    history = []
    
    for p_data in prescriptions:
        # Fetch payment details only if payment status is completed
        if p_data.get('payment_status') == 'completed':
            payment_record = get_payments_for_prescription(p_data.get('_id'))
            p_data['payment'] = payment_record if payment_record else {'payment_method': 'N/A', 'timestamp': 'N/A'}
        else:
            p_data['payment'] = {'payment_method': 'N/A', 'timestamp': 'N/A'}
        
        history.append(p_data)
        
    # Sort history by date descending
    return sorted(history, key=lambda x: x['date'], reverse=True)


def update_prescription_payment_status(prescription_id, status):
    if db:
        doc_ref = db.collection('prescriptions').document(prescription_id)
        doc_ref.update({'payment_status': status})
    else:
        for p in in_memory_db['prescriptions']:
            if p.get('_id') == prescription_id:
                p['payment_status'] = status
                break

def get_prescriptions_by_doctor(doctor_id):
    if db:
        docs = db.collection('prescriptions').where('doctor_id', '==', doctor_id).stream()
        return [doc.to_dict() for doc in docs]
    return [p for p in in_memory_db['prescriptions'] if p['doctor_id'] == doctor_id]

def get_payments_by_doctor_and_date(doctor_id, date):
    if db:
        docs = db.collection('payments').where('doctor_id', '==', doctor_id).where('date', '==', date).stream()
        # Ensure amount is an integer
        return [{**doc.to_dict(), 'amount': int(doc.to_dict().get('amount', DEFAULT_PRESCRIPTION_FEE))} for doc in docs]
    # Handle in-memory fallback
    return [{**p, 'amount': int(p.get('amount', DEFAULT_PRESCRIPTION_FEE))} for p in in_memory_db['payments'] if p.get('doctor_id') == doctor_id and p.get('date') == date]

def get_monthly_payments_for_doctor(doctor_id):
    """Aggregates payments by month and year for a specific doctor."""
    monthly_summary = {}
    
    if db:
        docs = db.collection('payments').where('doctor_id', '==', doctor_id).stream()
        payments = [doc.to_dict() for doc in docs]
    else:
        payments = [p for p in in_memory_db['payments'] if p.get('doctor_id') == doctor_id]

    for payment in payments:
        amount = int(payment.get('amount', DEFAULT_PRESCRIPTION_FEE)) # Use stored or default amount
        date_obj = datetime.strptime(payment['date'], '%Y-%m-%d')
        month_year_key = date_obj.strftime('%Y-%m') 
        
        if month_year_key not in monthly_summary:
            monthly_summary[month_year_key] = {'count': 0, 'total_earnings': 0, 'month_year': month_year_key}
        
        monthly_summary[month_year_key]['count'] += 1
        monthly_summary[month_year_key]['total_earnings'] += amount
        
    sorted_stats = sorted(monthly_summary.values(), key=lambda x: x['month_year'], reverse=True)
    return sorted_stats


def save_appointment(appointment_data):
    if db:
        db.collection('appointments').add(appointment_data)
        print("Appointment saved to Firestore.")
    else:
        import uuid
        appointment_data['_id'] = str(uuid.uuid4())
        in_memory_db['appointments'].append(appointment_data)
        print("Appointment saved to in-memory database.")
        
# Helper function to update status just by ID (used by doctor when writing Rx)
def update_appointment_status_by_id(doc_id, status):
    """Updates the appointment status directly by its ID."""
    if db:
        doc_ref = db.collection('appointments').document(doc_id)
        doc_ref.update({'status': status})
    else:
        # For in-memory, we must find the object by the passed ID
        for a in in_memory_db['appointments']:
            if a.get('_id') == doc_id:
                a['status'] = status
                print(f"In-memory appointment {doc_id} updated to {status}.")
                return
    
def find_appointment_by_patient_and_doctor(patient_id, doctor_id):
    """Finds a 'Booked' appointment by patient and doctor ID. Returns (doc_id, appointment_data)"""
    if db:
        # NOTE: This complex query REQUIRES a composite index in Firestore.
        appointments = db.collection('appointments')\
                             .where('patient_id', '==', patient_id)\
                             .where('doctor_id', '==', doctor_id)\
                             .where('status', '==', 'Booked')\
                             .order_by('date', direction=firestore.Query.DESCENDING)\
                             .order_by('time', direction=firestore.Query.DESCENDING)\
                             .limit(1).stream()
        
        for doc in appointments:
            return doc.id, doc.to_dict()
    
    # In-memory lookup
    for a in reversed(in_memory_db['appointments']):
        if a.get('patient_id') == patient_id and a.get('doctor_id') == doctor_id and a.get('status') == 'Booked':
            return a.get('_id'), a 
    return None, None

# This function is now OBSOLETE but kept for backwards compatibility with payment process.
def update_appointment_status(doc_id, appointment_data, status):
    """Updates the appointment status in database or memory. (Deprecated: use update_appointment_status_by_id)"""
    if db and doc_id:
        doc_ref = db.collection('appointments').document(doc_id)
        doc_ref.update({'status': status})
    elif appointment_data:
        appointment_data['status'] = status
        print(f"In-memory appointment updated to {status}.")


def save_prescription(prescription_data):
    if db:
        doc_ref = db.collection('prescriptions').document()
        doc_ref.set(prescription_data)
        print("Prescription saved to Firestore.")
    else:
        import uuid
        prescription_data['_id'] = str(uuid.uuid4())
        # Ensure 'amount' is set, default if missing
        prescription_data['amount'] = int(prescription_data.get('amount', DEFAULT_PRESCRIPTION_FEE)) 
        in_memory_db['prescriptions'].append(prescription_data)
        print("Prescription saved to in-memory database.")

def save_payment(payment_data):
    if db:
        db.collection('payments').add(payment_data)
        print("Payment saved to Firestore.")
    else:
        in_memory_db['payments'].append(payment_data)
        print("Payment saved to in-memory database.")

@app.route('/export_monthly_stats', methods=['GET'])
def export_monthly_stats():
    """Export the logged-in doctor's monthly stats as CSV without external deps."""
    if 'user_id' not in session or session['user_role'] != 'doctor':
        return redirect(url_for('login_register'))

    doctor = get_user(session['user_id'])
    doctor_id = doctor.get('doctor_id', doctor['id'])
    monthly_stats = get_monthly_payments_for_doctor(doctor_id)

    # Build CSV content
    lines = ["month_year,year,month,count,total_earnings"]
    for s in monthly_stats:
        year, month = s['month_year'].split('-')
        lines.append(f"{s['month_year']},{year},{month},{s['count']},{s['total_earnings']}")
    csv_data = "\n".join(lines)

    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=monthly_earnings.csv'
    return response

# --- Running the application ---
if __name__ == '__main__':
    if not in_memory_db['users']:
        # Mock Patient 
        patient_hash = bcrypt.generate_password_hash('password').decode('utf-8')
        in_memory_db['users'].append({
            'id': 'patient@example.com',
            'name': 'Patient User',
            'email': 'patient@example.com',
            'phone': '+15551234567',
            'password_hash': patient_hash,
            'role': 'patient',
            'patient_id': 'PAT-1000',
            'age': 35,
            'gender': 'Male',
            'profile_pic_url': PROFILE_PIC_CHOICES['avatar_1'] # Initial profile pic from store
        })
        # Mock Doctors
        in_memory_db['users'].append({
            'id': 'jane.smith@example.com',
            'email': 'jane.smith@example.com',
            'name': 'Dr. Jane Smith',
            'specialty': 'Cardiology',
            'available': True,
            'phone': '+15557654321',
            'password_hash': bcrypt.generate_password_hash('password').decode('utf-8'),
            'role': 'doctor',
            'doctor_id': 'DOC-2000',
            'profile_pic_url': PROFILE_PIC_CHOICES['default']
        })
        in_memory_db['users'].append({
            'id': 'alan.turing@example.com',
            'email': 'alan.turing@example.com',
            'name': 'Dr. Alan Turing',
            'specialty': 'Neurology',
            'available': False,
            'phone': '+15551112222',
            'password_hash': bcrypt.generate_password_hash('password').decode('utf-8'),
            'role': 'doctor',
            'doctor_id': 'DOC-2001',
            'profile_pic_url': PROFILE_PIC_CHOICES['default']
        })
        PATIENT_ID_COUNTER = 1001
        DOCTOR_ID_COUNTER = 2002
        
        # Add a mock prescription for PAT-1000
        import uuid
        in_memory_db['prescriptions'].append({
            '_id': str(uuid.uuid4()),
            'patient_id': 'PAT-1000',
            'doctor_id': 'DOC-2000',
            'doctor_name': 'Dr. Jane Smith',
            'date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'), 
            'medication': ['Ibuprofen 400mg', 'Amoxicillin 500mg'],
            'notes': 'Flu symptoms, take rest.',
            'amount': 250, 
            'payment_status': 'pending'
        })
        in_memory_db['prescriptions'].append({
            '_id': str(uuid.uuid4()),
            'patient_id': 'PAT-1000',
            'doctor_id': 'DOC-2000',
            'doctor_name': 'Dr. Jane Smith',
            'date': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'), 
            'medication': ['Paracetamol 500mg'],
            'notes': 'Minor headache, stay hydrated.',
            'amount': 150, 
            'payment_status': 'completed'
        })
        # Add a mock payment for the completed prescription
        in_memory_db['payments'].append({
            'patient_id': 'PAT-1000',
            'patient_name': 'Patient User',
            'amount': 150,
            'timestamp': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d 10:30:00'),
            'date': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'),
            'doctor_id': 'DOC-2000',
            'payment_method': 'Card',
            'status': 'Completed'
        })
        # Add a booked appointment for PAT-1000
        in_memory_db['appointments'].append({
            '_id': str(uuid.uuid4()),
            'patient_id': 'PAT-1000',
            'doctor_id': 'DOC-2000',
            'patient_name': 'Patient User',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': '16:00',
            'status': 'Booked' 
        })
        
    app.run(debug=True)