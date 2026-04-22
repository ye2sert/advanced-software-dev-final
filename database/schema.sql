
PRAGMA foreign_keys = ON;


-- Location: each office/city

CREATE TABLE IF NOT EXISTS locations (
    location_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    city          TEXT NOT NULL UNIQUE,
    address       TEXT NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);


-- Users: staff accounts with role-based access

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    role          TEXT NOT NULL CHECK (role IN
                   ('FrontDesk','FinanceManager','MaintenanceStaff','Administrator','Manager')),
    location_id   INTEGER,
    active        INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login    TEXT,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);


-- Tenants: residents / applicants

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ni_number     TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    phone         TEXT NOT NULL,
    email         TEXT NOT NULL,
    occupation    TEXT,
    tenant_references TEXT,
    location_id   INTEGER NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by    INTEGER,
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);


-- Apartments

CREATE TABLE IF NOT EXISTS apartments (
    apartment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id   INTEGER NOT NULL,
    apt_number    TEXT NOT NULL,
    apt_type      TEXT NOT NULL,           -- studio, 1-bed, 2-bed, 3-bed
    bedrooms      INTEGER NOT NULL,
    monthly_rent  REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Available'
                  CHECK (status IN ('Available','Occupied','Maintenance','Reserved')),
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (location_id, apt_number),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);


-- Leases: binds tenant ↔ apartment

CREATE TABLE IF NOT EXISTS leases (
    lease_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     INTEGER NOT NULL,
    apartment_id  INTEGER NOT NULL,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    deposit       REAL NOT NULL,
    monthly_rent  REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Active'
                  CHECK (status IN ('Active','Terminated','Expired')),
    termination_reason TEXT,
    penalty_amount REAL DEFAULT 0,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY (apartment_id) REFERENCES apartments(apartment_id)
);


-- Invoices

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id      INTEGER NOT NULL,
    amount        REAL NOT NULL,
    issue_date    TEXT NOT NULL,
    due_date      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Pending'
                  CHECK (status IN ('Pending','Paid','Overdue','PartiallyPaid')),
    late_fee      REAL DEFAULT 0,
    FOREIGN KEY (lease_id) REFERENCES leases(lease_id)
);


-- Payments

CREATE TABLE IF NOT EXISTS payments (
    payment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL,
    amount        REAL NOT NULL,
    payment_date  TEXT NOT NULL,
    method        TEXT NOT NULL,
    recorded_by   INTEGER,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY (recorded_by) REFERENCES users(user_id)
);


-- Maintenance Requests

CREATE TABLE IF NOT EXISTS maintenance_requests (
    request_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL,
    tenant_id     INTEGER,
    description   TEXT NOT NULL,
    priority      TEXT NOT NULL DEFAULT 'Medium'
                  CHECK (priority IN ('Low','Medium','High','Critical')),
    status        TEXT NOT NULL DEFAULT 'Open'
                  CHECK (status IN ('Open','InProgress','Resolved','Cancelled')),
    reported_date TEXT NOT NULL,
    resolved_date TEXT,
    assigned_to   INTEGER,
    time_taken_hours REAL,
    cost          REAL DEFAULT 0,
    resolution_notes TEXT,
    reported_by   INTEGER,
    FOREIGN KEY (apartment_id) REFERENCES apartments(apartment_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    FOREIGN KEY (assigned_to) REFERENCES users(user_id),
    FOREIGN KEY (reported_by) REFERENCES users(user_id)
);


-- Audit log (non-functional: security)

CREATE TABLE IF NOT EXISTS audit_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    action        TEXT NOT NULL,
    entity_type   TEXT,
    entity_id     INTEGER,
    details       TEXT,
    timestamp     TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);


-- Indexes for performance

CREATE INDEX IF NOT EXISTS idx_tenants_location  ON tenants(location_id);
CREATE INDEX IF NOT EXISTS idx_apts_location     ON apartments(location_id);
CREATE INDEX IF NOT EXISTS idx_apts_status       ON apartments(status);
CREATE INDEX IF NOT EXISTS idx_leases_tenant     ON leases(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leases_apt        ON leases(apartment_id);
CREATE INDEX IF NOT EXISTS idx_leases_status     ON leases(status);
CREATE INDEX IF NOT EXISTS idx_invoices_lease    ON invoices(lease_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status   ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_maint_status      ON maintenance_requests(status);
CREATE INDEX IF NOT EXISTS idx_maint_apt         ON maintenance_requests(apartment_id);
