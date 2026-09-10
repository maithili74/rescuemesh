from pathlib import Path

import subprocess
import sys

from app.database.db import (
    get_connection,
)


# rescuemesh/
PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


def _get_demo_counts():
    """
    Return the current dynamic RescueMesh database counts.

    These tables should be empty immediately after
    a successful demo reset.
    """

    conn = get_connection()

    try:

        tables = [
            "operations",
            "driver_routes",
            "delivery_stops",
            "events",
            "escalations",
        ]

        counts = {}

        for table in tables:

            row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {table}
                """
            ).fetchone()

            counts[
                table
            ] = int(
                row[0]
            )

        return counts

    finally:
        conn.close()


def reset_demo_environment():
    """
    Reset RescueMesh to its deterministic seeded
    demo state.

    Uses the same trusted seed module that is used
    from the command line:

        python -m app.database.seed

    This intentionally resets only the SQLite
    application state.

    It does NOT modify:
    - AWS resources
    - .env
    - source code
    - evaluation/results.json
    - evaluation/scenario_results.json
    """

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.database.seed",
        ],

        cwd=str(
            PROJECT_ROOT
        ),

        capture_output=True,
        text=True,
    )

    if (
        result.returncode
        !=
        0
    ):

        error_message = (
            result.stderr.strip()
            or
            result.stdout.strip()
            or
            "Unknown database reset error."
        )

        raise RuntimeError(
            "Demo reset failed: "
            f"{error_message}"
        )

    counts = (
        _get_demo_counts()
    )

    expected_empty = [
        "operations",
        "driver_routes",
        "delivery_stops",
        "events",
        "escalations",
    ]

    not_empty = {
        table:
            counts[
                table
            ]

        for table
        in expected_empty

        if (
            counts[
                table
            ]
            !=
            0
        )
    }

    if not_empty:

        raise RuntimeError(
            "Demo reset completed, but dynamic "
            f"tables were not empty: {not_empty}"
        )

    return {
        "status":
            "ready",

        "message":
            (
                "RescueMesh has been restored "
                "to the clean seeded demo state."
            ),

        "counts":
            counts,
    }