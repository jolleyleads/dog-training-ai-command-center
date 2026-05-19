from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import hashlib
import os
import requests

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "demo-secret-key-change-in-production")

db_url = os.getenv("DATABASE_URL", "sqlite:///dog_training_command_center.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url.replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

BOOKING_LINK = os.getenv("BOOKING_LINK", "https://calendly.com/your-dog-training-company/consultation")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

HIGH_INTENT_SIGNALS = [
    "aggression", "aggressive", "biting", "bite", "reactive", "separation anxiety",
    "board and train", "ready to book", "urgent", "failed previous trainer",
    "multiple dogs", "private lessons", "behavior issue", "fearful", "resource guarding"
]

MEDIUM_INTENT_SIGNALS = [
    "puppy training", "leash pulling", "obedience", "jumping", "barking",
    "crate training", "recall", "basic commands", "socialization", "house training"
]

HIGH_TICKET_SERVICES = [
    "board and train", "private lessons", "behavior modification",
    "aggression rehab", "reactivity program", "in-home training"
]

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(120), unique=True)
    owner_name = db.Column(db.String(200))
    dog_name = db.Column(db.String(200))
    dog_breed = db.Column(db.String(200))
    dog_age = db.Column(db.String(100))
    behavior_issue = db.Column(db.Text)
    service_interest = db.Column(db.String(200))
    urgency = db.Column(db.String(100))
    phone = db.Column(db.String(100))
    email = db.Column(db.String(200))
    city = db.Column(db.String(120))
    state = db.Column(db.String(80))
    source = db.Column(db.String(200))
    notes = db.Column(db.Text)
    score = db.Column(db.Integer)
    priority = db.Column(db.String(80))
    ai_summary = db.Column(db.Text)
    recommended_program = db.Column(db.Text)
    next_best_action = db.Column(db.Text)
    estimated_program_value = db.Column(db.Float, default=0)
    probability_to_close = db.Column(db.Float, default=0.25)
    projected_revenue = db.Column(db.Float, default=0)
    status = db.Column(db.String(100), default="New")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Outreach(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.String(120))
    channel = db.Column(db.String(50))
    subject = db.Column(db.String(300))
    message = db.Column(db.Text)
    status = db.Column(db.String(80), default="drafted")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            return f(*args, **kwargs)
        if session.get("logged_in"):
            return f(*args, **kwargs)
        return redirect(url_for("login"))
    return wrapper

def make_lead_id(owner_name, dog_name, phone, email):
    raw = f"{owner_name}|{dog_name}|{phone}|{email}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def calc_projected_revenue(value, probability):
    try:
        return round(float(value or 0) * float(probability or 0.25), 2)
    except Exception:
        return 0

def score_dog_training_lead(behavior_issue, service_interest, notes, dog_breed="", urgency=""):
    text = f"{behavior_issue} {service_interest} {notes} {dog_breed} {urgency}".lower()
    score = 10
    reasons = []

    for item in HIGH_INTENT_SIGNALS:
        if item in text:
            score += 14
            reasons.append(f"High-intent training signal: {item}")

    for item in MEDIUM_INTENT_SIGNALS:
        if item in text:
            score += 7
            reasons.append(f"Training need detected: {item}")

    for item in HIGH_TICKET_SERVICES:
        if item in text:
            score += 16
            reasons.append(f"High-ticket service interest: {item}")

    if any(x in text for x in ["aggression", "aggressive", "biting", "reactive", "resource guarding"]):
        score += 18
        reasons.append("Urgent behavior modification opportunity")

    if any(x in text for x in ["ready to book", "asap", "urgent", "today", "this week"]):
        score += 15
        reasons.append("High booking urgency")

    if "multiple dogs" in text or "two dogs" in text or "3 dogs" in text:
        score += 10
        reasons.append("Multiple-dog household increases program value")

    score = min(score, 100)

    if score >= 75:
        priority = "High"
        program = "Recommend consultation plus high-ticket program such as private lessons, behavior modification, or board-and-train."
        action = "Contact immediately, offer consultation, and send booking link."
    elif score >= 45:
        priority = "Medium"
        program = "Recommend structured obedience, puppy training, or private lesson package."
        action = "Follow up with educational message and consultation invitation."
    else:
        priority = "Low"
        program = "Recommend nurture sequence, basic training resources, and future consultation."
        action = "Add to nurture list and follow up later."

    summary = "; ".join(reasons) if reasons else "No strong urgent training signal detected yet."
    return score, priority, summary, program, action

def fallback_summary(lead):
    return (
        f"{lead.owner_name} is interested in dog training for {lead.dog_name or 'their dog'}. "
        f"The main issue is {lead.behavior_issue or 'general training needs'}. "
        f"Recommended program: {lead.recommended_program}. "
        f"Projected revenue opportunity: ${lead.projected_revenue:,.0f}. "
        f"Next best action: {lead.next_best_action}."
    )

