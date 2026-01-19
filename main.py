"""
India Post Tracking Microservice
FastAPI application for tracking India Post shipments
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from tracker import IndiaPostTracker, TrackingResult
from flight_utils import filter_flight_events, generate_flight_summary

# API Tags for documentation
tags_metadata = [
    {
        "name": "Health",
        "description": "Health check endpoints for monitoring service status",
    },
    {
        "name": "Tracking",
        "description": "Track India Post shipments. Supports single and bulk tracking with optional flight event filtering.",
    },
]

# Initialize FastAPI app
app = FastAPI(
    title="India Post Tracking API",
    description="""
## India Post Shipment Tracking Microservice

Track India Post shipments by scraping the official MIS CEPT tracking portal.

### Features

- **Single Tracking**: Track individual shipments by tracking number
- **Bulk Tracking**: Track up to 10 shipments simultaneously
- **Flight Event Filtering**: Filter to show only flight/air transport events
- **Flight Summary**: Get extracted flight information (flight number, airline, route)
- **Demo Mode**: Test integration with mock data

### Flight Detection

Flight events are detected when the event's `location` field contains "Flight".
Example location: `Flight - AI0187 (DEL to YYZ)`

The API extracts:
- Flight number (e.g., AI0187)
- Airline code (e.g., AI = Air India)
- Origin airport (e.g., DEL)
- Destination airport (e.g., YYZ)

### Tracking Number Format

India Post tracking numbers follow the format: `XX123456789XX`
- Example: `LP951627598IN`
- 2 letters + 9 digits + 2 letters (country code)
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "API Support",
        "url": "https://github.com/Aranhav/indiapost-tracker-service",
    },
    license_info={
        "name": "MIT",
    },
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for running sync scraper in async context
executor = ThreadPoolExecutor(max_workers=5)


def get_tracker() -> IndiaPostTracker:
    """Create a fresh tracker instance for each request"""
    return IndiaPostTracker(timeout=30)


# Pydantic Models for API
class TrackingEvent(BaseModel):
    """Individual tracking event from shipment history"""
    date: str = Field(..., description="Event date", example="11-01-2026")
    time: str = Field(..., description="Event time", example="07:27:00")
    office: str = Field(..., description="Post office name", example="DIMC NEW DELHI")
    event: str = Field(..., description="Event description", example="Aircraft take off")
    location: Optional[str] = Field(None, description="Location details, may contain flight info", example="Flight - AI0187 (DEL to YYZ)")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "11-01-2026",
                "time": "07:27:00",
                "office": "DIMC NEW DELHI",
                "event": "Aircraft take off",
                "location": "Flight - AI0187 (DEL to YYZ)"
            }
        }


class FlightInfo(BaseModel):
    """Extracted flight information from tracking events"""
    flightNumber: Optional[str] = Field(None, description="Flight number", example="AI0187")
    airline: Optional[str] = Field(None, description="Airline code", example="AI")
    origin: Optional[str] = Field(None, description="Origin airport code", example="DEL")
    destination: Optional[str] = Field(None, description="Destination airport code", example="YYZ")

    class Config:
        json_schema_extra = {
            "example": {
                "flightNumber": "AI0187",
                "airline": "AI",
                "origin": "DEL",
                "destination": "YYZ"
            }
        }


class FlightSummary(BaseModel):
    """Summary of flight events for a shipment"""
    hasFlightEvents: bool = Field(..., description="Whether shipment has any flight events", example=True)
    flightEventCount: int = Field(..., description="Number of flight-related events", example=5)
    flights: List[FlightInfo] = Field(default=[], description="List of unique flights used for this shipment")

    class Config:
        json_schema_extra = {
            "example": {
                "hasFlightEvents": True,
                "flightEventCount": 5,
                "flights": [
                    {
                        "flightNumber": "AI0187",
                        "airline": "AI",
                        "origin": "DEL",
                        "destination": "YYZ"
                    }
                ]
            }
        }


