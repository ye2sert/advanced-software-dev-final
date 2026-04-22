"""
PAMS - Domain model classes (OOP)
Author: Tahmid Ahmed (240180955) and Mackenzie Sawers (24033341)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, date
from dataclasses import dataclass, field
import re



# Base User hierarchy (inheritance + polymorphism)
class User(ABC):
    """Abstract base class for every system user."""

    def __init__(self, user_id: int, username: str, full_name: str,
                 email: str, location_id: int | None):
        self._user_id = user_id
        self._username = username
        self._full_name = full_name
        self._email = self._validate_email(email)
        self._location_id = location_id

    # encapsulation (read-only) 
    @property
    def user_id(self) -> int: return self._user_id
    @property
    def username(self) -> str: return self._username
    @property
    def full_name(self) -> str: return self._full_name
    @property
    def email(self) -> str: return self._email
    @property
    def location_id(self) -> int | None: return self._location_id

    # polymorphic 
    @abstractmethod
    def role_name(self) -> str: ...

    @abstractmethod
    def permissions(self) -> set[str]:
        """Return set of permission strings this role can perform."""

    def can(self, permission: str) -> bool:
        return permission in self.permissions()

    # validation 
    @staticmethod
    def _validate_email(email: str) -> str:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""):
            raise ValueError(f"Invalid email: {email!r}")
        return email

    def __repr__(self):
        return f"<{self.role_name()} id={self._user_id} user={self._username}>"


class FrontDeskStaff(User):
    def role_name(self) -> str:
        return "FrontDesk"

    def permissions(self) -> set[str]:
        return {
            "tenant.register", "tenant.view", "tenant.update",
            "apartment.view", "apartment.assign",
            "maintenance.register", "maintenance.view",
            "lease.create",
        }


class FinanceManager(User):
    def role_name(self) -> str:
        return "FinanceManager"

    def permissions(self) -> set[str]:
        return {
            "invoice.create", "invoice.view",
            "payment.record", "payment.view",
            "latefee.apply",
            "report.financial",
            "tenant.view", "apartment.view",
        }


class MaintenanceStaff(User):
    def role_name(self) -> str:
        return "MaintenanceStaff"

    def permissions(self) -> set[str]:
        return {
            "maintenance.view", "maintenance.assign",
            "maintenance.resolve", "maintenance.log",
            "apartment.view",
        }


class Administrator(User):
    def role_name(self) -> str:
        return "Administrator"

    def permissions(self) -> set[str]:
        return {
            "user.create", "user.update", "user.delete", "user.view",
            "tenant.register", "tenant.update", "tenant.delete", "tenant.view",
            "apartment.create", "apartment.update", "apartment.delete", "apartment.view",
            "lease.create", "lease.track", "lease.terminate",
            "report.generate", "report.financial", "report.occupancy", "report.maintenance",
            "maintenance.view",
        }


class Manager(User):
    """Top-level: cross-location oversight + business expansion."""
    def role_name(self) -> str:
        return "Manager"

    def permissions(self) -> set[str]:
        # Manager can do everything an Admin can, plus cross-location + expansion
        admin_perms = Administrator(0, "tmp", "tmp", "tmp@x.co", None).permissions()
        return admin_perms | {
            "location.create", "location.view.all",
            "report.cross_location", "business.expand",
        }


USER_ROLE_MAP = {
    "FrontDesk": FrontDeskStaff,
    "FinanceManager": FinanceManager,
    "MaintenanceStaff": MaintenanceStaff,
    "Administrator": Administrator,
    "Manager": Manager,
}


def user_from_row(row) -> User:
    """Factory: build the correct User subclass from a DB row."""
    cls = USER_ROLE_MAP.get(row["role"])
    if cls is None:
        raise ValueError(f"Unknown role: {row['role']}")
    return cls(
        user_id=row["user_id"],
        username=row["username"],
        full_name=row["full_name"],
        email=row["email"],
        location_id=row["location_id"],
    )



# Tenant
@dataclass
class Tenant:
    tenant_id: int | None
    ni_number: str
    full_name: str
    phone: str
    email: str
    occupation: str
    tenant_references: str
    location_id: int

    def __post_init__(self):
        # UK NI number: 2 letters, 6 digits, 1 letter (relaxed)
        if not re.match(r"^[A-Z]{2}\d{6}[A-Z]$", (self.ni_number or "").upper()):
            raise ValueError(f"Invalid NI number: {self.ni_number!r}")
        self.ni_number = self.ni_number.upper()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.email or ""):
            raise ValueError(f"Invalid email: {self.email!r}")
        if not re.match(r"^[+]?[\d\s\-()]{7,20}$", self.phone or ""):
            raise ValueError(f"Invalid phone: {self.phone!r}")
        if not self.full_name or len(self.full_name) < 2:
            raise ValueError("Full name is required")



# Apartment
@dataclass
class Apartment:
    apartment_id: int | None
    location_id: int
    apt_number: str
    apt_type: str
    bedrooms: int
    monthly_rent: float
    status: str = "Available"

    VALID_STATUSES = {"Available", "Occupied", "Maintenance", "Reserved"}

    def __post_init__(self):
        if self.bedrooms < 0 or self.bedrooms > 10:
            raise ValueError("bedrooms must be 0..10")
        if self.monthly_rent <= 0:
            raise ValueError("monthly_rent must be > 0")
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"invalid status: {self.status}")



# Lease
@dataclass
class Lease:
    lease_id: int | None
    tenant_id: int
    apartment_id: int
    start_date: str   # ISO date YYYY-MM-DD
    end_date: str
    deposit: float
    monthly_rent: float
    status: str = "Active"
    termination_reason: str | None = None
    penalty_amount: float = 0.0

    def __post_init__(self):
        s = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        e = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        if e <= s:
            raise ValueError("end_date must be after start_date")
        if self.deposit < 0 or self.monthly_rent <= 0:
            raise ValueError("invalid deposit or monthly_rent")

    @property
    def duration_months(self) -> int:
        s = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        e = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        return (e.year - s.year) * 12 + (e.month - s.month)

    def calculate_early_termination_penalty(self) -> float:
        """5% of monthly rent (per spec)."""
        return round(self.monthly_rent * 0.05, 2)



# Invoice / Payment
@dataclass
class Invoice:
    invoice_id: int | None
    lease_id: int
    amount: float
    issue_date: str
    due_date: str
    status: str = "Pending"
    late_fee: float = 0.0

    def is_overdue(self, today: date | None = None) -> bool:
        today = today or date.today()
        due = datetime.strptime(self.due_date, "%Y-%m-%d").date()
        return today > due and self.status in ("Pending", "PartiallyPaid")


@dataclass
class Payment:
    payment_id: int | None
    invoice_id: int
    amount: float
    payment_date: str
    method: str
    recorded_by: int | None = None



# Maintenance Request
@dataclass
class MaintenanceRequest:
    request_id: int | None
    apartment_id: int
    tenant_id: int | None
    description: str
    priority: str = "Medium"
    status: str = "Open"
    reported_date: str = field(default_factory=lambda: date.today().isoformat())
    resolved_date: str | None = None
    assigned_to: int | None = None
    time_taken_hours: float | None = None
    cost: float = 0.0
    resolution_notes: str | None = None
    reported_by: int | None = None

    VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
    VALID_STATUSES   = {"Open", "InProgress", "Resolved", "Cancelled"}

    def __post_init__(self):
        if self.priority not in self.VALID_PRIORITIES:
            raise ValueError(f"invalid priority: {self.priority}")
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if not self.description or len(self.description) < 5:
            raise ValueError("description too short")



# Reports (polymorphism)
class Report(ABC):
    def __init__(self, title: str, generated_by: int, location_id: int | None = None):
        self.title = title
        self.generated_by = generated_by
        self.location_id = location_id
        self.generated_at = datetime.now().isoformat(timespec="seconds")

    @abstractmethod
    def generate(self, db) -> dict: ...


class OccupancyReport(Report):
    def generate(self, db) -> dict:
        sql = """
        SELECT l.city,
               COUNT(a.apartment_id) AS total,
               SUM(CASE WHEN a.status='Occupied'    THEN 1 ELSE 0 END) AS occupied,
               SUM(CASE WHEN a.status='Available'   THEN 1 ELSE 0 END) AS available,
               SUM(CASE WHEN a.status='Maintenance' THEN 1 ELSE 0 END) AS in_maintenance
        FROM apartments a
        JOIN locations l ON l.location_id = a.location_id
        """
        params = ()
        if self.location_id:
            sql += " WHERE a.location_id = ?"
            params = (self.location_id,)
        sql += " GROUP BY l.city"
        rows = [dict(r) for r in db.query_all(sql, params)]
        total = sum(r["total"] for r in rows) or 1
        occupied = sum(r["occupied"] for r in rows)
        return {"title": self.title, "rows": rows,
                "occupancy_rate": round(occupied * 100 / total, 2),
                "generated_at": self.generated_at}


class FinancialReport(Report):
    def generate(self, db) -> dict:
        sql_collected = """
        SELECT COALESCE(SUM(p.amount),0) AS collected
        FROM payments p
        JOIN invoices i ON i.invoice_id = p.invoice_id
        JOIN leases   le ON le.lease_id   = i.lease_id
        JOIN apartments a ON a.apartment_id = le.apartment_id
        """
        sql_pending = """
        SELECT COALESCE(SUM(i.amount),0) AS pending
        FROM invoices i
        JOIN leases le ON le.lease_id = i.lease_id
        JOIN apartments a ON a.apartment_id = le.apartment_id
        WHERE i.status IN ('Pending','Overdue','PartiallyPaid')
        """
        params = ()
        if self.location_id:
            sql_collected += " WHERE a.location_id = ?"
            sql_pending   += " AND a.location_id = ?"
            params = (self.location_id,)
        collected = db.query_one(sql_collected, params)["collected"]
        pending   = db.query_one(sql_pending, params)["pending"]
        return {"title": self.title,
                "collected": round(collected, 2),
                "pending": round(pending, 2),
                "generated_at": self.generated_at}


class MaintenanceCostReport(Report):
    def generate(self, db) -> dict:
        sql = """
        SELECT l.city,
               COUNT(m.request_id) AS total_requests,
               COALESCE(SUM(m.cost),0) AS total_cost,
               COALESCE(AVG(m.time_taken_hours),0) AS avg_hours
        FROM maintenance_requests m
        JOIN apartments a ON a.apartment_id = m.apartment_id
        JOIN locations  l ON l.location_id  = a.location_id
        """
        params = ()
        if self.location_id:
            sql += " WHERE a.location_id = ?"
            params = (self.location_id,)
        sql += " GROUP BY l.city"
        rows = [dict(r) for r in db.query_all(sql, params)]
        return {"title": self.title, "rows": rows,
                "generated_at": self.generated_at}
