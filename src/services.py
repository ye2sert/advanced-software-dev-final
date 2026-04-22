"""
PAMS - Services layer (auth, business logic, notifications)
Author: Tahmid Ahmed (240180955), Mackenzie Sawers (24033341) and Yunus Sert (24015097)
"""
from __future__ import annotations
import hashlib
import os
import secrets
from datetime import datetime, date, timedelta
from typing import Optional

from models import (
    User, Tenant, Apartment, Lease, Invoice, Payment, MaintenanceRequest,
    user_from_row,
    OccupancyReport, FinancialReport, MaintenanceCostReport,
)

# Password hashing (PBKDF2)
PBKDF2_ITERATIONS = 120_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (hash_hex, salt_hex). Generate salt if not given."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return dk.hex(), salt


def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    # constant-time compare
    return secrets.compare_digest(calc, pw_hash)

# Audit log
def audit(db, user_id: Optional[int], action: str,
          entity_type: str = "", entity_id: Optional[int] = None,
          details: str = ""):
    db.execute(
        """INSERT INTO audit_log (user_id, action, entity_type, entity_id, details)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, action, entity_type, entity_id, details),
    )

# Auth service

class AuthService:
    def __init__(self, db):
        self.db = db
        self._current: User | None = None

    def login(self, username: str, password: str) -> User:
        row = self.db.query_one(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,),
        )
        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            audit(self.db, None, "LOGIN_FAILED", "user", None,
                  f"username={username}")
            raise PermissionError("Invalid username or password")
        self.db.execute(
            "UPDATE users SET last_login = ? WHERE user_id = ?",
            (datetime.now().isoformat(timespec="seconds"), row["user_id"]),
        )
        self._current = user_from_row(row)
        audit(self.db, self._current.user_id, "LOGIN_OK", "user",
              self._current.user_id)
        return self._current

    @property
    def current_user(self) -> User | None:
        return self._current

    def logout(self):
        if self._current:
            audit(self.db, self._current.user_id, "LOGOUT", "user",
                  self._current.user_id)
        self._current = None

    def require(self, permission: str):
        if not self._current or not self._current.can(permission):
            raise PermissionError(
                f"Access denied. '{permission}' is not permitted for role "
                f"{self._current.role_name() if self._current else 'Guest'}."
            )



# Tenant service
class TenantService:
    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def register_tenant(self, tenant: Tenant) -> int:
        self.auth.require("tenant.register")
        # enforce unique NI number
        exists = self.db.query_one(
            "SELECT tenant_id FROM tenants WHERE ni_number = ?",
            (tenant.ni_number,),
        )
        if exists:
            raise ValueError(f"Tenant with NI {tenant.ni_number} already exists")
        cur = self.db.execute(
            """INSERT INTO tenants
               (ni_number, full_name, phone, email, occupation,
                tenant_references, location_id, created_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tenant.ni_number, tenant.full_name, tenant.phone, tenant.email,
             tenant.occupation, tenant.tenant_references, tenant.location_id,
             self.auth.current_user.user_id),
        )
        tid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "TENANT_CREATE",
              "tenant", tid, f"{tenant.full_name}")
        return tid

    def update_tenant(self, tenant_id: int, **fields):
        self.auth.require("tenant.update")
        if not fields:
            return
        allowed = {"full_name", "phone", "email", "occupation",
                   "tenant_references"}
        cols, vals = [], []
        for k, v in fields.items():
            if k in allowed:
                cols.append(f"{k} = ?")
                vals.append(v)
        vals.append(tenant_id)
        self.db.execute(f"UPDATE tenants SET {', '.join(cols)} WHERE tenant_id = ?",
                        tuple(vals))
        audit(self.db, self.auth.current_user.user_id, "TENANT_UPDATE",
              "tenant", tenant_id)

    def delete_tenant(self, tenant_id: int):
        self.auth.require("tenant.delete")
        self.db.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
        audit(self.db, self.auth.current_user.user_id, "TENANT_DELETE",
              "tenant", tenant_id)

    def list_tenants(self, location_id: int | None = None):
        self.auth.require("tenant.view")
        if location_id:
            return self.db.query_all(
                "SELECT * FROM tenants WHERE location_id = ? ORDER BY full_name",
                (location_id,))
        return self.db.query_all("SELECT * FROM tenants ORDER BY full_name")



