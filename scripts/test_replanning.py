from pprint import pprint

from app.optimizer.rescue_optimizer import (
    optimize_rescue_plan,
)

from app.operations.execution import (
    create_operation_from_plan,
    start_operation,
    get_operation,
    cancel_driver_and_replan,
)


print(
    "\n"
    + "=" * 70
)

print(
    "STEP 1 - CREATE ORIGINAL PLAN"
)

print(
    "=" * 70
)

plan = optimize_rescue_plan(
    9
)

pprint(
    plan
)


print(
    "\n"
    + "=" * 70
)

print(
    "STEP 2 - SAVE OPERATION"
)

print(
    "=" * 70
)

operation_id = (
    create_operation_from_plan(
        plan
    )
)

print(
    "Operation:",
    operation_id
)


print(
    "\n"
    + "=" * 70
)

print(
    "STEP 3 - ACTIVATE + RESERVE RESOURCES"
)

print(
    "=" * 70
)

start_operation(
    operation_id
)

operation = get_operation(
    operation_id
)

pprint(
    operation
)


# Original Donation #9 should normally choose James.
driver_id = (
    operation[
        "driver_routes"
    ][0][
        "driver_id"
    ]
)

driver_name = (
    operation[
        "driver_routes"
    ][0][
        "driver_name"
    ]
)


print(
    "\n"
    + "=" * 70
)

print(
    f"STEP 4 - SIMULATE "
    f"{driver_name.upper()} CANCELLATION"
)

print(
    "=" * 70
)

result = (
    cancel_driver_and_replan(
        operation_id,
        driver_id,
    )
)

pprint(
    result
)


print(
    "\n"
    + "=" * 70
)

print(
    "OLD OPERATION"
)

print(
    "=" * 70
)

pprint(
    get_operation(
        operation_id
    )
)


if (
    result["status"]
    ==
    "replanned"
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "NEW REPLACEMENT OPERATION"
    )

    print(
        "=" * 70
    )

    pprint(
        get_operation(
            result[
                "new_operation_id"
            ]
        )
    )