def ai_summary_for_lead(lead):
    if not OPENAI_API_KEY:
        return fallback_summary(lead)

    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You summarize dog training sales leads for a dog training company CRM."},
                {"role": "user", "content": f"Owner: {lead.owner_name}\nDog: {lead.dog_name}\nBreed: {lead.dog_breed}\nAge: {lead.dog_age}\nBehavior issue: {lead.behavior_issue}\nService interest: {lead.service_interest}\nUrgency: {lead.urgency}\nNotes: {lead.notes}\nScore: {lead.score}\nPriority: {lead.priority}\nProjected revenue: {lead.projected_revenue}\nWrite a concise sales intelligence summary."}
            ],
            "temperature": 0.4
        }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return fallback_summary(lead)

def build_messages(lead):
    subject = f"Dog training consultation for {lead.dog_name or 'your dog'}"

    email = f"""Hi {lead.owner_name or 'there'},

Thanks for reaching out about training for {lead.dog_name or 'your dog'}.

Based on what you shared, the main training need appears to be:
{lead.behavior_issue or 'general behavior and obedience support'}

The program I would recommend starting with:
{lead.recommended_program}

The next best step is a quick consultation so we can understand the behavior, your goals, your home routine, and the best training path.

You can book here:
{BOOKING_LINK}

After that, we can recommend the right option, whether that is puppy training, private lessons, behavior modification, obedience, or board-and-train.

Best,
Dog Training Team
"""

    sms = f"Hi {lead.owner_name or ''}, thanks for reaching out about {lead.dog_name or 'your dog'}. Based on the issue, the best next step is a quick training consultation. Book here: {BOOKING_LINK}"

    follow_up = f"""Hi {lead.owner_name or 'there'}, just following up about training for {lead.dog_name or 'your dog'}.

If you're still looking for help with {lead.behavior_issue or 'training'}, the next step would be a quick consultation so we can recommend the right program.

Booking link:
{BOOKING_LINK}
"""

    return subject, email, sms, follow_up

def lead_to_dict(x):
    return {
        "id": x.lead_id,
        "owner_name": x.owner_name,
        "dog_name": x.dog_name,
        "dog_breed": x.dog_breed,
        "dog_age": x.dog_age,
        "behavior_issue": x.behavior_issue,
        "service_interest": x.service_interest,
        "urgency": x.urgency,
        "phone": x.phone,
        "email": x.email,
        "city": x.city,
        "state": x.state,
        "source": x.source,
        "notes": x.notes,
        "score": x.score,
        "priority": x.priority,
        "ai_summary": x.ai_summary,
        "recommended_program": x.recommended_program,
        "next_best_action": x.next_best_action,
        "estimated_program_value": x.estimated_program_value,
        "probability_to_close": x.probability_to_close,
        "projected_revenue": x.projected_revenue,
        "status": x.status,
        "created_at": x.created_at.isoformat() if x.created_at else None
    }

def create_or_update_lead(data):
    owner_name = data.get("owner_name", "Unknown Owner")
    dog_name = data.get("dog_name", "")
    phone = data.get("phone", "")
    email = data.get("email", "")
    lead_id = make_lead_id(owner_name, dog_name, phone, email)

    existing = Lead.query.filter_by(lead_id=lead_id).first()
    if existing:
        return existing, False

    score, priority, summary, program, action = score_dog_training_lead(
        data.get("behavior_issue", ""),
        data.get("service_interest", ""),
        data.get("notes", ""),
        data.get("dog_breed", ""),
        data.get("urgency", "")
    )

    projected = calc_projected_revenue(
        data.get("estimated_program_value", 0),
        data.get("probability_to_close", 0.25)
    )

    lead = Lead(
        lead_id=lead_id,
        owner_name=owner_name,
        dog_name=data.get("dog_name", ""),
        dog_breed=data.get("dog_breed", ""),
        dog_age=data.get("dog_age", ""),
        behavior_issue=data.get("behavior_issue", ""),
        service_interest=data.get("service_interest", ""),
        urgency=data.get("urgency", ""),
        phone=phone,
        email=email,
        city=data.get("city", ""),
        state=data.get("state", ""),
        source=data.get("source", "Manual/API"),
        notes=data.get("notes", ""),
        score=score,
        priority=priority,
        recommended_program=program,
        next_best_action=action,
        estimated_program_value=float(data.get("estimated_program_value") or 0),
        probability_to_close=float(data.get("probability_to_close") or 0.25),
        projected_revenue=projected,
        status=data.get("status", "New")
    )

    lead.ai_summary = fallback_summary(lead)
    db.session.add(lead)
    db.session.commit()

    lead.ai_summary = ai_summary_for_lead(lead)
    db.session.commit()

    return lead, True

