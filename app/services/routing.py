import os
import time
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
    
    
def get_route_matrix(locations):
    """
    Get real road distances and travel times between
    multiple coordinates using openrouteservice Matrix API.

    Accepted location formats:

    [
        (latitude, longitude),
        (latitude, longitude),
    ]

    or:

    [
        {
            "latitude": 36.1627,
            "longitude": -86.7816,
        },
        ...
    ]

    ORS expects coordinates in:
        [longitude, latitude]
    """

    if not ORS_API_KEY:
        raise RuntimeError(
            "ORS_API_KEY is missing. Add it to your .env file."
        )

    url = f"{ORS_BASE_URL}/v2/matrix/driving-car"

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }

    coordinates = []

    for location in locations:

        # ---------------------------------------------
        # Dictionary format
        # ---------------------------------------------
        if isinstance(location, dict):

            latitude = location.get("latitude")
            longitude = location.get("longitude")

        # ---------------------------------------------
        # Tuple/list format
        # ---------------------------------------------
        elif (
            isinstance(location, (tuple, list))
            and len(location) == 2
        ):

            latitude = location[0]
            longitude = location[1]

        else:

            raise ValueError(
                f"Invalid location format: {location}"
            )

        if latitude is None or longitude is None:

            raise ValueError(
                f"Location is missing latitude or longitude: "
                f"{location}"
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)

        except (TypeError, ValueError):

            raise ValueError(
                f"Invalid latitude/longitude values: "
                f"{location}"
            )

        # ORS requires longitude FIRST.
        coordinates.append(
            [
                longitude,
                latitude,
            ]
        )

    if len(coordinates) < 2:
        raise ValueError(
            "Route matrix requires at least two locations."
        )

    payload = {
        "locations": coordinates,
        "metrics": [
            "distance",
            "duration",
        ],
        "units": "mi",
    }

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            # Do not retry invalid requests.
            if 400 <= response.status_code < 500:
                response.raise_for_status()

            # Retry temporary ORS/server failures.
            if response.status_code >= 500:

                if attempt == max_attempts:
                    response.raise_for_status()

                time.sleep(attempt)
                continue

            response.raise_for_status()
            break

        except requests.exceptions.Timeout:

            if attempt == max_attempts:
                raise

            time.sleep(attempt)

        except requests.exceptions.ConnectionError:

            if attempt == max_attempts:
                raise

            time.sleep(attempt)

    data = response.json()

    distances = data["distances"]
    durations_seconds = data["durations"]

    durations_minutes = []

    for row in durations_seconds:

        converted_row = []

        for value in row:

            if value is None:
                converted_row.append(None)

            else:
                converted_row.append(
                    value / 60
                )

        durations_minutes.append(
            converted_row
        )

    return {
        "distances_miles":
            distances,

        "durations_minutes":
            durations_minutes,
    }
    
if __name__ == "__main__":
    route = get_route(
        origin_lat=35.3859,
        origin_lon=-94.3985,
        destination_lat=35.3733,
        destination_lon=-94.4233,
    )

    print(route)