# Apartment + Lease service
class ApartmentService:
    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def register_apartment(self, apt: Apartment) -> int:
        self.auth.require("apartment.create")
        cur = self.db.execute(
            """INSERT INTO apartments
               (location_id, apt_number, apt_type, bedrooms, monthly_rent, status)
               VALUES (?,?,?,?,?,?)""",
            (apt.location_id, apt.apt_number, apt.apt_type, apt.bedrooms,
             apt.monthly_rent, apt.status))
        aid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "APT_CREATE",
              "apartment", aid)
        return aid

    def list_apartments(self, location_id: int | None = None,
                        status: str | None = None):
        self.auth.require("apartment.view")
        sql = "SELECT a.*, l.city FROM apartments a JOIN locations l ON l.location_id = a.location_id WHERE 1=1"
        p = []
        if location_id:
            sql += " AND a.location_id = ?"
            p.append(location_id)
        if status:
            sql += " AND a.status = ?"
            p.append(status)
        sql += " ORDER BY l.city, a.apt_number"
        return self.db.query_all(sql, tuple(p))

    def assign_to_tenant(self, lease: Lease) -> int:
        self.auth.require("lease.create")
        apt = self.db.query_one(
            "SELECT status FROM apartments WHERE apartment_id = ?",
            (lease.apartment_id,))
        if not apt:
            raise ValueError("Apartment not found")
        if apt["status"] != "Available":
            raise ValueError(f"Apartment is not available (currently {apt['status']})")
        cur = self.db.execute(
            """INSERT INTO leases
               (tenant_id, apartment_id, start_date, end_date,
                deposit, monthly_rent, status)
               VALUES (?,?,?,?,?,?, 'Active')""",
            (lease.tenant_id, lease.apartment_id, lease.start_date,
             lease.end_date, lease.deposit, lease.monthly_rent))
        lid = cur.lastrowid
        self.db.execute(
            "UPDATE apartments SET status = 'Occupied' WHERE apartment_id = ?",
            (lease.apartment_id,))
        audit(self.db, self.auth.current_user.user_id, "LEASE_CREATE",
              "lease", lid)
        return lid

    def terminate_lease_early(self, lease_id: int, reason: str) -> float:
        self.auth.require("lease.terminate")
        row = self.db.query_one("SELECT * FROM leases WHERE lease_id = ?",
                                (lease_id,))
        if not row:
            raise ValueError("Lease not found")
        if row["status"] != "Active":
            raise ValueError("Lease is not active")
        penalty = round(row["monthly_rent"] * 0.05, 2)  # 5% of monthly rent
        self.db.execute(
            """UPDATE leases
               SET status = 'Terminated',
                   termination_reason = ?,
                   penalty_amount = ?
               WHERE lease_id = ?""",
            (reason, penalty, lease_id))
        self.db.execute(
            "UPDATE apartments SET status = 'Available' WHERE apartment_id = ?",
            (row["apartment_id"],))
        audit(self.db, self.auth.current_user.user_id, "LEASE_TERMINATE",
              "lease", lease_id, f"penalty={penalty}")
        return penalty

    def leases_ending_soon(self, days: int = 30):
        """For admins to track upcoming lease expirations."""
        self.auth.require("lease.track")
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today  = date.today().isoformat()
        return self.db.query_all(
            """SELECT le.*, t.full_name AS tenant_name, a.apt_number, l.city
               FROM leases le
               JOIN tenants t ON t.tenant_id = le.tenant_id
               JOIN apartments a ON a.apartment_id = le.apartment_id
               JOIN locations l ON l.location_id = a.location_id
               WHERE le.status = 'Active'
                 AND le.end_date BETWEEN ? AND ?
               ORDER BY le.end_date ASC""",
            (today, cutoff))


