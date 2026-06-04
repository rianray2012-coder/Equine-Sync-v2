"""seed_data.py — self-contained demo-data seeder.

Extracted from server.py (Phase 3B). Exposes a single ``run_seed(db)``
coroutine used by BOTH the startup auto-seed and the guarded /api/seed route.
It performs NO authorization itself — callers are responsible for gating
access (see routes/admin.py + core.config.evaluate_seed_access / auto_seed_enabled).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import bcrypt


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def run_seed(db):
    """Idempotent: clears and inserts rich demo data. Returns a small status dict."""
    now_utc, iso, new_id, hash_pwd = _now_utc, _iso, _new_id, _hash_pwd

    seeded_collections = ["users", "horses", "owners", "riders", "medications", "medication_logs",
              "feed_tasks", "vet_records", "injuries", "wellness", "lessons", "training",
              "invoices", "messages", "service_requests", "incidents"]
    for c in seeded_collections:
        await db[c].delete_many({})

    # demo users
    demo_users = [
        ("admin@equinesync.com", "demo1234", "Eleanor Whitfield", "admin"),
        ("trainer@equinesync.com", "demo1234", "Marcus Aldridge", "trainer"),
        ("groom@equinesync.com", "demo1234", "Sophia Reyes", "groom"),
        ("owner@equinesync.com", "demo1234", "Charlotte Vance", "horse_owner"),
        ("vet@equinesync.com", "demo1234", "Dr. Henrik Vossler", "veterinarian"),
    ]
    for email, pwd, name, role in demo_users:
        await db.users.insert_one({
            "id": new_id(), "email": email, "full_name": name, "role": role,
            "password_hash": hash_pwd(pwd), "created_at": iso(now_utc()),
        })

    # Owners
    owners = []
    for name, email, phone in [
        ("Charlotte Vance", "charlotte@vanceequestrian.com", "+1 555 0142"),
        ("Alexandre Beaumont", "a.beaumont@beaumonte.eu", "+33 1 22 33 44 55"),
        ("Isabella Hartwell", "isabella@hartwellfarms.com", "+1 555 0388"),
    ]:
        o = {"id": new_id(), "full_name": name, "email": email, "phone": phone,
             "horses": [], "photo_url": None, "created_at": iso(now_utc())}
        await db.owners.insert_one(o)
        owners.append(o)

    # Riders
    riders = []
    for name, level, goals in [
        ("Amelia Vance", "intermediate", "Move up to 1.10m jumpers by summer"),
        ("Theodore Beaumont", "advanced", "Compete CDI Small Tour 2026"),
        ("Olivia Hartwell", "beginner", "Confident canter on the rail"),
    ]:
        r = {"id": new_id(), "full_name": name, "age": 16, "skill_level": level,
             "goals": goals, "emergency_contact": "+1 555 0900",
             "photo_url": None, "created_at": iso(now_utc())}
        await db.riders.insert_one(r)
        riders.append(r)

    # Horses
    horse_seed = [
        ("Valentino", "Hanoverian", 11, "Bay", 16.3, "Show Jumping", "active", "Stall 1",
         "https://images.unsplash.com/photo-1553284965-5dc02f396399?w=900&auto=format&fit=crop",
         "Sweet itch", "Premier Equine 2.5M", 92, "Aim for 1.20m by April."),
        ("Saint-Cloud", "Selle Français", 9, "Grey", 17.0, "Show Jumping", "active", "Stall 3",
         "https://images.unsplash.com/photo-1534773728080-33d31da27ae5?w=900&auto=format&fit=crop",
         "", "Hartwell Insurance 1.8M", 88, "Maintain fitness through indoor season."),
        ("Belle Étoile", "Dutch Warmblood", 14, "Chestnut", 16.2, "Dressage", "active", "Stall 5",
         "https://images.unsplash.com/photo-1605713704694-f59ae1ca8efb?w=900&auto=format&fit=crop",
         "Bee stings", "Beaumont Coverage 1.2M", 90, "Confirm flying changes in 4-tempi."),
        ("Whisper", "Thoroughbred", 16, "Black", 16.0, "Hunters", "stall_rest", "Stall 7",
         "https://images.unsplash.com/photo-1639570830431-6c2d0100d37b?w=900&auto=format&fit=crop",
         "Penicillin", "Vance Premier 800K", 64, "Rehab from soft tissue."),
        ("Mercury", "KWPN", 7, "Dark Bay", 16.1, "Show Jumping", "active", "Stall 9",
         "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=900&auto=format&fit=crop",
         "", "Working Insurance", 86, "Build canter strength."),
        ("Iolani", "Lusitano", 12, "Grey", 15.3, "Dressage", "rehab", "Stall 11",
         "https://images.unsplash.com/photo-1598974357801-cbca100e65d3?w=900&auto=format&fit=crop",
         "", "Beaumont 1.2M", 71, "Return to controlled work."),
    ]
    horses = []
    flags_pool = ["Buddy sour", "Hard to catch", "Solo turnout", "Dominant", "Kicks"]
    for i, h in enumerate(horse_seed):
        doc = {
            "id": new_id(),
            "name": h[0], "barn_name": h[0].split()[0], "breed": h[1], "age": h[2],
            "color": h[3], "height_hands": h[4], "discipline": h[5], "status": h[6],
            "stall": h[7], "photo_url": h[8],
            "allergies": [h[9]] if h[9] else [],
            "insurance": h[10], "wellness_score": h[11], "training_goals": h[12],
            "owner_id": owners[i % 3]["id"],
            "rider_id": riders[i % 3]["id"],
            "feed_plan": "Morning: 2lb grain + 4lb hay. Midday: 4lb hay. Evening: 2lb grain + 6lb hay + supplements.",
            "turnout_group": ["Geldings A", "Geldings B", "Mares Pasture"][i % 3],
            "behavior_flags": [flags_pool[i % len(flags_pool)]] if i % 2 == 0 else [],
            "emergency_notes": "Owner authorises emergency vet care up to $5,000.",
            "created_at": iso(now_utc()),
        }
        await db.horses.insert_one(doc)
        horses.append(doc)

    # Feed tasks (today, all 3 meals each horse)
    today = now_utc().date().isoformat()
    meals = [("morning", "2lb Triple Crown Senior + 4lb timothy hay"),
             ("midday", "4lb timothy hay + free-choice water"),
             ("evening", "2lb grain + 6lb hay + joint supplement")]
    for h in horses:
        for meal, ration in meals:
            await db.feed_tasks.insert_one({
                "id": new_id(),
                "horse_id": h["id"], "horse_name": h["name"], "meal": meal,
                "ration": ration, "instructions": "Soak feed for Whisper.",
                "date": today, "completed": meal == "morning",
                "completed_by": "Sophia Reyes" if meal == "morning" else None,
                "completed_at": iso(now_utc()) if meal == "morning" else None,
            })

    # Medications
    for h in horses[:4]:
        med = {
            "id": new_id(),
            "horse_id": h["id"], "horse_name": h["name"],
            "name": "Previcox", "dosage": "57mg", "route": "oral",
            "frequency": "Once daily", "prescribing_vet": "Dr. Henrik Vossler",
            "times": ["08:00"], "notes": "Give with feed.",
            "start_date": today, "created_at": iso(now_utc()),
        }
        await db.medications.insert_one(med)
        # log entries
        await db.medication_logs.insert_one({
            "id": new_id(),
            "medication_id": med["id"], "horse_id": h["id"], "horse_name": h["name"],
            "med_name": med["name"], "dosage": med["dosage"],
            "scheduled_time": f"{today}T08:00:00",
            "status": "given" if h["wellness_score"] > 80 else "missed",
            "notes": None,
        })

    # Vet records
    for h in horses:
        await db.vet_records.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "type": "vaccine", "title": "Spring Vaccine — EWT, Flu/Rhino",
            "date": (now_utc() - timedelta(days=30)).date().isoformat(),
            "vet_name": "Dr. Henrik Vossler", "cost": 245.0,
            "notes": "All shots up to date.", "created_at": iso(now_utc()),
        })
        await db.vet_records.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "type": "coggins", "title": "Coggins (negative)",
            "date": (now_utc() - timedelta(days=60)).date().isoformat(),
            "vet_name": "Dr. Henrik Vossler", "cost": 95.0,
            "notes": "Valid 12 months.", "created_at": iso(now_utc()),
        })

    # Injuries
    await db.injuries.insert_one({
        "id": new_id(), "horse_id": horses[3]["id"], "horse_name": horses[3]["name"],
        "title": "Right front suspensory strain", "description": "Mild proximal suspensory desmitis.",
        "status": "improving", "severity": "moderate",
        "start_date": (now_utc() - timedelta(days=21)).date().isoformat(),
        "rehab_plan": "6 weeks: 4 wks hand-walking, then tack walk + jog.",
        "created_at": iso(now_utc()),
    })
    await db.injuries.insert_one({
        "id": new_id(), "horse_id": horses[5]["id"], "horse_name": horses[5]["name"],
        "title": "Hind fetlock swelling", "description": "Soft tissue, monitoring.",
        "status": "monitoring", "severity": "mild",
        "start_date": (now_utc() - timedelta(days=10)).date().isoformat(),
        "rehab_plan": "Cold therapy 2x daily, light hand walking.",
        "created_at": iso(now_utc()),
    })

    # Wellness entries
    for h in horses:
        await db.wellness.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "appetite": 5, "water_intake": 5, "energy": 4 if h["wellness_score"] < 80 else 5,
            "body_condition": 5.5, "coat_quality": 5,
            "status": "concern" if h["wellness_score"] < 75 else ("watch" if h["wellness_score"] < 85 else "normal"),
            "notes": "Bright and forward today.",
            "created_at": iso(now_utc() - timedelta(hours=4)),
        })

    # Lessons (today + tomorrow)
    for idx, r in enumerate(riders):
        start = now_utc().replace(hour=10 + idx * 2, minute=0, second=0, microsecond=0)
        await db.lessons.insert_one({
            "id": new_id(),
            "rider_id": r["id"], "rider_name": r["full_name"],
            "horse_id": horses[idx]["id"], "horse_name": horses[idx]["name"],
            "trainer_id": None, "trainer_name": "Marcus Aldridge",
            "start_time": iso(start), "duration_min": 60,
            "focus": ["Gymnastic grid", "Lateral work", "Position & balance"][idx],
            "completed": False, "created_at": iso(now_utc()),
        })

    # Training sessions
    for h in horses[:4]:
        await db.training.insert_one({
            "id": new_id(), "horse_id": h["id"], "horse_name": h["name"],
            "trainer_id": None, "trainer_name": "Marcus Aldridge",
            "date": (now_utc() - timedelta(days=1)).date().isoformat(),
            "discipline": h["discipline"],
            "exercises": "Trot poles, canter transitions, gymnastic line 2-1-2.",
            "notes": "Forward, balanced, sharp off the leg.",
            "rating": 8, "homework": "Hack out tomorrow.",
            "created_at": iso(now_utc()),
        })

    # Invoices
    invoice_items = [
        {"label": "Full Board (Monthly)", "amount": 2850},
        {"label": "Training (4x/week)", "amount": 1200},
        {"label": "Supplements", "amount": 145},
    ]
    for idx, o in enumerate(owners):
        await db.invoices.insert_one({
            "id": new_id(), "owner_id": o["id"], "owner_name": o["full_name"],
            "horse_id": horses[idx]["id"], "horse_name": horses[idx]["name"],
            "items": invoice_items,
            "total": sum(i["amount"] for i in invoice_items),
            "due_date": (now_utc() + timedelta(days=10 - idx * 4)).date().isoformat(),
            "status": ["open", "paid", "overdue"][idx],
            "created_at": iso(now_utc()),
        })

    # Messages
    await db.messages.insert_one({
        "id": new_id(), "from_user_id": "system", "from_name": "Eleanor Whitfield",
        "to_role": "trainer", "subject": "Spring Show Schedule",
        "body": "Please confirm entries for the Wellington circuit by Friday.",
        "visibility": "staff_only", "read": False,
        "created_at": iso(now_utc() - timedelta(hours=3)),
    })
    await db.messages.insert_one({
        "id": new_id(), "from_user_id": "system", "from_name": "Charlotte Vance",
        "to_role": "admin", "subject": "Extra grooming for Saturday",
        "body": "Could we add a body clip before Saturday's show?",
        "visibility": "admin_only", "read": False,
        "created_at": iso(now_utc() - timedelta(hours=6)),
    })

    # Service requests
    await db.service_requests.insert_one({
        "id": new_id(), "horse_id": horses[0]["id"], "horse_name": horses[0]["name"],
        "type": "body_clip", "details": "Full body clip before Saturday show.",
        "requested_date": (now_utc() + timedelta(days=2)).date().isoformat(),
        "requested_by": "system", "requester_name": "Charlotte Vance",
        "status": "pending", "created_at": iso(now_utc()),
    })
    await db.service_requests.insert_one({
        "id": new_id(), "horse_id": horses[2]["id"], "horse_name": horses[2]["name"],
        "type": "extra_ride", "details": "Schoolmaster ride on Thursday morning.",
        "requested_date": (now_utc() + timedelta(days=3)).date().isoformat(),
        "requested_by": "system", "requester_name": "Alexandre Beaumont",
        "status": "pending", "created_at": iso(now_utc()),
    })

    # Incidents
    await db.incidents.insert_one({
        "id": new_id(), "horse_id": horses[3]["id"], "horse_name": horses[3]["name"],
        "type": "injury", "title": "Cast in stall overnight",
        "description": "Whisper found cast at 5am; freed without injury.",
        "severity": "moderate", "occurred_at": iso(now_utc() - timedelta(hours=8)),
        "status": "open", "follow_up": "Add stall padding & monitor cameras.",
        "reported_by": "Sophia Reyes", "created_at": iso(now_utc()),
    })

    # Phase 4A: stamp the canonical barn on every freshly-seeded document
    # (idempotent — only sets where missing). Keeps demo data tenant-consistent.
    for c in seeded_collections:
        await db[c].update_many({"barn_id": {"$exists": False}},
                                {"$set": {"barn_id": "primary"}})

    return {"ok": True, "seeded": True}
