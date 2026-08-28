import os

import requests
from dotenv import load_dotenv


load_dotenv()

ORS_API_KEY = os.getenv("ORS_API_KEY")

ORS_BASE_URL = "https://api.heigit.org/openrouteservice"


def get_route(origin_lat, origin_lon, destination_lat, destination_lon):
    """
    Get real driving distance and travel time using
    openrouteservice.

    Returns:
        distance_miles
        duration_minutes
    """

    if not ORS_API_KEY:
        raise RuntimeError(
            "ORS_API_KEY is missing. Add it to your .env file."
        )

    url = (
        f"{ORS_BASE_URL}/v2/directions/"
        "driving-car"
    )

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "coordinates": [
            [origin_lon, origin_lat],
            [destination_lon, destination_lat],
        ]
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    route = data["routes"][0]["summary"]

    distance_meters = route["distance"]
    duration_seconds = route["duration"]

    distance_miles = distance_meters / 1609.344
    duration_minutes = duration_seconds / 60

    return {
        "distance_miles": round(distance_miles, 2),
        "duration_minutes": round(duration_minutes, 2),
    }
    
if __name__ == "__main__":
    route = get_route(
        origin_lat=35.3859,
        origin_lon=-94.3985,
        destination_lat=35.3733,
        destination_lon=-94.4233,
    )

    print(route)