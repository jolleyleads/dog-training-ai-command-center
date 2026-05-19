# Dog Training AI Lead Intelligence & Client Booking Command Center

## What This App Does

This is an AI Client Intake, Lead Qualification, and Booking Automation system for dog trainers.

It helps dog training companies capture leads, qualify dog owners, identify behavior issues, score urgency, recommend programs, draft outreach, track projected revenue, and book consultations.

## Features

- Dog training lead intake dashboard
- Owner and dog profile fields
- Behavior issue tracking
- Service interest tracking
- Lead scoring
- Priority ranking
- Seeded demo dog training leads
- AI summary generation
- Rule-based fallback if OpenAI is not configured
- Gmail-ready drafts
- SMS draft generation
- Consultation booking messages
- Follow-up drafts
- Revenue tracking
- Projected revenue calculation
- Make.com webhook support
- Google Sheets sync payload support
- Bulk lead import endpoint
- Login foundation
- Render-safe deployment

## API Endpoints

GET /api/health  
GET /api/leads  
GET /api/lead-source-template  
POST /api/add-lead  
POST /api/import-leads  
POST /api/outreach/<lead_id>  
POST /api/gmail-draft/<lead_id>  
POST /api/sheets-sync/<lead_id>  
POST /api/update-lead  
POST /api/regenerate-summary/<lead_id>  

## Environment Variables

Required:
PYTHON_VERSION = 3.11.9

Optional:
BOOKING_LINK = your Calendly or booking link  
MAKE_WEBHOOK_URL = Make.com webhook for Google Sheets / CRM sync  
OPENAI_API_KEY = optional OpenAI summaries  
ADMIN_USERNAME = dashboard login username  
ADMIN_PASSWORD = dashboard login password  
SECRET_KEY = Flask session secret  
DATABASE_URL = optional external Postgres database  

If ADMIN_USERNAME and ADMIN_PASSWORD are not set, the app runs in demo mode.

If OPENAI_API_KEY is not set, the app uses rule-based summaries.

## Render Deployment

Build command:
pip install -r requirements.txt

Start command:
gunicorn app:app

Root directory:
leave blank

Branch:
main

## Business Value

Dog trainers lose leads when inquiries are not followed up with quickly, behavior issues are not qualified properly, and owners are not guided into the right program.

This app helps dog trainers:
- respond faster
- qualify serious dog owners
- prioritize urgent cases
- identify high-ticket program opportunities
- book more consultations
- track projected revenue
- automate follow-up workflows

## Pricing Recommendation

Small dog trainer:
$1,500-$3,000 setup plus $297-$750/month

Established dog training company:
$3,500-$7,500 setup plus $750-$1,500/month

High-volume dog training company:
$10,000+ setup plus $2,000+/month depending on integrations, ads, CRM, SMS, call handling, and automation depth.

## Positioning Statement

AI Client Intake, Lead Qualification & Booking Automation for Dog Trainers.