# Billing service
class BillingService:
    LATE_FEE_RATE = 0.05  # 5%

    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def create_invoice(self, lease_id: int, amount: float,
                       issue_date: str, due_date: str) -> int:
        self.auth.require("invoice.create")
        cur = self.db.execute(
            """INSERT INTO invoices (lease_id, amount, issue_date, due_date, status)
               VALUES (?,?,?,?, 'Pending')""",
            (lease_id, amount, issue_date, due_date))
        iid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "INVOICE_CREATE",
              "invoice", iid)
        return iid

    def record_payment(self, invoice_id: int, amount: float,
                       method: str = "BankTransfer",
                       payment_date: str | None = None) -> int:
        self.auth.require("payment.record")
        payment_date = payment_date or date.today().isoformat()
        inv = self.db.query_one("SELECT * FROM invoices WHERE invoice_id = ?",
                                (invoice_id,))
        if not inv:
            raise ValueError("Invoice not found")
        if amount <= 0:
            raise ValueError("Payment must be > 0")
        cur = self.db.execute(
            """INSERT INTO payments (invoice_id, amount, payment_date, method, recorded_by)
               VALUES (?,?,?,?,?)""",
            (invoice_id, amount, payment_date, method,
             self.auth.current_user.user_id))
        # update invoice status
        total_paid_row = self.db.query_one(
            "SELECT COALESCE(SUM(amount),0) AS paid FROM payments WHERE invoice_id = ?",
            (invoice_id,))
        total_paid = total_paid_row["paid"]
        total_due = inv["amount"] + (inv["late_fee"] or 0)
        if total_paid >= total_due:
            new_status = "Paid"
        else:
            new_status = "PartiallyPaid"
        self.db.execute(
            "UPDATE invoices SET status = ? WHERE invoice_id = ?",
            (new_status, invoice_id))
        audit(self.db, self.auth.current_user.user_id, "PAYMENT_RECORD",
              "payment", cur.lastrowid, f"£{amount}")
        return cur.lastrowid

    def apply_late_fees(self) -> list[dict]:
        """Mark overdue invoices and apply late fee. Returns notifications."""
        self.auth.require("latefee.apply")
        today = date.today().isoformat()
        overdue = self.db.query_all(
            """SELECT * FROM invoices
               WHERE status IN ('Pending','PartiallyPaid') AND due_date < ?""",
            (today,))
        notifications = []
        for inv in overdue:
            fee = round(inv["amount"] * self.LATE_FEE_RATE, 2)
            self.db.execute(
                """UPDATE invoices
                   SET status = 'Overdue', late_fee = ?
                   WHERE invoice_id = ?""",
                (fee, inv["invoice_id"]))
            notifications.append({
                "invoice_id": inv["invoice_id"],
                "original_amount": inv["amount"],
                "late_fee": fee,
                "total_due": round(inv["amount"] + fee, 2),
                "message": f"Invoice #{inv['invoice_id']} is overdue. "
                           f"Late fee of £{fee} applied. "
                           f"Total due: £{round(inv['amount']+fee, 2)}.",
            })
        audit(self.db, self.auth.current_user.user_id, "LATEFEE_RUN",
              "invoice", None, f"count={len(notifications)}")
        return notifications

    def list_invoices(self, lease_id: int | None = None,
                      status: str | None = None):
        self.auth.require("invoice.view")
        sql = "SELECT * FROM invoices WHERE 1=1"
        p = []
        if lease_id:
            sql += " AND lease_id = ?"
            p.append(lease_id)
        if status:
            sql += " AND status = ?"
            p.append(status)
        sql += " ORDER BY due_date DESC"
        return self.db.query_all(sql, tuple(p))



