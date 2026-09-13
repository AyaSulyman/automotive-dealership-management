# AutoSource ADMS

**AutoSource ADMS (Automotive Dealership Management System)** is a web-based dealership management platform designed to streamline vehicle inventory, customers, sales, trade-ins, payments, financing, and financial reporting in one centralized system.

The project is structured as two Django applications:

* **Backend** — Django REST Framework API responsible for business logic, database persistence, authentication, sales, payments, inventory, customers, and reporting.
* **Frontend** — Django server-rendered application that provides the dealership employee portal and communicates with the backend through REST APIs.

---

## Features

### Authentication & User Management

* Employee authentication
* JWT-based authentication
* Access and refresh tokens
* Logout
* Current-user information
* User management
* Role management

### Inventory & Procurement

* Vehicle management
* Vehicle media/images
* Vehicle valuation
* Vendor management
* Purchase orders
* Vehicle documents
* Document download and deletion

### Customer Management

* Customer creation and management
* Customer details
* Customer history
* Customer balance
* Customer statements

### Sales & Deal Management

* Customer and vehicle selection
* Deal worksheet
* Trade-ins
* Trade-in credit application
* Tax rules
* Sales invoices
* Invoice drafts
* Invoice finalization
* Invoice discounts
* Invoice cancellation
* Invoice PDF generation

### Payments & Financing

* Payment management
* Payment receipts
* Payment schedules
* Financing accounts
* Generate payment schedules
* Customer statements
* Payment export

### Reports & Dashboard

* Dashboard overview
* Recent invoices
* Recent payments
* Finance overview
* Vehicle financial summaries
* Audit logs

### AI-Powered Features

* AI Text Polisher for rewriting customer feedback and vehicle descriptions professionally
* Integration with Google Generative AI (Gemini 1.5 Flash)
* Dedicated UI assistant accessible via the dealership sidebar
* Isolated REST endpoint for prompt-engineered text refinement

### API Documentation

The backend uses **drf-spectacular** to provide OpenAPI documentation.

Available documentation:

* Swagger UI: `/api/v1/docs`
* OpenAPI Schema: `/api/v1/schema`
* ReDoc: `/api/v1/redoc`

---

## Project Structure

