from app.database.db import get_connection, create_tables


def clear_existing_data(conn):
    """
    Clear existing seed data and reset SQLite auto-increment IDs
    so our seeded IDs always start from 1.
    """
    cursor = conn.cursor()

    cursor.execute("DELETE FROM pantry_needs")
    cursor.execute("DELETE FROM donations")
    cursor.execute("DELETE FROM drivers")
    cursor.execute("DELETE FROM pantries")
    cursor.execute("DELETE FROM donors")

    # Reset AUTOINCREMENT counters
    cursor.execute(
        """
        DELETE FROM sqlite_sequence
        WHERE name IN (
            'pantry_needs',
            'donations',
            'drivers',
            'pantries',
            'donors'
        )
        """
    )

    conn.commit()


# =========================================================
# DONORS
# =========================================================

def seed_donors(conn):
    """
    8 simulated food donors representing common donor types.
    """

    donors = [
        ("GreenMart #12", "Downtown"),
        ("Fresh Foods Market", "Northside"),
        ("Community Bakery", "Westside"),
        ("Harvest Market", "Eastside"),
        ("Local Grill", "Southside"),
        ("Riverfront Grocery", "Downtown"),
        ("Sunrise Cafe", "Northside"),
        ("Metro Wholesale Foods", "Eastside"),
    ]

    conn.executemany(
        """
        INSERT INTO donors (name, location)
        VALUES (?, ?)
        """,
        donors,
    )


# =========================================================
# PANTRIES
# =========================================================