def seed_leads():
    examples = [
        {
            "owner_name": "Sarah Mitchell",
            "dog_name": "Rex",
            "dog_breed": "German Shepherd",
            "dog_age": "3 years",
            "behavior_issue": "Aggression and reactivity toward other dogs on walks. Owner says Rex has lunged and snapped before.",
            "service_interest": "Behavior modification private lessons",
            "urgency": "Urgent",
            "phone": "",
            "email": "",
            "city": "Virginia Beach",
            "state": "VA",
            "source": "Demo Lead",
            "estimated_program_value": 2500,
            "probability_to_close": 0.45,
            "notes": "High urgency behavior case."
        },
        {
            "owner_name": "James Carter",
            "dog_name": "Bella",
            "dog_breed": "Golden Retriever",
            "dog_age": "12 weeks",
            "behavior_issue": "Puppy biting, potty training, crate training, and basic obedience.",
            "service_interest": "Puppy training package",
            "urgency": "This week",
            "city": "Norfolk",
            "state": "VA",
            "source": "Demo Lead",
            "estimated_program_value": 900,
            "probability_to_close": 0.35,
            "notes": "Good fit for puppy training package."
        },
        {
            "owner_name": "Amanda Lewis",
            "dog_name": "Diesel",
            "dog_breed": "Pit Bull mix",
            "dog_age": "2 years",
            "behavior_issue": "Leash pulling, jumping, poor recall, and owner is interested in board and train.",
            "service_interest": "Board and train",
            "urgency": "Ready to book",
            "city": "Chesapeake",
            "state": "VA",
            "source": "Demo Lead",
            "estimated_program_value": 4200,
            "probability_to_close": 0.50,
            "notes": "High-ticket board-and-train opportunity."
        },
        {
            "owner_name": "Michael Brown",
            "dog_name": "Luna",
            "dog_breed": "Husky",
            "dog_age": "4 years",
            "behavior_issue": "Separation anxiety, barking, destructive behavior when left alone.",
            "service_interest": "Private lessons",
            "urgency": "Soon",
            "city": "Portsmouth",
            "state": "VA",
            "source": "Demo Lead",
            "estimated_program_value": 1500,
            "probability_to_close": 0.40,
            "notes": "Anxiety case with strong private lesson fit."
        }
    ]

    for item in examples:
        create_or_update_lead(item)

@app.before_request
def setup():
    db.create_all()
    if Lead.query.count() == 0:
        seed_leads()

@app.route("/login", methods=["GET", "POST"])
def login():
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return redirect(url_for("index"))

    error = ""
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid login."

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    leads = Lead.query.order_by(Lead.score.desc(), Lead.created_at.desc()).all()
    outreach = Outreach.query.order_by(Outreach.created_at.desc()).limit(20).all()

    total_revenue = sum([x.projected_revenue or 0 for x in leads])
    high_count = len([x for x in leads if x.priority == "High"])
    avg_score = round(sum([x.score or 0 for x in leads]) / len(leads), 1) if leads else 0

    metrics = {
        "total_leads": len(leads),
        "high_priority": high_count,
        "projected_revenue": total_revenue,
        "average_score": avg_score,
        "outreach_count": Outreach.query.count(),
        "new_count": len([x for x in leads if x.status == "New"]),
        "contacted_count": len([x for x in leads if x.status == "Contacted"]),
        "booked_count": len([x for x in leads if x.status == "Booked"]),
        "demo_mode": not ADMIN_USERNAME or not ADMIN_PASSWORD
    }

    return render_template("index.html", leads=leads, outreach=outreach, metrics=metrics, booking_link=BOOKING_LINK)

@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "system": "Dog Training AI Lead Intelligence & Client Booking Command Center",
        "render_safe": True,
        "requires_paid_keys": False
    })

@app.route("/api/leads")
def api_leads():
    leads = Lead.query.order_by(Lead.score.desc()).all()
    return jsonify({"count": len(leads), "leads": [lead_to_dict(x) for x in leads]})

@app.route("/api/add-lead", methods=["POST"])
def add_lead():
    data = request.get_json(silent=True) or {}
    lead, created = create_or_update_lead(data)

    if MAKE_WEBHOOK_URL:
        try:
            requests.post(MAKE_WEBHOOK_URL, json=lead_to_dict(lead), timeout=10)
        except Exception:
            pass

    return jsonify({"status": "saved" if created else "duplicate", "lead": lead_to_dict(lead)})

