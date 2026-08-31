from enum import Enum


class EventType(str, Enum):
    """
    Events RescueMesh currently knows how to respond to.
    """

    # Normal rescue lifecycle
    DONATION_CREATED = "DONATION_CREATED"
    DRIVER_ACCEPTED = "DRIVER_ACCEPTED"
    PICKUP_COMPLETED = "PICKUP_COMPLETED"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"

    # Disruptions
    DRIVER_CANCELLED = "DRIVER_CANCELLED"
    PANTRY_CAPACITY_CHANGED = "PANTRY_CAPACITY_CHANGED"


SUPPORTED_EVENT_TYPES = {
    event.value
    for event in EventType
}