def seed_pantries(conn):
    """
    Pantries intentionally have different capacities.

    These differences allow us to test:
    - small vs large pantry capacity
    - nearly full pantries
    - splitting donations
    - high-need vs low-need allocation
    """

    pantries = [
        # name, location, max_capacity, available_capacity, status

        # P1: Good general-purpose pantry
        ("Hope Community Pantry", "Downtown", 180, 180, "available"),

        # P2: Smaller pantry
        ("River Valley Food Center", "Northside", 100, 80, "available"),

        # P3: Large pantry, but farther from some donors
        ("Community Care Pantry", "Westside", 250, 250, "available"),

        # P4: Medium-large food bank
        ("Helping Hands Food Bank", "Eastside", 200, 160, "available"),

        # P5: EDGE CASE - almost full, only 40 lbs currently available
        ("Neighborhood Relief Center", "Southside", 120, 40, "available"),

        # P6: Large available capacity but lower produce need
        ("Northside Family Pantry", "Northside", 220, 200, "available"),

        # P7: Specialized pantry
        ("St. Mary's Community Shelf", "Downtown", 120, 100, "available"),

        # P8: High-need pantry with moderate remaining capacity
        ("Southside Outreach Center", "Southside", 180, 150, "available"),
    ]

    conn.executemany(
        """
        INSERT INTO pantries (
            name,
            location,
            max_capacity_lbs,
            available_capacity_lbs,
            status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        pantries,
    )


# =========================================================
# PANTRY NEEDS
# =========================================================

def seed_pantry_needs(conn):
    """
    pantry_needs also represents which food types each pantry accepts.

    If a pantry has no record for a food type, we will treat that pantry
    as incompatible with that food type.

    need_score:
        0.0 -> almost no current need
        1.0 -> critical current need
    """

    needs = [

        # -------------------------------------------------
        # P1 - Hope Community Pantry
        # Strong need for produce
        # -------------------------------------------------
        (1, "produce", 0.95),
        (1, "dairy", 0.70),
        (1, "bakery", 0.55),
        (1, "shelf_stable", 0.75),

        # -------------------------------------------------
        # P2 - River Valley Food Center
        # Medium need, smaller capacity
        # -------------------------------------------------
        (2, "produce", 0.60),
        (2, "dairy", 0.85),
        (2, "shelf_stable", 0.70),

        # -------------------------------------------------
        # P3 - Community Care Pantry
        # Large capacity + high produce need
        # -------------------------------------------------
        (3, "produce", 0.90),
        (3, "prepared_food", 0.92),
        (3, "bakery", 0.80),
        (3, "shelf_stable", 0.65),

        # -------------------------------------------------
        # P4 - Helping Hands Food Bank
        # IMPORTANT EDGE CASE:
        # No prepared_food entry.
        # Therefore prepared food must NOT be assigned here.
        # -------------------------------------------------
        (4, "produce", 0.82),
        (4, "dairy", 0.95),
        (4, "bakery", 0.65),
        (4, "shelf_stable", 0.90),

        # -------------------------------------------------
        # P5 - Neighborhood Relief Center
        # Very high need BUT only 40 lbs available capacity.
        # Tests high need vs limited capacity.
        # -------------------------------------------------
        (5, "produce", 0.99),
        (5, "prepared_food", 0.95),
        (5, "dairy", 0.88),

        # -------------------------------------------------
        # P6 - Northside Family Pantry
        # High capacity but relatively low produce need.
        # Useful for high-need vs capacity/distance tradeoff.
        # -------------------------------------------------
        (6, "produce", 0.35),
        (6, "dairy", 0.60),
        (6, "prepared_food", 0.55),
        (6, "bakery", 0.50),
        (6, "shelf_stable", 0.65),

        # -------------------------------------------------
        # P7 - St. Mary's Community Shelf
        # SPECIALIZED PANTRY.
        # Accepts ONLY bakery and shelf-stable food.
        # -------------------------------------------------
        (7, "bakery", 0.96),
        (7, "shelf_stable", 0.90),

        # -------------------------------------------------
        # P8 - Southside Outreach Center
        # High community need.
        # -------------------------------------------------
        (8, "produce", 0.97),
        (8, "prepared_food", 0.90),
        (8, "dairy", 0.75),
        (8, "shelf_stable", 0.80),
    ]

    conn.executemany(
        """
        INSERT INTO pantry_needs (
            pantry_id,
            food_type,
            need_score
        )
        VALUES (?, ?, ?)
        """,
        needs,
    )


# =========================================================
# DRIVERS
# =========================================================

def seed_drivers(conn):
    """
    12 drivers with intentionally different:
    - vehicle capacities
    - availability windows
    - locations
    - statuses

    These allow us to create deadline conflicts,
    exact-capacity cases, cancellations, and shortages.
    """

    drivers = [

        # D1 - reliable mid-size driver
        ("Sarah", "Downtown", 150, "10:00", "14:00", "available"),

        # D2
        ("Mike", "Northside", 100, "12:00", "16:00", "available"),

        # D3
        ("Lisa", "Westside", 120, "10:00", "17:00", "available"),

        # D4 - high-capacity driver but ends early
        ("James", "Eastside", 200, "09:00", "13:00", "available"),

        # D5 - small vehicle
        ("Priya", "Southside", 80, "11:00", "15:00", "available"),

        # D6 - starts late
        ("Daniel", "Downtown", 100, "13:00", "18:00", "available"),

        # D7 - useful for tight morning deadlines
        ("Emily", "Northside", 140, "09:00", "12:30", "available"),

        # D8 - EDGE CASE: explicitly unavailable
        ("John", "Westside", 100, "10:00", "14:00", "unavailable"),

        # D9 - very small vehicle
        ("Aisha", "Downtown", 60, "10:00", "14:00", "available"),

        # D10 - large-capacity driver
        ("Carlos", "Eastside", 180, "11:00", "16:00", "available"),

        # D11 - available only early
        ("Noah", "Northside", 75, "08:00", "11:30", "available"),

        # D12 - starts very late
        ("Maya", "Southside", 120, "14:00", "18:00", "available"),
    ]

    conn.executemany(
        """
        INSERT INTO drivers (
            name,
            location,
            capacity_lbs,
            available_from,
            available_until,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        drivers,
    )


# =========================================================
# DONATIONS
# =========================================================

def seed_donations(conn):
    """
    Donations are deliberately designed to represent both
    normal scenarios and edge cases.
    """

    donations = [

        # -------------------------------------------------
        # Donation 1
        # NORMAL MULTI-PANTRY CASE
        # -------------------------------------------------
        # 200 lbs produce
        # Good first optimizer test.
        (1, "produce", 200, "11:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 2
        # DAIRY COMPATIBILITY
        # -------------------------------------------------
        (2, "dairy", 90, "10:30", "13:30", "available"),

        # -------------------------------------------------
        # Donation 3
        # EARLY DEADLINE
        # -------------------------------------------------
        # Tests drivers whose shifts end too late or begin too late.
        (3, "bakery", 60, "09:30", "12:00", "available"),

        # -------------------------------------------------
        # Donation 4
        # LARGE PRODUCE DONATION
        # -------------------------------------------------
        # Tests splitting across multiple pantries/drivers.
        (4, "produce", 300, "11:00", "15:00", "available"),

        # -------------------------------------------------
        # Donation 5
        # PREPARED FOOD COMPATIBILITY EDGE CASE
        # -------------------------------------------------
        # Not every pantry accepts prepared food.
        (5, "prepared_food", 250, "12:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 6
        # HIGH NEED VS DISTANCE / CAPACITY TRADEOFF
        # -------------------------------------------------
        (6, "produce", 200, "13:00", "15:30", "available"),

        # -------------------------------------------------
        # Donation 7
        # TIGHT DEADLINE
        # -------------------------------------------------
        # Only drivers available during a narrow window should qualify.
        (2, "dairy", 120, "11:30", "12:30", "available"),

        # -------------------------------------------------
        # Donation 8
        # LATE-DAY DONATION
        # -------------------------------------------------
        # Tests late-starting drivers such as Maya and Daniel.
        (8, "shelf_stable", 180, "14:00", "17:00", "available"),

        # -------------------------------------------------
        # Donation 9
        # DRIVER CANCELLATION DEMO SCENARIO
        # -------------------------------------------------
        # Initially solvable.
        # Later we'll simulate the selected driver cancelling.
        (1, "produce", 200, "11:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 10
        # HUMAN ESCALATION DEMO
        # -------------------------------------------------
        # Later we modify driver availability so only part of
        # this donation can be moved.
        (4, "produce", 200, "11:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 11
        # SMALL DONATION / EASY CASE
        # -------------------------------------------------
        (3, "bakery", 35, "10:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 12
        # LARGE SHELF-STABLE DONATION
        # -------------------------------------------------
        (8, "shelf_stable", 320, "10:00", "16:00", "available"),

        # -------------------------------------------------
        # Donation 13
        # SMALL PREPARED FOOD CASE
        # -------------------------------------------------
        (7, "prepared_food", 75, "11:00", "14:30", "available"),

        # -------------------------------------------------
        # Donation 14
        # PRODUCE BOUNDARY CASE
        # -------------------------------------------------
        # Useful later for exact capacity testing.
        (6, "produce", 150, "10:00", "14:00", "available"),

        # -------------------------------------------------
        # Donation 15
        # DAIRY LARGE CASE
        # -------------------------------------------------
        (2, "dairy", 220, "10:00", "15:00", "available"),

        # -------------------------------------------------
        # Donation 16
        # BAKERY SPECIALIZED-PANTRY TEST
        # -------------------------------------------------
        # St. Mary's should be highly attractive because bakery need is 0.96.
        (3, "bakery", 100, "11:00", "15:00", "available"),

        # -------------------------------------------------
        # Donation 17
        # LATE PREPARED FOOD
        # -------------------------------------------------
        (5, "prepared_food", 140, "14:00", "17:30", "available"),

        # -------------------------------------------------
        # Donation 18
        # LARGE PRODUCE STRESS CASE
        # -------------------------------------------------
        (8, "produce", 400, "10:30", "15:30", "available"),
    ]

    conn.executemany(
        """
        INSERT INTO donations (
            donor_id,
            food_type,
            quantity_lbs,
            available_at,
            pickup_deadline,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        donations,
    )


# =========================================================
# MAIN SEED FUNCTION
# =========================================================

def seed_database():
    create_tables()

    conn = get_connection()

    clear_existing_data(conn)

    seed_donors(conn)
    seed_pantries(conn)
    seed_pantry_needs(conn)
    seed_drivers(conn)
    seed_donations(conn)

    conn.commit()
    conn.close()

    print("RescueMesh expanded sample network inserted successfully.")


if __name__ == "__main__":
    seed_database()