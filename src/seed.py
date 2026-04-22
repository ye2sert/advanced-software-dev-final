"""
PAMS - Seed script: populates DB with realistic mock data for demo + testing.
Author: Tahmid Ahmed (240180955) 

"""
from datetime import date, timedelta
import random
from services import hash_password


def seed(db):
    """Fill empty DB with 4 cities, users of every role, apartments, tenants,
    leases, invoices, a couple of payments and maintenance requests."""

    # locations
    cities = [
        ("Bristol",    "12 Harbourside, Bristol BS1 5TX"),
        ("Cardiff",    "44 Queen Street, Cardiff CF10 2PU"),
        ("London",     "88 Baker Street, London W1U 6RP"),
        ("Manchester", "15 Deansgate, Manchester M3 2BW"),
    ]
    loc_ids = {}
    for city, addr in cities:
        cur = db.execute("INSERT INTO locations (city, address) VALUES (?,?)",
                         (city, addr))
        loc_ids[city] = cur.lastrowid

    # users (1 of each role per city + 1 cross-location Manager) 
    role_table = [
        ("admin",        "admin123",     "Alex Admin",       "admin@pams.co.uk",       "Administrator"),
        ("frontdesk",    "desk123",      "Fiona FrontDesk",  "fiona@pams.co.uk",       "FrontDesk"),
        ("finance",      "finance123",   "Fred Finance",     "fred@pams.co.uk",        "FinanceManager"),
        ("maintenance",  "maint123",     "Mia Maintenance",  "mia@pams.co.uk",         "MaintenanceStaff"),
    ]
    user_ids = {}
    for city, _addr in cities:
        for (uname, pw, fname, email, role) in role_table:
            username = f"{uname}_{city.lower()}"
            email_u  = email.replace("@", f"+{city.lower()}@")
            pw_hash, salt = hash_password(pw)
            cur = db.execute(
                """INSERT INTO users
                   (username, password_hash, salt, full_name, email, role, location_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (username, pw_hash, salt, fname, email_u, role, loc_ids[city]))
            user_ids[username] = cur.lastrowid

    # Top-level Manager (cross-location)
    pw_hash, salt = hash_password("manager123")
    cur = db.execute(
        """INSERT INTO users
           (username, password_hash, salt, full_name, email, role, location_id)
           VALUES (?,?,?,?,?,?,?)""",
        ("manager", pw_hash, salt, "Morgan Manager",
         "morgan@pams.co.uk", "Manager", None))
    user_ids["manager"] = cur.lastrowid

    # apartments (6 per city) 
    apt_ids_by_city = {city: [] for city, _ in cities}
    apt_types = [
        ("Studio", 0,  850),
        ("1-Bed",  1, 1100),
        ("2-Bed",  2, 1450),
        ("2-Bed",  2, 1500),
        ("3-Bed",  3, 1850),
        ("3-Bed",  3, 1950),
    ]
    for city, _addr in cities:
        for i, (atype, beds, rent) in enumerate(apt_types, 1):
            cur = db.execute(
                """INSERT INTO apartments
                   (location_id, apt_number, apt_type, bedrooms, monthly_rent, status)
                   VALUES (?,?,?,?,?, 'Available')""",
                (loc_ids[city], f"{city[:3].upper()}-{i:02d}",
                 atype, beds, rent))
            apt_ids_by_city[city].append(cur.lastrowid)  

    # tenants + leases (fill ~half of apartments) 
    tenants_data = [
        ("AB123456C", "Jane Smith",       "+44 7700 900001", "jane.smith@example.com",  "Teacher",     "Prev landlord OK"),
        ("CD234567D", "John Doe",         "+44 7700 900002", "john.doe@example.com",    "Engineer",    "2 refs"),
        ("EF345678E", "Alice Brown",      "+44 7700 900003", "alice.b@example.com",     "Nurse",       "Employer"),
        ("GH456789F", "Bob Wilson",       "+44 7700 900004", "bob.w@example.com",       "Accountant",  "Guarantor"),
        ("IJ567890G", "Carol Davis",      "+44 7700 900005", "carol.d@example.com",     "Developer",   "OK"),
        ("KL678901H", "David Evans",      "+44 7700 900006", "david.e@example.com",     "Doctor",      "Clean"),
        ("MN789012I", "Eve Foster",       "+44 7700 900007", "eve.f@example.com",       "Lawyer",      "Ref x2"),
        ("OP890123J", "Frank Green",      "+44 7700 900008", "frank.g@example.com",     "Chef",        "OK"),
    ]
    city_cycle = [c for c, _ in cities] * 2
    admin_city = {c: user_ids[f"admin_{c.lower()}"] for c, _ in cities}

    tenant_ids = []
    for idx, (ni, name, phone, email, occ, refs) in enumerate(tenants_data):
        city = city_cycle[idx]
        cur = db.execute(
            """INSERT INTO tenants
               (ni_number, full_name, phone, email, occupation,
                tenant_references, location_id, created_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (ni, name, phone, email, occ, refs, loc_ids[city],
             user_ids[f"frontdesk_{city.lower()}"]))
        tenant_ids.append((cur.lastrowid, city))

    # create leases for each tenant
    lease_ids = []
    today = date.today()
    for (tid, city) in tenant_ids:
        # pick first available apt in that city
        apt_rows = db.query_all(
            "SELECT apartment_id, monthly_rent FROM apartments "
            "WHERE location_id = ? AND status = 'Available' LIMIT 1",
            (loc_ids[city],))
        if not apt_rows:
            continue
        apt = apt_rows[0]
        start = today - timedelta(days=random.randint(30, 300))
        end   = start + timedelta(days=365)
        rent  = apt["monthly_rent"]
        cur = db.execute(
            """INSERT INTO leases
               (tenant_id, apartment_id, start_date, end_date,
                deposit, monthly_rent, status)
               VALUES (?,?,?,?,?,?, 'Active')""",
            (tid, apt["apartment_id"], start.isoformat(), end.isoformat(),
             rent * 2, rent))
        lease_ids.append(cur.lastrowid)
        db.execute("UPDATE apartments SET status = 'Occupied' WHERE apartment_id = ?",
                   (apt["apartment_id"],))

    # invoices + some payments 
    for lid in lease_ids:
        le = db.query_one("SELECT * FROM leases WHERE lease_id = ?", (lid,))
        # 2 historic invoices
        for m in range(2):
            issue = (today - timedelta(days=60 - m*30)).isoformat()
            due   = (today - timedelta(days=30 - m*30)).isoformat()
            cur = db.execute(
                """INSERT INTO invoices
                   (lease_id, amount, issue_date, due_date, status)
                   VALUES (?,?,?,?, 'Pending')""",
                (lid, le["monthly_rent"], issue, due))
            iid = cur.lastrowid
            # randomly mark some paid
            if random.random() < 0.7:
                db.execute(
                    """INSERT INTO payments
                       (invoice_id, amount, payment_date, method, recorded_by)
                       VALUES (?,?,?,?,?)""",
                    (iid, le["monthly_rent"],
                     (today - timedelta(days=25 - m*30)).isoformat(),
                     "BankTransfer",
                     user_ids["finance_" + _city_for_lease(db, lid).lower()]))
                db.execute("UPDATE invoices SET status = 'Paid' WHERE invoice_id = ?",
                           (iid,))
        # current pending invoice
        db.execute(
            """INSERT INTO invoices
               (lease_id, amount, issue_date, due_date, status)
               VALUES (?,?,?,?, 'Pending')""",
            (lid, le["monthly_rent"], today.isoformat(),
             (today + timedelta(days=14)).isoformat()))

    # maintenance requests 
    maint_examples = [
        ("Leaking tap in kitchen",            "Medium"),
        ("Boiler not heating water",          "High"),
        ("Broken window lock",                "High"),
        ("Mould on bathroom ceiling",         "Medium"),
        ("Front door doesn't lock properly",  "Critical"),
    ]
    apt_rows = db.query_all("SELECT apartment_id, location_id FROM apartments")
    for desc, pr in maint_examples:
        apt = random.choice(apt_rows)
        city = next(c for c, lid in loc_ids.items() if lid == apt["location_id"])
        db.execute(
            """INSERT INTO maintenance_requests
               (apartment_id, description, priority, status, reported_date,
                reported_by)
               VALUES (?,?,?, 'Open', ?, ?)""",
            (apt["apartment_id"], desc, pr, today.isoformat(),
             user_ids[f"frontdesk_{city.lower()}"]))

    # a resolved one with cost
    apt = random.choice(apt_rows)
    city = next(c for c, lid in loc_ids.items() if lid == apt["location_id"])
    db.execute(
        """INSERT INTO maintenance_requests
           (apartment_id, description, priority, status, reported_date,
            resolved_date, assigned_to, time_taken_hours, cost,
            resolution_notes, reported_by)
           VALUES (?,?,?, 'Resolved', ?, ?, ?, ?, ?, ?, ?)""",
        (apt["apartment_id"], "Replaced kitchen sink", "Medium",
         (today - timedelta(days=14)).isoformat(),
         (today - timedelta(days=10)).isoformat(),
         user_ids[f"maintenance_{city.lower()}"],
         4.0, 180.00, "Replaced siphon and tap unit",
         user_ids[f"frontdesk_{city.lower()}"]))

    print("Seed complete. Login credentials (demo only):")
    print("  admin_bristol   / admin123")
    print("  frontdesk_bristol / desk123")
    print("  finance_bristol / finance123")
    print("  maintenance_bristol / maint123")
    print("  manager         / manager123")


def _city_for_lease(db, lease_id: int) -> str:
    row = db.query_one(
        """SELECT l.city FROM leases le
           JOIN apartments a ON a.apartment_id = le.apartment_id
           JOIN locations l ON l.location_id = a.location_id
           WHERE le.lease_id = ?""", (lease_id,))
    return row["city"]
