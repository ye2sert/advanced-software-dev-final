"""
PAMS - Paragon Apartment Management System
Entry point.

Author: Yunus Sert (24015097)
"""
import os
import sys
from pathlib import Path

# Make sure our package dir is on PYTHONPATH regardless of CWD
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from database import get_db
from seed import seed
from ui import LoginWindow


def main():
    db_path = os.environ.get("PAMS_DB",
                             str(HERE.parent / "database" / "pams.db"))
    schema_path = HERE.parent / "database" / "schema.sql"

    # Ensure database directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = get_db(db_path)
    db.initialise_schema(str(schema_path))
    db.seed_if_empty(seed)

    LoginWindow().mainloop()


if __name__ == "__main__":
    main()
