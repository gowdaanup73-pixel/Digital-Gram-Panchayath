<div align="center">
  <h1>🏛️ Digital Gram Panchayath</h1>
  <p>A comprehensive digital governance platform empowering local rural administration with digital services and grievance redressal.</p>

  [![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
  [![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

  <h3>🚀 <a href="https://digital-grampanchayath.vercel.app/"><b>Live Demo (Vercel)</b></a> 🚀</h3>
</div>

---

## 📖 Overview

The **Digital Gram Panchayath** is an e-governance portal designed to bridge the digital divide in rural areas. It streamlines administrative workflows, allowing citizens to easily apply for services and submit complaints—all from a unified dashboard.

## 🌟 Key Features

### 1. 📝 Digital Services & Schemes
- Citizens can browse and apply for government schemes (e.g., Building Construction, Skill Equipment, Bio-Gas Plant).
- Application tracking via the User Dashboard.
- Admin dashboard to review, approve, or reject applications with feedback.

### 2. 📢 Grievance Redressal (Complaint Management)
- Submit geo-tagged and categorized complaints.
- Real-time status tracking (Pending → In Progress → Resolved).
- Admin dashboard to efficiently manage and update complaint statuses.

### 3. 👤 User & Admin Dashboards
- Secure authentication with role-based access control (Citizen vs. Officer/Admin).
- Personalized citizen profiles and application history.

### 4. 🗳️ Democratic Election System (Work in Progress)
- *Note: This module is actively under development.*
- **Admin Controls**: Create voting sessions, define terms, and approve candidates.
- **Candidate Registration**: Citizens can apply for candidacy with custom display names.
- **Elected Officials Directory**: Public page detailing the current elected members, their term dates, and roles.

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/gowdaanup73-pixel/Digital-Gram-Panchayath.git
   cd Digital-Gram-Panchayath
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Database Migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a Superuser (Admin)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000` in your browser.

## 📁 Project Structure

```text
├── core/                   # Main Django application
│   ├── models.py           # Database schema (User, Complaints, etc.)
│   ├── views.py            # Citizen-facing logic
│   └── templates/          # HTML templates
├── digital_gram_panchayat/ # Django project configuration
├── static/                 # CSS, JS, and Images
├── media/                  # User uploads
└── manage.py               # Django execution script
```

## 🛠️ Built With

* **Backend**: Django 5.2, Python 3.11+
* **Database**: SQLite (Development) / PostgreSQL (Production ready)
* **Frontend**: HTML5, CSS3, JavaScript, Bootstrap

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
