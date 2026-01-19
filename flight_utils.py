"""
Flight Event Utilities
Simple flight detection and summary generation for tracking events
"""

from typing import List, Dict, Any, Optional
import re


def is_flight_event(event: Dict[str, Any]) -> bool:
    """
    Check if an event is a flight event.
    Simple detection: if "flight" appears in the location field (case-insensitive).

    Args:
        event: A tracking event dictionary with optional 'location' field

    Returns:
        True if the event is a flight event, False otherwise
    """
    location = event.get("location") or ""
    return "flight" in location.lower()


def filter_flight_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter events to only include flight events.

    Args:
        events: List of tracking event dictionaries

    Returns:
        List of events where "flight" appears in the location field
    """
    return [event for event in events if is_flight_event(event)]


def extract_flight_info(location: str) -> Optional[Dict[str, Any]]:
    """
    Extract flight information from a location string.
    Attempts to parse flight number, airline, origin, and destination.

    Args:
        location: The location string containing flight information

    Returns:
        Dictionary with flightNumber, airline, origin, destination or None if parsing fails
    """
    if not location:
        return None

    # Try to extract flight number (common patterns: XX123, XX1234, XXX123)
    flight_number_match = re.search(r'\b([A-Z]{2,3}\d{1,4})\b', location.upper())
    flight_number = flight_number_match.group(1) if flight_number_match else None

    # Try to extract airline name (before "flight" or at the beginning)
    airline = None
    airline_match = re.search(r'^([A-Za-z\s]+?)(?:\s+flight|\s+FL)', location, re.IGNORECASE)
    if airline_match:
        airline = airline_match.group(1).strip()

    # Try to extract origin and destination (patterns like "from X to Y" or "X - Y")
    origin = None
    destination = None

    # Pattern: "from X to Y"
    from_to_match = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+)', location, re.IGNORECASE)
    if from_to_match:
        origin = from_to_match.group(1).strip()
        destination = from_to_match.group(2).strip()
    else:
        # Pattern: "X - Y" or "X to Y"
        route_match = re.search(r'([A-Za-z]{3})\s*[-–]\s*([A-Za-z]{3})', location)
        if route_match:
            origin = route_match.group(1).strip()
            destination = route_match.group(2).strip()

    return {
        "flightNumber": flight_number,
        "airline": airline,
        "origin": origin,
        "destination": destination
    }


def generate_flight_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a flight summary from tracking events.

    Args:
        events: List of tracking event dictionaries

    Returns:
        Dictionary with:
        - hasFlightEvents: boolean indicating if any flight events exist
        - flightEventCount: number of flight events
        - flights: array of unique flight information
    """
    flight_events = filter_flight_events(events)

    # Extract unique flights
    flights = []
    seen_flights = set()

    for event in flight_events:
        location = event.get("location") or ""
        flight_info = extract_flight_info(location)

        if flight_info:
            # Use flight number as unique key, or location if no flight number
            key = flight_info.get("flightNumber") or location.lower()
            if key not in seen_flights:
                seen_flights.add(key)
                flights.append(flight_info)

    return {
        "hasFlightEvents": len(flight_events) > 0,
        "flightEventCount": len(flight_events),
        "flights": flights
    }
