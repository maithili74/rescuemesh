from enum import Enum


class EventType(str, Enum):
    """
    Events RescueMesh currently knows how to respond to.
    """

    DRIVER_CANCELLED = "DRIVER_CANCELLED"

    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"

    PANTRY_CAPACITY_CHANGED = (
        "PANTRY_CAPACITY_CHANGED"
    )


SUPPORTED_EVENT_TYPES = {
    event.value
    for event in EventType
}