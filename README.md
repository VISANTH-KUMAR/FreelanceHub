# FreelanceHub

**FreelanceHub** is a web-based freelancing platform built with Flask and Python. It provides a place for clients to post projects and freelancers to showcase services, discover opportunities, and submit proposals.

## 🚀 Features

- **User Authentication:** Register and log in to the platform.
- **Role-Based Accounts:** Supports client and freelancer accounts.
- **Service Listings:** Freelancers can publish their services.
- **Project Management:** Clients can create and manage projects.
- **Proposal System:** Freelancers can submit proposals for projects.
- **Dashboard:** Access relevant project and service information.
- **Database Integration:** Uses SQLite to store application data.
- **Responsive Interface:** Uses HTML, CSS, and JavaScript for the user interface.

## 🛠️ Technologies Used

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** SQLite
- **Version Control:** Git and GitHub

## 📋 Prerequisites

Before running FreelanceHub, install:

- Python 3
- Git (optional, but recommended)
- A code editor such as Visual Studio Code

## ⚙️ Installation and Setup

Follow these steps to run the project on your local computer.

### 1. Clone the repository

Open a terminal and run:

git clone https://github.com/VISANTH-KUMAR/FreelanceHub.git


Navigate to the project directory:

cd FreelanceHub

### 2. Create a virtual environment

On Windows:

python -m venv venv

Activate it using PowerShell:

.\venv\Scripts\Activate.ps1

If you use Command Prompt instead:

venv\Scripts\activate.bat

### 3. Install dependencies

Install the required Python packages:

python -m pip install -r requirements.txt


### 4. Run the application

Start the Flask application:

python app.py

If the application is configured to use Flask's development server, open your browser and visit:

http://127.0.0.1:5000

If the application uses a different port, use the address printed in your terminal.

### 6. Start using FreelanceHub

1. Register for an account.
2. Choose the appropriate account type.
3. Log in.
4. Explore the available services and projects.
5. Use the features available to your account type.

## 📁 Project Structure

FreelanceHub/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── services.html
│   ├── service_detail.html
│   ├── add_service.html
│   ├── projects.html
│   ├── create_project.html
│   ├── project_detail.html
│   ├── my_projects.html
│   ├── my_proposals.html
│   └── 404.html
│
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── main.js

- `app.py` — Flask application and backend routes.
- `requirements.txt` — Python dependencies.
- `templates/` — HTML templates.
- `static/css/` — Stylesheets.
- `static/js/` — JavaScript files.

The application may create its SQLite database automatically when it starts, depending on its database initialization code.

## 🔒 Security Notes

- Do not commit passwords, API keys, or secret keys.
- Do not publish databases containing real users' personal information.
- Use environment variables for sensitive configuration.
- Use a production-ready server and appropriate security settings when deploying publicly.

## ⚠️ Development Status

FreelanceHub is a project for learning and developing a freelancing marketplace. Test its features before using it with real users.

## 👨‍💻 Author

**Myla Visanth Kumar**

B.Tech — Computer Science and Engineering

## 📄 License

This project is available for learning and demonstration purposes. No specific open-source license has been assigned yet.