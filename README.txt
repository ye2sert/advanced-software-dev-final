PAMS — Paragon Apartment Management System
===================================================

Author: Yunus Sert (24015097), Mackenzie Sawers (24033341) and Tahmid Ahmed. (240180955)
Group: 37

1. Project folder layout
------------------------
    PAMS_Portfolio/
    |-- README.txt           <-- this file
    |-- src/                 <-- Python source code
    |   |-- main.py          <-- entry point
    |   |-- database.py      <-- DAO (SQLite wrapper, singleton)
    |   |-- models.py        <-- domain classes + validation
    |   |-- services.py      <-- business logic + permission gates
    |   |-- seed.py          <-- demo data loader
    |   |-- ui.py            <-- Tkinter GUI
    |-- database/
    |   |-- schema.sql       <-- tables, constraints, indexes
    |   |-- pams.db          <-- auto-created on first launch
    |-- tests/
    |   |-- test_pams.py     <-- 40 automated tests
    |   |-- screenshots/     <-- test-run evidence PNGs
    |-- diagrams/            <-- Use Case, Class, 5 x Sequence PNGs
    |-- docs/
    |   |-- Element1_Design.pdf
    |   |-- Element2_Methodology.pdf
    |   |-- Element3_Testing.pdf


2. Requirements
---------------
    * Python 3.10 or newer
    * Standard library only (sqlite3, tkinter, hashlib, dataclasses,
      unittest). No pip install required.


3. Running the application
--------------------------
    From the PAMS_Portfolio folder:

        python src/main.py

    The login window opens. The demo dataset is seeded automatically
    the first time the app runs (or whenever database/pams.db is
    missing).


4. Demo user accounts
---------------------
    | Role                 | Username             | Password    |
    | -------------------- | -------------------- | ----------- |
    | Administrator        | admin_bristol        | admin123    |
    | Front-desk Staff     | frontdesk_bristol    | desk123     |
    | Finance Manager      | finance_bristol      | finance123  |
    | Maintenance Staff    | maintenance_bristol  | maint123    |
    | Manager (director)   | manager              | manager123  |

    Each city (Cardiff / London / Manchester) has the same four
    admin/frontdesk/finance/maintenance accounts with its own city
    suffix (e.g. admin_cardiff). The single manager account can see
    all four cities.

    All passwords are stored as PBKDF2-HMAC-SHA256 hashes with per-user
    salts. The plaintexts above are for demonstration only.


5. Running the automated tests
------------------------------
    From the PAMS_Portfolio folder:

        python -m unittest discover -s tests -v

    Expected result: 40 tests, all passing, ~12 seconds.


6. Resetting the database
-------------------------
    Delete database/pams.db and database/pams.db-journal, then re-run
    the application or the tests. The schema is re-created from
    database/schema.sql and the demo dataset is re-seeded.


7. Key features to try in the demo
----------------------------------
    * Log in as frontdesk_bristol and register a new tenant with an
      invalid NI number (e.g. "NOT_NI") to see validation kick in.
    * Log in as finance_bristol, run "Apply Late Fees" in the Billing
      tab, and confirm overdue invoices rise by exactly 5%.
    * Log in as admin_bristol and terminate an active lease early to
      watch the 5% early-termination penalty invoice appear.
    * Log in as manager and run the three reports (Occupancy,
      Financial, Maintenance Cost) to see cross-city analytics.