# Maintenance service
class MaintenanceService:
    PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def register_request(self, req: MaintenanceRequest) -> int:
        self.auth.require("maintenance.register")
        cur = self.db.execute(
            """INSERT INTO maintenance_requests
               (apartment_id, tenant_id, description, priority, status,
                reported_date, reported_by)
               VALUES (?,?,?,?, 'Open', ?, ?)""",
            (req.apartment_id, req.tenant_id, req.description, req.priority,
             req.reported_date, self.auth.current_user.user_id))
        rid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "MAINT_OPEN",
              "maintenance", rid)
        return rid

    def prioritise_queue(self, location_id: int | None = None):
        """Return OPEN requests ordered by priority then reported_date."""
        self.auth.require("maintenance.view")
        sql = """SELECT m.*, a.apt_number, l.city, t.full_name AS tenant_name
                 FROM maintenance_requests m
                 JOIN apartments a ON a.apartment_id = m.apartment_id
                 JOIN locations  l ON l.location_id  = a.location_id
                 LEFT JOIN tenants t ON t.tenant_id  = m.tenant_id
                 WHERE m.status IN ('Open','InProgress')"""
        p = []
        if location_id:
            sql += " AND a.location_id = ?"
            p.append(location_id)
        rows = self.db.query_all(sql, tuple(p))
        # Sort in Python using priority order map
        return sorted(rows, key=lambda r: (
            self.PRIORITY_ORDER.get(r["priority"], 99), r["reported_date"]))

    def assign(self, request_id: int, staff_user_id: int):
        self.auth.require("maintenance.assign")
        self.db.execute(
            """UPDATE maintenance_requests
               SET assigned_to = ?, status = 'InProgress'
               WHERE request_id = ?""",
            (staff_user_id, request_id))
        audit(self.db, self.auth.current_user.user_id, "MAINT_ASSIGN",
              "maintenance", request_id, f"assignee={staff_user_id}")

    def resolve(self, request_id: int, time_taken_hours: float,
                cost: float, notes: str):
        self.auth.require("maintenance.resolve")
        if time_taken_hours < 0 or cost < 0:
            raise ValueError("time_taken_hours and cost must be >= 0")
        self.db.execute(
            """UPDATE maintenance_requests
               SET status = 'Resolved',
                   resolved_date = ?,
                   time_taken_hours = ?,
                   cost = ?,
                   resolution_notes = ?
               WHERE request_id = ?""",
            (date.today().isoformat(), time_taken_hours, cost, notes,
             request_id))
        audit(self.db, self.auth.current_user.user_id, "MAINT_RESOLVE",
              "maintenance", request_id, f"cost={cost}")



# Report service (polymorphism entry point)
class ReportService:
    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def occupancy(self, location_id: int | None = None):
        self.auth.require("report.occupancy")
        r = OccupancyReport("Occupancy Report",
                            self.auth.current_user.user_id, location_id)
        return r.generate(self.db)

    def financial(self, location_id: int | None = None):
        self.auth.require("report.financial")
        r = FinancialReport("Financial Report",
                            self.auth.current_user.user_id, location_id)
        return r.generate(self.db)

    def maintenance(self, location_id: int | None = None):
        self.auth.require("report.maintenance")
        r = MaintenanceCostReport("Maintenance Cost Report",
                                  self.auth.current_user.user_id, location_id)
        return r.generate(self.db)


# User management service (Admin / Manager)
class UserService:
    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def create_user(self, username: str, password: str, full_name: str,
                    email: str, role: str, location_id: int | None) -> int:
        self.auth.require("user.create")
        pw_hash, salt = hash_password(password)
        cur = self.db.execute(
            """INSERT INTO users
               (username, password_hash, salt, full_name, email, role, location_id)
               VALUES (?,?,?,?,?,?,?)""",
            (username, pw_hash, salt, full_name, email, role, location_id))
        uid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "USER_CREATE",
              "user", uid, f"role={role}")
        return uid

    def deactivate_user(self, user_id: int):
        self.auth.require("user.update")
        self.db.execute("UPDATE users SET active = 0 WHERE user_id = ?",
                        (user_id,))
        audit(self.db, self.auth.current_user.user_id, "USER_DEACTIVATE",
              "user", user_id)

    def list_users(self, location_id: int | None = None):
        self.auth.require("user.view")
        if location_id:
            return self.db.query_all(
                "SELECT * FROM users WHERE location_id = ? ORDER BY role, username",
                (location_id,))
        return self.db.query_all("SELECT * FROM users ORDER BY role, username")



# Location service (Manager: expand to new city)
class LocationService:
    def __init__(self, db, auth: AuthService):
        self.db, self.auth = db, auth

    def list_locations(self):
        return self.db.query_all("SELECT * FROM locations ORDER BY city")

    def add_location(self, city: str, address: str) -> int:
        self.auth.require("location.create")
        cur = self.db.execute(
            "INSERT INTO locations (city, address) VALUES (?,?)",
            (city, address))
        lid = cur.lastrowid
        audit(self.db, self.auth.current_user.user_id, "LOCATION_CREATE",
              "location", lid, city)
        return lid
