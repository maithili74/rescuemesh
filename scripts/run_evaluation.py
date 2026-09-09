import json
import os
import sys
import time

from datetime import (
    datetime,
    timezone,
)

import pytest


class EvaluationCollector:

    def __init__(self):

        self.passed = set()
        self.failed = set()
        self.skipped = set()

    def pytest_runtest_logreport(
        self,
        report,
    ):

        node_id = report.nodeid

        if report.failed:

            self.failed.add(
                node_id
            )

            self.passed.discard(
                node_id
            )

            return

        if report.skipped:

            if (
                node_id
                not in self.failed
            ):

                self.skipped.add(
                    node_id
                )

            return

        if (
            report.when == "call"
            and
            report.passed
            and
            node_id not in self.failed
            and
            node_id not in self.skipped
        ):

            self.passed.add(
                node_id
            )


def main():

    print()
    print(
        "=" * 60
    )

    print(
        "RESCUEMESH AUTOMATED EVALUATION"
    )

    print(
        "=" * 60
    )

    print()

    collector = (
        EvaluationCollector()
    )

    start_time = (
        time.perf_counter()
    )

    exit_code = pytest.main(
        [
            "tests",
            "-q",
        ],
        plugins=[
            collector
        ],
    )

    duration = (
        time.perf_counter()
        -
        start_time
    )

    passed = len(
        collector.passed
    )

    failed = len(
        collector.failed
    )

    skipped = len(
        collector.skipped
    )

    total = (
        passed
        +
        failed
        +
        skipped
    )

    pass_rate = (
        passed
        /
        total
        if total
        else 0
    )

    result = {
        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "total":
            total,

        "passed":
            passed,

        "failed":
            failed,

        "skipped":
            skipped,

        "pass_rate":
            round(
                pass_rate,
                4,
            ),

        "duration_seconds":
            round(
                duration,
                2,
            ),

        "pytest_exit_code":
            int(
                exit_code
            ),
    }

    os.makedirs(
        "evaluation",
        exist_ok=True,
    )

    output_path = os.path.join(
        "evaluation",
        "results.json",
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
        )

    print()
    print(
        "=" * 60
    )

    print(
        "EVALUATION RESULTS"
    )

    print(
        "=" * 60
    )

    print(
        f"Passed:  {passed}"
    )

    print(
        f"Failed:  {failed}"
    )

    print(
        f"Skipped: {skipped}"
    )

    print(
        f"Total:   {total}"
    )

    print(
        f"Pass rate: "
        f"{pass_rate * 100:.1f}%"
    )

    print(
        f"Duration: "
        f"{duration:.1f}s"
    )

    print()

    print(
        f"Saved to: "
        f"{output_path}"
    )

    print()

    return int(
        exit_code
    )


if __name__ == "__main__":

    sys.exit(
        main()
    )