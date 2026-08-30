import sqlite3
from pathlib import Path

DB_PATH = Path("data/rescuemesh.db")


def get_connection():
    """
    Create and return a SQLite database connection.

    Foreign key enforcement is enabled so relationships like:

        operations -> donations
        driver_routes -> operations
        delivery_stops -> driver_routes

    are actually enforced by SQLite.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = (
        sqlite3.Row
    )

    # SQLite does not enforce foreign keys by default.
    # Enable them for every new connection.
    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def create_tables():
    """
    Create the core RescueMesh database tables.
    """

    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------
    # DONORS
    # -----------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
        """
    )

    # -----------------------------
    # PANTRIES
    # -----------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pantries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            max_capacity_lbs REAL NOT NULL,
            available_capacity_lbs REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
        )
        """
    )

    # -----------------------------
    # PANTRY NEEDS
    # -----------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pantry_needs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pantry_id INTEGER NOT NULL,
            food_type TEXT NOT NULL,
            need_score REAL NOT NULL,
            FOREIGN KEY (pantry_id) REFERENCES pantries(id)
        )
        """
    )

    # -----------------------------
    # DRIVERS
    # -----------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            capacity_lbs REAL NOT NULL,
            available_from TEXT NOT NULL,
            available_until TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
        )
        """
    )

    # -----------------------------
    # DONATIONS
    # -----------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER NOT NULL,
            food_type TEXT NOT NULL,
            quantity_lbs REAL NOT NULL,
            available_at TEXT NOT NULL,
            pickup_deadline TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            FOREIGN KEY (donor_id) REFERENCES donors(id)
        )
        """
    )
    
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            donation_id INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'planned',

            rescued_lbs REAL NOT NULL,
            unrescued_lbs REAL NOT NULL,
            rescue_rate REAL NOT NULL,

            total_distance_miles REAL NOT NULL,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (donation_id)
                REFERENCES donations(id)
        );


        CREATE TABLE IF NOT EXISTS driver_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            operation_id INTEGER NOT NULL,
            driver_id INTEGER NOT NULL,

            assigned_lbs REAL NOT NULL,

            pickup_start TEXT NOT NULL,
            pickup_complete TEXT NOT NULL,

            route_complete TEXT NOT NULL,

            distance_miles REAL NOT NULL,

            status TEXT NOT NULL
                DEFAULT 'assigned',

            FOREIGN KEY (operation_id)
                REFERENCES operations(id)
                ON DELETE CASCADE,

            FOREIGN KEY (driver_id)
                REFERENCES drivers(id)
        );


        CREATE TABLE IF NOT EXISTS delivery_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            route_id INTEGER NOT NULL,
            pantry_id INTEGER NOT NULL,

            stop_order INTEGER NOT NULL,

            quantity_lbs REAL NOT NULL,

            eta TEXT NOT NULL,

            status TEXT NOT NULL
                DEFAULT 'pending',

            FOREIGN KEY (route_id)
                REFERENCES driver_routes(id)
                ON DELETE CASCADE,

            FOREIGN KEY (pantry_id)
                REFERENCES pantries(id)
        );


        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            operation_id INTEGER NOT NULL,

            event_type TEXT NOT NULL,

            details TEXT,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (operation_id)
                REFERENCES operations(id)
                ON DELETE CASCADE
        );
        """
    )

    conn.commit()
    conn.close()
    
def get_donation_by_id(donation_id):
    conn = get_connection()

    donation = conn.execute(
        """
        SELECT
            donations.id,
            donations.food_type,
            donations.quantity_lbs,
            donations.available_at,
            donations.pickup_deadline,
            donations.status,

            donors.name AS donor_name,
            donors.location AS donor_location,
            donors.latitude AS donor_latitude,
            donors.longitude AS donor_longitude

        FROM donations
        JOIN donors
            ON donations.donor_id = donors.id

        WHERE donations.id = ?
        """,
        (donation_id,),
    ).fetchone()

    conn.close()

    return dict(donation) if donation else None


def get_compatible_pantries(donation_id):
    """
    Return pantries that:
    - accept this donation's food type
    - are available
    - have remaining capacity
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            p.id,
            p.name,
            p.location,
            p.latitude,
            p.longitude,
            p.available_capacity_lbs,
            pn.need_score,
            pn.food_type
        FROM donations d

        JOIN pantry_needs pn
            ON pn.food_type = d.food_type

        JOIN pantries p
            ON p.id = pn.pantry_id

        WHERE d.id = ?
          AND p.status = 'available'
          AND p.available_capacity_lbs > 0

        ORDER BY pn.need_score DESC
        """,
        (donation_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_eligible_drivers(donation_id):
    """
    Return drivers whose availability overlaps the donation window.

    For now we use a simple rule:
    driver must be available at or before the pickup deadline,
    and must remain available after the donation becomes available.

    Later we will add travel-time constraints.
    """

    conn = get_connection()

    rows = conn.execute(
    """
    SELECT
        dr.id,
        dr.name,
        dr.location,
        dr.latitude,
        dr.longitude,
        dr.capacity_lbs,
        dr.available_from,
        dr.available_until,
        dr.status

        FROM drivers dr
        JOIN donations d
        ON d.id = ?

    WHERE dr.status = 'available'
      AND dr.available_from < d.pickup_deadline
      AND dr.available_until > d.available_at

    ORDER BY dr.capacity_lbs DESC
    """,
    (donation_id,),
).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_network_state(donation_id):
    """
    Build the complete current state needed to plan
    a rescue operation.
    """

    donation = get_donation_by_id(donation_id)

    if donation is None:
        return None

    return {
        "donation": donation,
        "compatible_pantries": get_compatible_pantries(donation_id),
        "eligible_drivers": get_eligible_drivers(donation_id),
    }


if __name__ == "__main__":
    create_tables()
    print("RescueMesh database tables created successfully.")