class TrackingResponse(BaseModel):
    """Response for tracking request"""
    success: bool = Field(..., description="Whether tracking was successful", example=True)
    tracking_number: str = Field(..., description="The tracking number queried", example="LP951627598IN")
    status: str = Field(..., description="Current shipment status", example="Delivered")
    events: List[Dict[str, Any]] = Field(default=[], description="List of tracking events (filtered if flightOnly=true)")
    origin: Optional[str] = Field(None, description="Origin country/location", example="India")
    destination: Optional[str] = Field(None, description="Destination country/location", example="Canada")
    booked_on: Optional[str] = Field(None, description="Booking date", example="08-01-2026")
    delivered_on: Optional[str] = Field(None, description="Delivery date (if delivered)", example="16-01-2026")
    article_type: Optional[str] = Field(None, description="Type of shipment", example="Letter Post")
    error: Optional[str] = Field(None, description="Error message if tracking failed", example=None)
    source: Optional[str] = Field(None, description="Data source", example="MIS CEPT")
    flightSummary: Optional[FlightSummary] = Field(None, description="Summary of flight events")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "tracking_number": "LP951627598IN",
                "status": "Delivered",
                "events": [
                    {
                        "date": "11-01-2026",
                        "time": "07:27:00",
                        "office": "DIMC NEW DELHI",
                        "event": "Aircraft take off",
                        "location": "Flight - AI0187 (DEL to YYZ)"
                    }
                ],
                "origin": "India",
                "destination": "Canada",
                "booked_on": "08-01-2026",
                "delivered_on": "16-01-2026",
                "article_type": "Letter Post",
                "error": None,
                "source": "MIS CEPT",
                "flightSummary": {
                    "hasFlightEvents": True,
                    "flightEventCount": 5,
                    "flights": [
                        {
                            "flightNumber": "AI0187",
                            "airline": "AI",
                            "origin": "DEL",
                            "destination": "YYZ"
                        }
                    ]
                },
                "timestamp": "2026-01-19T14:30:00.000000"
            }
        }


class BulkTrackingRequest(BaseModel):
    """Request body for bulk tracking"""
    tracking_numbers: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of tracking numbers to track (max 10)",
        example=["LP951627598IN", "LP951629165IN"]
    )
    demo: bool = Field(False, description="Use demo mode for testing (returns mock data)")
    flightOnly: bool = Field(False, description="Filter events to only show flight events")

    class Config:
        json_schema_extra = {
            "example": {
                "tracking_numbers": ["LP951627598IN", "LP951629165IN"],
                "demo": False,
                "flightOnly": False
            }
        }


class BulkTrackingResponse(BaseModel):
    """Response for bulk tracking request"""
    success: bool = Field(..., description="Whether all trackings were successful", example=True)
    results: List[TrackingResponse] = Field(..., description="Tracking results for each number")
    total: int = Field(..., description="Total number of tracking numbers requested", example=2)
    successful: int = Field(..., description="Number of successful trackings", example=2)
    failed: int = Field(..., description="Number of failed trackings", example=0)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status", example="healthy")
    service: str = Field(..., description="Service name", example="India Post Tracking API")
    version: str = Field(..., description="API version", example="2.0.0")
    timestamp: str = Field(..., description="Current timestamp")


# Helper function to run sync tracker in async context
def _sync_track(tracking_number: str, demo_mode: bool = False) -> TrackingResult:
    """Synchronous tracking function for executor"""
    tracker = get_tracker()
    return tracker.track(tracking_number, demo_mode)


async def track_async(tracking_number: str, demo_mode: bool = False) -> TrackingResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _sync_track, tracking_number, demo_mode)


