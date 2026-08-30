from pprint import pprint

from app.optimizer.rescue_optimizer import (
    optimize_rescue_plan,
)

from app.operations.execution import (
    create_operation_from_plan,
    get_operation,
)


print(
    "\nCreating optimized plan..."
)

plan = optimize_rescue_plan(
    1
)

print(
    "\nSaving plan as operation..."
)

operation_id = (
    create_operation_from_plan(
        plan
    )
)

print(
    f"\nCreated operation #{operation_id}"
)

print(
    "\nStored operation:"
)

operation = get_operation(
    operation_id
)

pprint(
    operation
)