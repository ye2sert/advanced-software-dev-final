"""
PAMS - Automated test suite (unittest)
Author: Tahmid Ahmed
Covers:
- Model validation (data integrity)
- Password hashing (security)
- Auth login/logout + role-based access denial
- Tenant / Apartment / Lease lifecycle
- Billing: invoice, payment, late-fee rule
- Maintenance lifecycle + prioritisation
- Reports: occupancy, financial, maintenance cost
- SQL injection protection (negative test)
"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

# Make src importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from database import get_db, DatabaseManager  # noqa: E402
from seed import seed  # noqa: E402
from models import (  # noqa: E402
    Tenant, Apartment, Lease, MaintenanceRequest,
    FrontDeskStaff, Administrator, Manager,
)
from services import (  # noqa: E402
    hash_password, verify_password,
    AuthService, TenantService, ApartmentService,
    BillingService, MaintenanceService, ReportService,
    UserService, LocationService,
)


# =============================================================================
class BaseDBTest(unittest.TestCase):
    """Each test class gets its own fresh temp DB."""

    @classmethod
    def setUpClass(cls):
        # Use a temp file-based SQLite DB, not :memory:, because our
        # DatabaseManager is a singleton that opens its own connection.
        cls._tmp = tempfile.mkdtemp(prefix="pams_test_")
        cls.db_path = os.path.join(cls._tmp, "pams.db")
        # Reset singleton
        DatabaseManager._instance = None
        cls.db = get_db(cls.db_path)
        cls.db.initialise_schema(str(ROOT / "database" / "schema.sql"))
        cls.db.seed_if_empty(seed)
        cls.auth = AuthService(cls.db)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.close()
        except Exception:
            pass
        DatabaseManager._instance = None


# =============================================================================
class TestPasswordHashing(unittest.TestCase):
    def test_hash_is_deterministic_with_same_salt(self):
        h1, s = hash_password("secret")
        h2, _ = hash_password("secret", s)
        self.assertEqual(h1, h2)

    def test_different_salt_produces_different_hash(self):
        h1, _ = hash_password("secret")
        h2, _ = hash_password("secret")
        self.assertNotEqual(h1, h2)

    def test_verify_correct_password(self):
        h, s = hash_password("secret")
        self.assertTrue(verify_password("secret", h, s))

    def test_verify_wrong_password(self):
        h, s = hash_password("secret")
        self.assertFalse(verify_password("wrong", h, s))


# =============================================================================
class TestModelValidation(unittest.TestCase):
    def test_tenant_valid(self):
        t = Tenant(None, "AB123456C", "Jane Smith",
                   "+44 7700 900111", "jane@example.com",
                   "Teacher", "ref1", 1)
        self.assertEqual(t.ni_number, "AB123456C")

    def test_tenant_rejects_bad_ni(self):
        with self.assertRaises(ValueError):
            Tenant(None, "NOT_NI", "Jane", "+44 7000000000",
                   "j@x.com", "", "", 1)

    def test_tenant_rejects_bad_email(self):
        with self.assertRaises(ValueError):
            Tenant(None, "AB123456C", "Jane", "+44 7000000000",
                   "not-an-email", "", "", 1)

    def test_apartment_rejects_negative_rent(self):
        with self.assertRaises(ValueError):
            Apartment(None, 1, "A1", "Studio", 0, -500)

    def test_apartment_rejects_invalid_status(self):
        with self.assertRaises(ValueError):
            Apartment(None, 1, "A1", "Studio", 0, 500, status="Floating")

    def test_lease_end_before_start(self):
        with self.assertRaises(ValueError):
            Lease(None, 1, 1, "2026-06-01", "2026-05-01", 1000, 500)

    def test_lease_early_termination_penalty_is_5_percent(self):
        l = Lease(None, 1, 1, "2026-01-01", "2027-01-01", 1800, 900)
        self.assertAlmostEqual(l.calculate_early_termination_penalty(), 45.00)

    def test_maintenance_priority_validated(self):
        with self.assertRaises(ValueError):
            MaintenanceRequest(None, 1, None, "Kitchen leak", priority="Emergency")

    def test_maintenance_description_min_length(self):
        with self.assertRaises(ValueError):
            MaintenanceRequest(None, 1, None, "no", priority="Medium")

    def test_user_role_permissions_fronts_desk(self):
        fd = FrontDeskStaff(0, "fd", "Fd", "fd@x.co", 1)
        self.assertTrue(fd.can("tenant.register"))
        self.assertFalse(fd.can("report.financial"))

    def test_user_role_manager_has_everything_admin_has(self):
        m = Manager(0, "m", "M", "m@x.co", None)
        a = Administrator(0, "a", "A", "a@x.co", 1)
        self.assertTrue(a.permissions().issubset(m.permissions()))
        self.assertTrue(m.can("business.expand"))


# =============================================================================
class TestAuth(BaseDBTest):
    def test_login_success(self):
        u = self.auth.login("admin_bristol", "admin123")
        self.assertEqual(u.role_name(), "Administrator")

    def test_login_wrong_password_rejected(self):
        with self.assertRaises(PermissionError):
            self.auth.login("admin_bristol", "wrongpass")

    def test_login_nonexistent_user_rejected(self):
        with self.assertRaises(PermissionError):
            self.auth.login("no_such_user", "x")

    def test_logout_clears_current_user(self):
        self.auth.login("admin_bristol", "admin123")
        self.auth.logout()
        self.assertIsNone(self.auth.current_user)


# =============================================================================
class TestTenantFlow(BaseDBTest):
    def setUp(self):
        self.auth.logout()
        self.auth.login("frontdesk_bristol", "desk123")
        self.ts = TenantService(self.db, self.auth)

    def test_register_tenant(self):
        t = Tenant(None, "ZZ999999Z", "Test User",
                   "+44 7900 111222", "test@example.com",
                   "Student", "Refs", 1)
        tid = self.ts.register_tenant(t)
        self.assertGreater(tid, 0)

    def test_duplicate_ni_rejected(self):
        t = Tenant(None, "QQ111111Q", "Alice One", "+44 7000 000001",
                   "a@x.co", "", "", 1)
        self.ts.register_tenant(t)
        t2 = Tenant(None, "QQ111111Q", "Bob Two", "+44 7000 000002",
                    "b@x.co", "", "", 1)
        with self.assertRaises(ValueError):
            self.ts.register_tenant(t2)

    def test_finance_cannot_register_tenant(self):
        self.auth.logout()
        self.auth.login("finance_bristol", "finance123")
        t = Tenant(None, "YY111111Y", "Nina Test", "+44 7000 000003",
                   "n@x.co", "", "", 1)
        with self.assertRaises(PermissionError):
            TenantService(self.db, self.auth).register_tenant(t)


# =============================================================================
class TestLeaseFlow(BaseDBTest):
    def setUp(self):
        self.auth.logout()
        self.auth.login("admin_bristol", "admin123")
        self.asvc = ApartmentService(self.db, self.auth)

    def test_cannot_double_book_apartment(self):
        # find an occupied apt
        row = self.db.query_one(
            "SELECT * FROM apartments WHERE status='Occupied' LIMIT 1")
        l = Lease(None, 1, row["apartment_id"],
                  date.today().isoformat(),
                  (date.today() + timedelta(days=365)).isoformat(),
                  1000, 500)
        with self.assertRaises(ValueError):
            self.asvc.assign_to_tenant(l)

    def test_early_termination_applies_5pct_penalty(self):
        lease = self.db.query_one(
            "SELECT * FROM leases WHERE status='Active' LIMIT 1")
        expected = round(lease["monthly_rent"] * 0.05, 2)
        penalty = self.asvc.terminate_lease_early(lease["lease_id"], "Moving")
        self.assertAlmostEqual(penalty, expected)


# =============================================================================
class TestBilling(BaseDBTest):
    def setUp(self):
        self.auth.logout()
        self.auth.login("finance_bristol", "finance123")
        self.bsvc = BillingService(self.db, self.auth)

    def test_create_invoice_and_pay(self):
        lid = self.db.query_one(
            "SELECT lease_id FROM leases LIMIT 1")["lease_id"]
        iid = self.bsvc.create_invoice(
            lid, 500.0, date.today().isoformat(),
            (date.today() + timedelta(days=30)).isoformat())
        self.bsvc.record_payment(iid, 500.0)
        row = self.db.query_one("SELECT status FROM invoices WHERE invoice_id=?",
                                (iid,))
        self.assertEqual(row["status"], "Paid")

    def test_partial_payment_status(self):
        lid = self.db.query_one(
            "SELECT lease_id FROM leases LIMIT 1")["lease_id"]
        iid = self.bsvc.create_invoice(
            lid, 1000.0, date.today().isoformat(),
            (date.today() + timedelta(days=30)).isoformat())
        self.bsvc.record_payment(iid, 400.0)
        row = self.db.query_one("SELECT status FROM invoices WHERE invoice_id=?",
                                (iid,))
        self.assertEqual(row["status"], "PartiallyPaid")

    def test_negative_payment_rejected(self):
        lid = self.db.query_one(
            "SELECT lease_id FROM leases LIMIT 1")["lease_id"]
        iid = self.bsvc.create_invoice(
            lid, 100.0, date.today().isoformat(),
            (date.today() + timedelta(days=30)).isoformat())
        with self.assertRaises(ValueError):
            self.bsvc.record_payment(iid, -50.0)

    def test_late_fee_applied_to_overdue(self):
        lid = self.db.query_one(
            "SELECT lease_id FROM leases LIMIT 1")["lease_id"]
        past_due = (date.today() - timedelta(days=10)).isoformat()
        iid = self.bsvc.create_invoice(lid, 1000.0,
                                       (date.today() - timedelta(days=40)).isoformat(),
                                       past_due)
        notifs = self.bsvc.apply_late_fees()
        self.assertTrue(any(n["invoice_id"] == iid for n in notifs))
        row = self.db.query_one("SELECT * FROM invoices WHERE invoice_id=?",
                                (iid,))
        self.assertEqual(row["status"], "Overdue")
        self.assertAlmostEqual(row["late_fee"], 50.0)

    def test_maintenance_cannot_record_payment(self):
        self.auth.logout()
        self.auth.login("maintenance_bristol", "maint123")
        b = BillingService(self.db, self.auth)
        with self.assertRaises(PermissionError):
            b.record_payment(1, 100)


# =============================================================================
class TestMaintenance(BaseDBTest):
    def test_prioritisation_order(self):
        self.auth.logout()
        self.auth.login("maintenance_bristol", "maint123")
        msvc = MaintenanceService(self.db, self.auth)
        rows = msvc.prioritise_queue()
        priorities = [r["priority"] for r in rows]
        # Critical before High before Medium before Low
        order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        mapped = [order[p] for p in priorities]
        self.assertEqual(mapped, sorted(mapped))

    def test_resolve_maintenance(self):
        self.auth.logout()
        self.auth.login("maintenance_bristol", "maint123")
        msvc = MaintenanceService(self.db, self.auth)
        # get an open one
        row = self.db.query_one(
            "SELECT request_id FROM maintenance_requests WHERE status='Open' LIMIT 1")
        msvc.resolve(row["request_id"], 2.5, 120.0, "Fixed")
        updated = self.db.query_one(
            "SELECT status, cost, time_taken_hours FROM maintenance_requests "
            "WHERE request_id = ?", (row["request_id"],))
        self.assertEqual(updated["status"], "Resolved")
        self.assertEqual(updated["cost"], 120.0)

    def test_resolve_negative_cost_rejected(self):
        self.auth.logout()
        self.auth.login("maintenance_bristol", "maint123")
        msvc = MaintenanceService(self.db, self.auth)
        row = self.db.query_one(
            "SELECT request_id FROM maintenance_requests WHERE status='Open' LIMIT 1")
        with self.assertRaises(ValueError):
            msvc.resolve(row["request_id"], 1, -10, "bad")


# =============================================================================
class TestReports(BaseDBTest):
    def setUp(self):
        self.auth.logout()
        self.auth.login("manager", "manager123")
        self.rsvc = ReportService(self.db, self.auth)

    def test_occupancy_report_structure(self):
        r = self.rsvc.occupancy()
        self.assertIn("occupancy_rate", r)
        self.assertIn("rows", r)
        self.assertGreater(len(r["rows"]), 0)

    def test_financial_report_nonnegative(self):
        r = self.rsvc.financial()
        self.assertGreaterEqual(r["collected"], 0)
        self.assertGreaterEqual(r["pending"], 0)

    def test_front_desk_cannot_run_financial_report(self):
        self.auth.logout()
        self.auth.login("frontdesk_bristol", "desk123")
        r = ReportService(self.db, self.auth)
        with self.assertRaises(PermissionError):
            r.financial()


# =============================================================================
class TestSQLInjection(BaseDBTest):
    """Negative test: parameterised queries must defeat SQL injection."""

    def test_login_does_not_accept_sql_injection(self):
        with self.assertRaises(PermissionError):
            self.auth.login("' OR '1'='1", "' OR '1'='1")
        # Our users table should still have all rows
        c = self.db.query_one("SELECT COUNT(*) c FROM users")["c"]
        self.assertGreater(c, 0)


# =============================================================================
class TestUserService(BaseDBTest):
    def test_admin_can_create_user(self):
        self.auth.logout()
        self.auth.login("admin_bristol", "admin123")
        us = UserService(self.db, self.auth)
        uid = us.create_user("newstaff", "Pw123!", "New Staff",
                             "ns@pams.co.uk", "FrontDesk", 1)
        self.assertGreater(uid, 0)

    def test_frontdesk_cannot_create_user(self):
        self.auth.logout()
        self.auth.login("frontdesk_bristol", "desk123")
        us = UserService(self.db, self.auth)
        with self.assertRaises(PermissionError):
            us.create_user("x", "pw", "X", "x@x.co", "FrontDesk", 1)


# =============================================================================
class TestLocationExpansion(BaseDBTest):
    def test_manager_can_add_location(self):
        self.auth.logout()
        self.auth.login("manager", "manager123")
        ls = LocationService(self.db, self.auth)
        before = len(ls.list_locations())
        ls.add_location("Edinburgh", "1 Royal Mile")
        self.assertEqual(len(ls.list_locations()), before + 1)

    def test_admin_cannot_expand_business(self):
        self.auth.logout()
        self.auth.login("admin_bristol", "admin123")
        ls = LocationService(self.db, self.auth)
        with self.assertRaises(PermissionError):
            ls.add_location("Leeds", "x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