# API Endpoints
@app.get("/", response_model=HealthResponse, tags=["Health"])
async def root():
    """
    Root endpoint - returns service health status.

    Use this to verify the API is running.
    """
    return HealthResponse(
        status="healthy",
        service="India Post Tracking API",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns service status, version, and current timestamp.
    """
    return HealthResponse(
        status="healthy",
        service="India Post Tracking API",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get(
    "/track/{tracking_number}",
    response_model=TrackingResponse,
    tags=["Tracking"],
    summary="Track single shipment by path parameter",
    responses={
        200: {
            "description": "Tracking information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "tracking_number": "LP951627598IN",
                        "status": "Delivered",
                        "events": [],
                        "flightSummary": {
                            "hasFlightEvents": True,
                            "flightEventCount": 5,
                            "flights": []
                        }
                    }
                }
            }
        },
        404: {"description": "Tracking number not found"},
        500: {"description": "Internal server error"}
    }
)
async def track_shipment(
    tracking_number: str = Query(..., description="India Post tracking number", example="LP951627598IN"),
    demo: bool = Query(False, description="Use demo mode for testing (returns mock data)"),
    flightOnly: bool = Query(False, description="Filter to only return flight/air transport events"),
):
    """
    Track a single India Post shipment by tracking number.

    **Parameters:**
    - **tracking_number**: India Post tracking number (format: XX123456789XX, e.g., LP951627598IN)
    - **demo**: Set to `true` to get mock data for testing integration
    - **flightOnly**: Set to `true` to filter events and only return flight-related events

    **Flight Detection:**
    Events are considered flight events if their `location` field contains "Flight".

    **Response includes:**
    - Complete tracking history (or filtered if flightOnly=true)
    - Flight summary with extracted flight information
    - Shipment metadata (origin, destination, dates)

    **Example:**
    ```
    GET /track/LP951627598IN?flightOnly=true
    ```
    """
    try:
        result = await track_async(tracking_number, demo_mode=demo)

        # Generate flight summary from all events
        flight_summary_data = generate_flight_summary(result.events)
        flight_summary = FlightSummary(
            hasFlightEvents=flight_summary_data["hasFlightEvents"],
            flightEventCount=flight_summary_data["flightEventCount"],
            flights=[FlightInfo(**f) for f in flight_summary_data["flights"]]
        )

        # Filter events if flightOnly is requested
        events = filter_flight_events(result.events) if flightOnly else result.events

        return TrackingResponse(
            success=result.error is None,
            tracking_number=result.tracking_number,
            status=result.status,
            events=events,
            origin=result.origin,
            destination=result.destination,
            booked_on=result.booked_on,
            delivered_on=result.delivered_on,
            article_type=result.article_type,
            error=result.error,
            source=result.source,
            flightSummary=flight_summary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/track",
    response_model=TrackingResponse,
    tags=["Tracking"],
    summary="Track single shipment by query parameter",
    responses={
        200: {"description": "Tracking information retrieved successfully"},
        400: {"description": "Missing or invalid tracking number"},
        500: {"description": "Internal server error"}
    }
)
async def track_shipment_query(
    id: str = Query(..., description="India Post tracking number", example="LP951627598IN"),
    demo: bool = Query(False, description="Use demo mode for testing (returns mock data)"),
    flightOnly: bool = Query(False, description="Filter to only return flight/air transport events"),
):
    """
    Track a single India Post shipment using query parameter.

    **Parameters:**
    - **id**: India Post tracking number (format: XX123456789XX)
    - **demo**: Set to `true` to get mock data for testing
    - **flightOnly**: Set to `true` to filter and only return flight events

    **Example:**
    ```
    GET /track?id=LP951627598IN&flightOnly=true
    ```

    **Note:** Use `&` to separate multiple query parameters, not `?`
    """
    return await track_shipment(id, demo, flightOnly)


@app.post(
    "/track/bulk",
    response_model=BulkTrackingResponse,
    tags=["Tracking"],
    summary="Track multiple shipments at once",
    responses={
        200: {"description": "Bulk tracking completed"},
        400: {"description": "Invalid request body"},
        500: {"description": "Internal server error"}
    }
)
async def track_bulk_shipments(request: BulkTrackingRequest):
    """
    Track multiple India Post shipments simultaneously (max 10).

    **Request Body:**
    ```json
    {
        "tracking_numbers": ["LP951627598IN", "LP951629165IN"],
        "demo": false,
        "flightOnly": false
    }
    ```

    **Parameters:**
    - **tracking_numbers**: Array of tracking numbers (1-10 items)
    - **demo**: Use demo mode for all trackings
    - **flightOnly**: Filter events to only show flight events for all results

    **Response includes:**
    - Individual tracking results for each number
    - Flight summary for each shipment
    - Overall success/failure counts

    **Example with flight filter:**
    ```json
    {
        "tracking_numbers": ["LP951627598IN"],
        "flightOnly": true
    }
    ```
    """
    results = []
    successful = 0
    failed = 0

    # Process tracking numbers with concurrency limit
    tasks = [track_async(tn, demo_mode=request.demo) for tn in request.tracking_numbers]
    tracking_results = await asyncio.gather(*tasks, return_exceptions=True)

    for tn, result in zip(request.tracking_numbers, tracking_results):
        if isinstance(result, Exception):
            results.append(TrackingResponse(
                success=False,
                tracking_number=tn,
                status="Error",
                error=str(result),
            ))
            failed += 1
        else:
            is_success = result.error is None

            # Generate flight summary from all events
            flight_summary_data = generate_flight_summary(result.events)
            flight_summary = FlightSummary(
                hasFlightEvents=flight_summary_data["hasFlightEvents"],
                flightEventCount=flight_summary_data["flightEventCount"],
                flights=[FlightInfo(**f) for f in flight_summary_data["flights"]]
            )

            # Filter events if flightOnly is requested
            events = filter_flight_events(result.events) if request.flightOnly else result.events

            results.append(TrackingResponse(
                success=is_success,
                tracking_number=result.tracking_number,
                status=result.status,
                events=events,
                origin=result.origin,
                destination=result.destination,
                booked_on=result.booked_on,
                delivered_on=result.delivered_on,
                article_type=result.article_type,
                error=result.error,
                source=result.source,
                flightSummary=flight_summary,
            ))
            if is_success:
                successful += 1
            else:
                failed += 1

    return BulkTrackingResponse(
        success=failed == 0,
        results=results,
        total=len(request.tracking_numbers),
        successful=successful,
        failed=failed,
    )


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Run with: uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
