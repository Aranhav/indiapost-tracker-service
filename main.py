"""
India Post Tracking Microservice
FastAPI application for tracking India Post shipments
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from tracker import IndiaPostTracker, TrackingResult
from flight_utils import filter_flight_events, generate_flight_summary

# Initialize FastAPI app
app = FastAPI(
    title="India Post Tracking API",
    description="Microservice for tracking India Post shipments by scraping the official tracking portal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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
    date: str
    time: str
    office: str
    event: str
    location: Optional[str] = None


class FlightInfo(BaseModel):
    flightNumber: Optional[str] = None
    airline: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None


class FlightSummary(BaseModel):
    hasFlightEvents: bool
    flightEventCount: int
    flights: List[FlightInfo] = []


class TrackingResponse(BaseModel):
    success: bool
    tracking_number: str
    status: str
    events: List[Dict[str, Any]] = []
    origin: Optional[str] = None
    destination: Optional[str] = None
    booked_on: Optional[str] = None
    delivered_on: Optional[str] = None
    article_type: Optional[str] = None
    error: Optional[str] = None
    source: Optional[str] = None
    flightSummary: Optional[FlightSummary] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class BulkTrackingRequest(BaseModel):
    tracking_numbers: List[str] = Field(..., min_length=1, max_length=10)
    demo: bool = Field(False, description="Use demo mode for testing")
    flightOnly: bool = Field(False, description="Filter to only show flight events")


class BulkTrackingResponse(BaseModel):
    success: bool
    results: List[TrackingResponse]
    total: int
    successful: int
    failed: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str


# Helper function to run sync tracker in async context
def _sync_track(tracking_number: str, demo_mode: bool = False) -> TrackingResult:
    """Synchronous tracking function for executor"""
    tracker = get_tracker()
    return tracker.track(tracking_number, demo_mode)


async def track_async(tracking_number: str, demo_mode: bool = False) -> TrackingResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _sync_track, tracking_number, demo_mode)


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return HealthResponse(
        status="healthy",
        service="India Post Tracking API",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="India Post Tracking API",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/track/{tracking_number}", response_model=TrackingResponse)
async def track_shipment(
    tracking_number: str,
    demo: bool = Query(False, description="Use demo mode for testing (returns mock data)"),
    flightOnly: bool = Query(False, description="Filter to only show flight events"),
):
    """
    Track a single shipment by tracking number

    Args:
        tracking_number: India Post tracking number (e.g., LP951627598IN)
        demo: Set to true to get demo/mock data for testing integration
        flightOnly: Set to true to filter events to only show flight events

    Returns:
        TrackingResponse with tracking information and flight summary
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


@app.get("/track", response_model=TrackingResponse)
async def track_shipment_query(
    id: str = Query(..., description="Tracking number", example="LP951627598IN"),
    demo: bool = Query(False, description="Use demo mode for testing"),
    flightOnly: bool = Query(False, description="Filter to only show flight events"),
):
    """
    Track a single shipment by tracking number (query parameter)

    Args:
        id: India Post tracking number
        demo: Set to true to get demo/mock data for testing integration
        flightOnly: Set to true to filter events to only show flight events

    Returns:
        TrackingResponse with tracking information and flight summary
    """
    return await track_shipment(id, demo, flightOnly)


@app.post("/track/bulk", response_model=BulkTrackingResponse)
async def track_bulk_shipments(request: BulkTrackingRequest):
    """
    Track multiple shipments at once (max 10)

    Args:
        request: BulkTrackingRequest with list of tracking numbers, optional demo flag, and optional flightOnly filter

    Returns:
        BulkTrackingResponse with results for all tracking numbers including flight summaries
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
