import json
import os
import subprocess
import time

from datetime import (
    datetime,
    timezone,
)


SCENARIOS = [
    {
        "name":
            "Transport capacity shortage",

        "description":
            "Donation exceeds available driver capacity.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_partial_rescue_when_transport_capacity_is_insufficient"
            ),

        "expected_behavior":
            "Partial rescue",
    },

    {
        "name":
            "Pantry capacity shortage",

        "description":
            "Available pantry capacity cannot hold the full donation.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_partial_rescue_when_pantry_capacity_is_insufficient"
            ),

        "expected_behavior":
            "Partial rescue",
    },

    {
        "name":
            "Exact driver capacity",

        "description":
            "Driver capacity exactly matches the assigned food.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_driver_can_carry_exact_capacity"
            ),

        "expected_behavior":
            "Full rescue",
    },

    {
        "name":
            "Pickup at deadline boundary",

        "description":
            "Pickup completes exactly at the allowed deadline.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_pickup_completed_exactly_at_deadline_is_allowed"
            ),

        "expected_behavior":
            "Feasible",
    },

    {
        "name":
            "Multi-stop driver route",

        "description":
            "One driver serves multiple nearby pantries.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_one_driver_can_make_multiple_nearby_drops"
            ),

        "expected_behavior":
            "Multi-stop rescue",
    },

    {
        "name":
            "Driver shift violation",

        "description":
            "A route would finish after the driver's available shift.",

        "test":
            (
                "tests/test_optimizer.py::"
                "test_route_finishing_after_driver_shift_is_rejected"
            ),

        "expected_behavior":
            "Safe rejection",
    },
]


def run_test(
    test_path,
):
    start = time.perf_counter()

    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            test_path,
            "-q",
        ],
        capture_output=True,
        text=True,
    )

    duration = (
        time.perf_counter()
        -
        start
    )

    return {
        "passed":
            result.returncode == 0,

        "duration_seconds":
            round(
                duration,
                2,
            ),

        "output":
            result.stdout.strip(),

        "error":
            result.stderr.strip(),
    }


def main():

    print()
    print(
        "=" * 70
    )

    print(
        "RESCUEMESH SCENARIO BENCHMARK"
    )

    print(
        "=" * 70
    )

    results = []

    for number, scenario in enumerate(
        SCENARIOS,
        start=1,
    ):

        print()
        print(
            f"[{number}/{len(SCENARIOS)}] "
            f"{scenario['name']}"
        )

        print(
            f"Expected: "
            f"{scenario['expected_behavior']}"
        )

        test_result = run_test(
            scenario[
                "test"
            ]
        )

        status = (
            "PASS"
            if test_result[
                "passed"
            ]
            else "FAIL"
        )

        print(
            f"Result: {status}"
        )

        result = {
            "name":
                scenario["name"],

            "description":
                scenario[
                    "description"
                ],

            "expected_behavior":
                scenario[
                    "expected_behavior"
                ],

            "passed":
                test_result[
                    "passed"
                ],

            "duration_seconds":
                test_result[
                    "duration_seconds"
                ],
        }

        results.append(
            result
        )

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = (
        len(results)
        -
        passed
    )

    benchmark = {
        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "total_scenarios":
            len(results),

        "passed":
            passed,

        "failed":
            failed,

        "pass_rate":
            (
                passed
                /
                len(results)
                if results
                else 0
            ),

        "scenarios":
            results,
    }

    os.makedirs(
        "evaluation",
        exist_ok=True,
    )

    path = (
        "evaluation/"
        "scenario_results.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            benchmark,
            file,
            indent=2,
        )

    print()
    print(
        "=" * 70
    )

    print(
        "BENCHMARK SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Scenarios: "
        f"{len(results)}"
    )

    print(
        f"Passed:    "
        f"{passed}"
    )

    print(
        f"Failed:    "
        f"{failed}"
    )

    print()

    print(
        f"Saved to: {path}"
    )


if __name__ == "__main__":

    main()