@app.route("/api/import-leads", methods=["POST"])
def import_leads():
    data = request.get_json(silent=True) or {}
    source = data.get("source", "Bulk Import")
    incoming = data.get("leads", [])

    created = 0
    duplicates = 0
    results = []

    for item in incoming:
        item["source"] = item.get("source", source)
        lead, was_created = create_or_update_lead(item)
        created += 1 if was_created else 0
        duplicates += 0 if was_created else 1
        results.append(lead_to_dict(lead))

    return jsonify({
        "status": "import_complete",
        "created": created,
        "duplicates": duplicates,
        "count": len(results),
        "leads": results
    })

@app.route("/api/lead-source-template")
def lead_source_template():
    return jsonify({
        "purpose": "Use this format from Make.com, Google Sheets, website forms, Meta leads, or dog training lead sources.",
        "send_to": "/api/import-leads",
        "method": "POST",
        "example_payload": {
            "source": "Google Sheets / Website Form / Make.com",
            "leads": [
                {
                    "owner_name": "Jane Smith",
                    "dog_name": "Max",
                    "dog_breed": "German Shepherd",
                    "dog_age": "2 years",
                    "behavior_issue": "Reactive on leash and barking at other dogs.",
                    "service_interest": "Private lessons",
                    "urgency": "Ready to book",
                    "phone": "555-555-5555",
                    "email": "owner@example.com",
                    "city": "Virginia Beach",
                    "state": "VA",
                    "estimated_program_value": 1800,
                    "probability_to_close": 0.35,
                    "notes": "Needs consultation."
                }
            ]
        }
    })

@app.route("/api/outreach/<lead_id>", methods=["POST"])
def outreach(lead_id):
    lead = Lead.query.filter_by(lead_id=lead_id).first()
    if not lead:
        return jsonify({"status": "not_found"}), 404

    subject, email_body, sms_body, follow_up = build_messages(lead)

    db.session.add(Outreach(lead_id=lead.lead_id, channel="email", subject=subject, message=email_body, status="drafted"))
    db.session.add(Outreach(lead_id=lead.lead_id, channel="sms", subject="", message=sms_body, status="drafted"))
    db.session.add(Outreach(lead_id=lead.lead_id, channel="follow_up", subject="Dog training follow-up", message=follow_up, status="drafted"))
    db.session.commit()

    return jsonify({
        "status": "drafted",
        "email_subject": subject,
        "email_body": email_body,
        "sms_body": sms_body,
        "follow_up_message": follow_up,
        "human_approval_required": True
    })

@app.route("/api/gmail-draft/<lead_id>", methods=["POST"])
def gmail_draft(lead_id):
    lead = Lead.query.filter_by(lead_id=lead_id).first()
    if not lead:
        return jsonify({"status": "not_found"}), 404

    subject, email_body, sms_body, follow_up = build_messages(lead)

    db.session.add(Outreach(lead_id=lead.lead_id, channel="gmail_draft", subject=subject, message=email_body, status="drafted"))
    db.session.commit()

    return jsonify({
        "status": "gmail_draft_ready",
        "to": lead.email,
        "subject": subject,
        "body": email_body,
        "note": "This does not send automatically. Use Gmail or Make.com for human-approved draft creation."
    })

@app.route("/api/sheets-sync/<lead_id>", methods=["POST"])
def sheets_sync(lead_id):
    lead = Lead.query.filter_by(lead_id=lead_id).first()
    if not lead:
        return jsonify({"status": "not_found"}), 404

    payload = lead_to_dict(lead)

    if MAKE_WEBHOOK_URL:
        try:
            r = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=10)
            return jsonify({"status": "sent_to_make_webhook", "status_code": r.status_code, "payload": payload})
        except Exception as e:
            return jsonify({"status": "webhook_failed", "error": str(e), "payload": payload})

    return jsonify({
        "status": "payload_ready",
        "note": "Add MAKE_WEBHOOK_URL env var to send this to Make.com / Google Sheets.",
        "payload": payload
    })

@app.route("/api/update-lead", methods=["POST"])
def update_lead():
    data = request.get_json(silent=True) or {}
    lead = Lead.query.filter_by(lead_id=data.get("id")).first()

    if not lead:
        return jsonify({"status": "not_found"}), 404

    lead.status = data.get("status", lead.status)
    lead.notes = data.get("notes", lead.notes)
    db.session.commit()

    return jsonify({"status": "updated", "lead": lead_to_dict(lead)})

@app.route("/api/regenerate-summary/<lead_id>", methods=["POST"])
def regenerate_summary(lead_id):
    lead = Lead.query.filter_by(lead_id=lead_id).first()
    if not lead:
        return jsonify({"status": "not_found"}), 404

    lead.ai_summary = ai_summary_for_lead(lead)
    db.session.commit()

    return jsonify({"status": "summary_updated", "ai_summary": lead.ai_summary})

if __name__ == "__main__":
    app.run(debug=True)
