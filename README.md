# Hospital-system
This hospital management system is a Flask-based app with Firebase and Twilio. It enables secure patient registration, appointment booking, prescription management, and payments. Doctors manage appointments and earnings. The app uses OTP for security and provides an efficient, user-friendly healthcare platform.
# Hospital Management System

This web application is a full-featured Hospital Management System developed using Flask as the backend framework, Firebase Firestore as the cloud database, and Twilio API for sending OTP verification messages securely. The main goal is to digitize and streamline hospital workflows for both patients and doctors.

## Features

- **Patient Functions**: Patients can register securely, log in, update profiles, book and view appointments, and manage prescription payments.
- **Doctor Functions**: Doctors get a dashboard with monthly appointment and payment statistics. They can update availability, write prescriptions, track appointments, and export earnings.
- **OTP Verification**: User authentication and sensitive actions are secured via OTPs sent through the Twilio Verify API.
- **Data Storage**: All patient, doctor, appointment, prescription, and payment data are stored and managed in Firebase Firestore.
- **Modern UI**: The interface uses Tailwind CSS for responsive, clean, and interactive pages including login, OTP input, appointments, and payments.
- **Security**: Role-based access controls ensure patients and doctors see only their relevant data.

## Setup and Installation

1. Clone this repository to your local machine.
2. Install required dependencies using:
3. Place the Firebase service account JSON file into the project directory.
4. Configure the `hospitalapp.py` file with your Firebase project details.
5. Update the Twilio API keys in the relevant section of the code:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
6. Run the Flask application with:
7. Open your browser to `http://localhost:5000` to start using the system.

## OTP Functionality Customization

The project uses Twilio’s Verify API for OTP functionality. If you want to enable or customize OTPs for user verification or appointment confirmation:

- Sign up and create a Twilio account.
- Get your Account SID, Auth Token, and Verify Service SID.
- Replace the existing API keys in the code with your own credentials.
- This ensures secure and reliable OTP sending to users' phone numbers.

## License

This project is open source for educational and development use.

---

For further questions or customizations, feel free to open an issue or contact the maintainer.
