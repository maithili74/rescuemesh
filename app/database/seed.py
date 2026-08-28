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
    donors = [
        # name, location label, latitude, longitude
        ("GreenMart #12", "Central District", 36.1627, -86.7816),
        ("Fresh Foods Market", "North District", 36.1880, -86.7900),
        ("Community Bakery", "West District", 36.1580, -86.8200),
        ("Harvest Market", "East District", 36.1670, -86.7450),
        ("Local Grill", "South District", 36.1300, -86.7800),
        ("Riverfront Grocery", "Central East", 36.1650, -86.7650),
        ("Sunrise Cafe", "Northwest", 36.1850, -86.8100),
        ("Metro Wholesale Foods", "Southeast", 36.1400, -86.7500),
    ]

    conn.executemany(
        """
        INSERT INTO donors (
            name,
            location,
            latitude,
            longitude
        )
        VALUES (?, ?, ?, ?)
        """,
        donors,
    )


# =========================================================
# PANTRIES
# =========================================================

def seed_pantries(conn):
    pantries = [
        # name, location, lat, lon,
        # max capacity, available capacity, status

        ("Hope Community Pantry",
         "Central District",
         36.1550, -86.7750,
         180, 180, "available"),

        ("River Valley Food Center",
         "North District",
         36.1950, -86.7850,
         100, 80, "available"),

        ("Community Care Pantry",
         "West District",
         36.1600, -86.8300,
         250, 250, "available"),

        ("Helping Hands Food Bank",
         "East District",
         36.1700, -86.7350,
         200, 160, "available"),

        # Edge case:
        # extremely high need later,
        # but only 40 lbs available capacity
        ("Neighborhood Relief Center",
         "South District",
         36.1250, -86.7900,
         120, 40, "available"),

        # Large capacity but lower produce need
        ("Northside Family Pantry",
         "North Central",
         36.2050, -86.7700,
         220, 200, "available"),

        # Specialized bakery/shelf-stable pantry
        ("St. Mary's Community Shelf",
         "Central West",
         36.1500, -86.8000,
         120, 100, "available"),

        # High-need pantry farther south
        ("Southside Outreach Center",
         "South East",
         36.1150, -86.7550,
         180, 150, "available"),
    ]

    conn.executemany(
        """
        INSERT INTO pantries (
            name,
            location,
            latitude,
            longitude,
            max_capacity_lbs,
            available_capacity_lbs,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
    drivers = [
        # name, location, lat, lon,
        # capacity, from, until, status

        ("Sarah",
         "Central District",
         36.1600, -86.7850,
         150, "10:00", "14:00", "available"),

        ("Mike",
         "North District",
         36.1900, -86.7950,
         100, "12:00", "16:00", "available"),

        ("Lisa",
         "West District",
         36.1550, -86.8150,
         120, "10:00", "17:00", "available"),

        # Large vehicle, but finishes early
        ("James",
         "East District",
         36.1750, -86.7400,
         200, "09:00", "13:00", "available"),

        # Small vehicle
        ("Priya",
         "South District",
         36.1300, -86.7850,
         80, "11:00", "15:00", "available"),

        # Starts later
        ("Daniel",
         "Central East",
         36.1650, -86.7700,
         100, "13:00", "18:00", "available"),

        # Useful for morning pickups
        ("Emily",
         "Northwest",
         36.1850, -86.8050,
         140, "09:00", "12:30", "available"),

        # Edge case: unavailable driver
        ("John",
         "West District",
         36.1600, -86.8250,
         100, "10:00", "14:00", "unavailable"),

        # Very small vehicle
        ("Aisha",
         "Central District",
         36.1500, -86.7700,
         60, "10:00", "14:00", "available"),

        # Large-capacity driver
        ("Carlos",
         "East District",
         36.1800, -86.7500,
         180, "11:00", "16:00", "available"),

        # Available only early
        ("Noah",
         "North District",
         36.2000, -86.8000,
         75, "08:00", "11:30", "available"),

        # Available only later
        ("Maya",
         "South East",
         36.1200, -86.7600,
         120, "14:00", "18:00", "available"),
    ]

    conn.executemany(
        """
        INSERT INTO drivers (
            name,
            location,
            latitude,
            longitude,
            capacity_lbs,
            available_from,
            available_until,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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