```text
automotive-dealership-management/
│
├── backend/
│   ├── accounts/
│   ├── customers/
│   ├── inventory/
│   ├── payments/
│   ├── reports/
│   ├── sales/
│   ├── config/
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/
│   ├── config/
│   ├── inventory/
│   ├── crm_finance/
│   ├── services/
│   ├── templates/
│   ├── static/
│   ├── manage.py
│   └── requirements.txt
│
└── README.md

Technology Stack
Backend
Python

Django 6.1

Django REST Framework

Simple JWT

PostgreSQL

Psycopg

Django CORS Headers

Django Filter

drf-spectacular

ReportLab

google-generativeai

python-dotenv

Frontend
Python

Django 6.1

Django Templates

HTML/CSS

JavaScript

Requests

python-dotenv

Database
The backend is designed to use PostgreSQL.

The frontend does not own the dealership business data. It communicates with the backend through REST APIs.

Installation
Prerequisites
Make sure the following are installed:

Python 3.13+

Git

PostgreSQL or a configured PostgreSQL-compatible database

pip

Virtual environment support

Backend Setup
Open a terminal and navigate to the backend:

PowerShell


cd backend
Create a virtual environment if one does not already exist:

PowerShell


python -m venv venv
Activate it on Windows:

PowerShell


.\venv\Scripts\Activate.ps1
Install dependencies:

PowerShell


python -m pip install --upgrade pip
pip install -r requirements.txt
Configure the backend environment variables in:

Plaintext


backend/.env
Example:

Code snippet


DB_NAME=postgres
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432

SECRET_KEY=your_secret_key
GEMINI_API_KEY=your_gemini_api_key
Run migrations:

PowerShell


python manage.py migrate
Check the project:

PowerShell


python manage.py check
Start the backend:

PowerShell


python manage.py runserver 8001
The backend will be available at:

Plaintext


[http://127.0.0.1:8001/](http://127.0.0.1:8001/)
API base URL:

Plaintext


[http://127.0.0.1:8001/api/v1/](http://127.0.0.1:8001/api/v1/)
Frontend Setup
Open a second terminal:

PowerShell


cd frontend
Install dependencies:

PowerShell


pip install -r requirements.txt
Configure the frontend environment in:

Plaintext


frontend/.env
Example:

Code snippet


ADMS_API_BASE_URL=[http://127.0.0.1:8001/api/v1](http://127.0.0.1:8001/api/v1)
ADMS_API_TIMEOUT=10

FRONTEND_SECRET_KEY=your_frontend_secret_key
FRONTEND_DEBUG=true
FRONTEND_ALLOWED_HOSTS=127.0.0.1,localhost
Run frontend migrations:

PowerShell


python manage.py migrate
Check the project:

PowerShell


python manage.py check
Start the frontend:

PowerShell


python manage.py runserver 8000
The employee portal will be available at:

Plaintext


[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
Running the Complete System
The backend and frontend should run simultaneously.

Terminal 1 — Backend
PowerShell


cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver 8001
Terminal 2 — Frontend
PowerShell


cd frontend
python manage.py runserver 8000
The architecture is:

Plaintext


                  ┌─────────────────────┐
                  │    ADMS Frontend    │
                  │     Django UI       │
                  │     Port 8000       │
                  └──────────┬──────────┘
                             │
                             │ REST API
                             ▼
                  ┌─────────────────────┐
                  │    ADMS Backend     │
                  │ Django REST API     │
                  │     Port 8001       │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │     PostgreSQL      │
                  │      Database       │
                  └─────────────────────┘
API Modules
The backend API is organized into the following modules.

Authentication
Plaintext


POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
Users & Roles
Plaintext


GET/POST /api/v1/users
GET      /api/v1/users/{id}
GET      /api/v1/roles
Inventory
Plaintext


GET/POST /api/v1/vehicles
GET      /api/v1/vehicles/{id}

GET/POST /api/v1/vendors
GET      /api/v1/vendors/{id}

GET/POST /api/v1/purchase-orders
GET      /api/v1/purchase-orders/{id}

GET/POST /api/v1/documents
DELETE   /api/v1/documents/{id}
GET      /api/v1/documents/{id}/download
Vehicle-related functionality also includes:

Plaintext


/api/v1/vehicles/{id}/media
/api/v1/vehicles/{id}/valuation
Customers
Plaintext


GET/POST /api/v1/customers
GET      /api/v1/customers/{id}
GET      /api/v1/customers/{id}/history
GET      /api/v1/customers/{id}/balance
GET      /api/v1/customers/{id}/statement
Sales
Plaintext


/api/v1/sales/customer-options
/api/v1/sales/vehicle-options
/api/v1/sales/deal-worksheet
/api/v1/trade-ins
/api/v1/tax-rules
/api/v1/sales-invoices
Sales invoices support draft saving, finalization, discounts, PDF generation, and cancellation.

Artificial Intelligence (AI)
Plaintext


POST /api/v1/ai/polish-feedback/
Provides automated grammar correction, stylistic enhancement, and tone polishing for customer communication drafts and inventory descriptions using Google Gemini.

Payments & Financing
Plaintext


/api/v1/payments
/api/v1/payment-schedules
/api/v1/financing-accounts
/api/v1/statements
The payment module also supports payment receipts, payment exports, statement generation, and payment schedule generation.

Reports
Plaintext


/api/v1/dashboard/overview
/api/v1/dashboard/recent-invoices
/api/v1/dashboard/recent-payments
/api/v1/reports/finance/overview
/api/v1/reports/vehicle-financial-summary
/api/v1/audit-log
API Documentation
After starting the backend, open:

Swagger
Plaintext


[http://127.0.0.1:8001/api/v1/docs](http://127.0.0.1:8001/api/v1/docs)
OpenAPI Schema
Plaintext


[http://127.0.0.1:8001/api/v1/schema](http://127.0.0.1:8001/api/v1/schema)
ReDoc
Plaintext


[http://127.0.0.1:8001/api/v1/redoc](http://127.0.0.1:8001/api/v1/redoc)
Swagger provides an interactive interface for testing the available REST API endpoints.

Environment Variables
Do not commit real passwords, API keys, secret keys, or database credentials to Git.

Use .env files locally and keep them excluded through .gitignore.

Example frontend configuration:

Code snippet


ADMS_API_BASE_URL=[http://127.0.0.1:8001/api/v1](http://127.0.0.1:8001/api/v1)
ADMS_API_TIMEOUT=10
FRONTEND_SECRET_KEY=your_secret_key
FRONTEND_DEBUG=true
FRONTEND_ALLOWED_HOSTS=127.0.0.1,localhost
Example backend configuration:

Code snippet


DB_NAME=postgres
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432
SECRET_KEY=your_secret_key
GEMINI_API_KEY=your_gemini_api_key
Development Workflow
Start the PostgreSQL database.

Start the backend on port 8001.

Start the frontend on port 8000.

Open the frontend employee portal.

Use Swagger to test backend APIs independently when needed.

Check Django logs in the corresponding terminal when debugging API or UI issues.

Troubleshooting
Backend API returns 404
Make sure the backend is running from the backend directory:

PowerShell


cd backend
python manage.py runserver 8001
Do not run the frontend Django application on port 8001.

Swagger returns 404
Verify that the backend is running and that the URL is:

Plaintext


[http://127.0.0.1:8001/api/v1/docs](http://127.0.0.1:8001/api/v1/docs)
Frontend cannot connect to backend
Check:

Code snippet


ADMS_API_BASE_URL=[http://127.0.0.1:8001/api/v1](http://127.0.0.1:8001/api/v1)
Then restart the frontend server.

Missing Python package
Install project dependencies:

PowerShell


pip install -r requirements.txt
Database migration errors
Run:

PowerShell


python manage.py check
python manage.py showmigrations
python manage.py migrate
Security
For development, environment variables may be stored in local .env files.

For production:

Use strong secret keys.

Never commit .env files containing credentials.

Use HTTPS.

Configure allowed hosts correctly.

Restrict database access.

Use production-grade Django deployment settings.

Disable DEBUG.

Rotate credentials if they are accidentally exposed.

Project Status
The system contains integrated modules for:

Authentication

User and role management

Inventory

Vendors

Purchase orders

Vehicles

Customers

Sales

Trade-ins

Sales invoices

Payments

Financing

Statements

Dashboard reporting

Financial reporting

Audit logging

AI-Powered Text Enhancement

API documentation

The frontend and backend are designed to operate as separate Django applications communicating through REST APIs.

License
This project is intended for dealership management and internal/project use.

Add the appropriate license here if the project will be distributed publicly.