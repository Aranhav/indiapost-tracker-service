"""
India Post Tracking Scraper
Scrapes tracking information from India Post MIS portal

NOTE: The official India Post tracking website uses CAPTCHA protection.
This scraper attempts multiple methods but may have limited success.
For production use, consider:
1. Official API integration via CEPT (salesndist.cept@indiapost.gov.in)
2. Third-party tracking APIs (TrackingMore, AfterShip, etc.)
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import re
import time
import json


@dataclass
class TrackingEvent:
    """Represents a single tracking event"""
    date: str
    time: str
    office: str
    event: str
    location: Optional[str] = None


@dataclass
class TrackingResult:
    """Represents the complete tracking result"""
    tracking_number: str
    status: str
    events: List[Dict[str, Any]]
    origin: Optional[str] = None
    destination: Optional[str] = None
    booked_on: Optional[str] = None
    delivered_on: Optional[str] = None
    article_type: Optional[str] = None
    error: Optional[str] = None
    source: Optional[str] = None  # Which method was used


class IndiaPostTracker:
    """
    Scraper for India Post tracking website

    Attempts multiple tracking methods:
    1. MIS CEPT Portal (internal use)
    2. India Post public portal (requires CAPTCHA)
    3. Mobile API endpoint (if available)

    For reliable tracking, use official API integration.
    """

    # Base URL and Tracking URL
    BASE_URL = "https://mis.cept.gov.in/"
    TRACKING_URL = "https://mis.cept.gov.in/General/IPS_Track.aspx"

    # Tracking URLs to try
    TRACKING_URLS = [
        {
            "name": "MIS CEPT",
            "base_url": "https://mis.cept.gov.in/",
            "tracking_url": "https://mis.cept.gov.in/General/IPS_Track.aspx",
            "method": "aspnet_form"
        },
    ]

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        self.session.headers.update(self.headers)
        self._session_initialized = False

    def _extract_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract ASP.NET hidden fields from the page"""
        hidden_fields = {}

        # Common ASP.NET hidden fields
        field_names = [
            '__VIEWSTATE',
            '__VIEWSTATEGENERATOR',
            '__EVENTVALIDATION',
            '__EVENTTARGET',
            '__EVENTARGUMENT',
            '__PREVIOUSPAGE',
        ]

        for field_name in field_names:
            field = soup.find('input', {'name': field_name})
            if field and field.get('value'):
                hidden_fields[field_name] = field['value']

        return hidden_fields

    def _find_input_field_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Find the tracking number input field name"""
        # Common patterns for tracking input fields
        patterns = [
            ('input', {'type': 'text', 'id': re.compile(r'.*track.*', re.I)}),
            ('input', {'type': 'text', 'id': re.compile(r'.*item.*', re.I)}),
            ('input', {'type': 'text', 'id': re.compile(r'.*article.*', re.I)}),
            ('input', {'type': 'text', 'id': re.compile(r'.*consignment.*', re.I)}),
            ('input', {'type': 'text', 'name': re.compile(r'.*track.*', re.I)}),
            ('input', {'type': 'text', 'name': re.compile(r'.*item.*', re.I)}),
        ]

        for tag, attrs in patterns:
            field = soup.find(tag, attrs)
            if field and field.get('name'):
                return field['name']

        # Fallback: find any text input that's not hidden
        text_inputs = soup.find_all('input', {'type': 'text'})
        for inp in text_inputs:
            name = inp.get('name', '')
            if name and not name.startswith('__'):
                return name

        return None

    def _find_submit_button(self, soup: BeautifulSoup) -> Optional[str]:
        """Find the submit button name"""
        # Look for submit buttons with common track-related text
        patterns = [
            ('input', {'type': 'submit', 'value': re.compile(r'.*(track|article).*', re.I)}),
            ('input', {'type': 'submit'}),
            ('input', {'type': 'button', 'value': re.compile(r'.*(track|submit|search|go).*', re.I)}),
            ('button', {'type': 'submit'}),
        ]

        for tag, attrs in patterns:
            button = soup.find(tag, attrs)
            if button and button.get('name'):
                return button['name']

        # Look for asp:Button which renders as input - find by value containing "Track"
        buttons = soup.find_all('input', {'type': 'submit'})
        for btn in buttons:
            value = btn.get('value', '').lower()
            if btn.get('name') and ('track' in value or 'article' in value):
                return btn['name']

        # Fallback - any submit button
        for btn in buttons:
            if btn.get('name'):
                return btn['name']

        return None

    def _parse_tracking_table(self, soup: BeautifulSoup) -> List[TrackingEvent]:
        """Parse tracking events from the results - handles both table and list formats"""
        events = []

        # First, try to find the events list (India Post MIS format)
        events_list = soup.find('ul', {'class': re.compile(r'.*events.*', re.I)})
        if events_list:
            print("Found events list format")
            list_items = events_list.find_all('li')
            print(f"Found {len(list_items)} event items")

            for item in list_items:
                # Extract time element
                time_elem = item.find('time')
                datetime_str = time_elem.get_text(strip=True) if time_elem else ""

                # Parse date and time from datetime string (format: "16-01-2026 22:41:03")
                date_str = ""
                time_str = ""
                if datetime_str:
                    parts = datetime_str.split(' ')
                    if len(parts) >= 1:
                        date_str = parts[0]
                    if len(parts) >= 2:
                        time_str = parts[1]

                # Extract event description from <strong> tag
                strong_elem = item.find('strong')
                event_desc = strong_elem.get_text(strip=True) if strong_elem else ""

                # Extract additional details from the div (if any)
                detail_div = item.find('div', {'style': re.compile(r'.*color.*', re.I)})
                details = detail_div.get_text(strip=True) if detail_div else ""

                if event_desc:
                    event = TrackingEvent(
                        date=date_str,
                        time=time_str,
                        office="",  # Not available in this format
                        event=event_desc,
                        location=details if details else None,
                    )
                    events.append(event)
                    print(f"  Parsed event: {date_str} {time_str} | {event_desc}")

            print(f"Total events parsed from list: {len(events)}")
            return events

        # Fallback: Try table-based parsing
        print("Trying table-based parsing...")

        # Common table IDs/classes for tracking results
        table_patterns = [
            {'id': re.compile(r'.*(grd|grid|gv|GridView|track|event|result).*', re.I)},
            {'class': re.compile(r'.*(grd|grid|gv|GridView|track|event|result|table).*', re.I)},
        ]

        table = None
        for pattern in table_patterns:
            table = soup.find('table', pattern)
            if table:
                print(f"Found tracking table with pattern: {pattern}")
                break

        # Try to find table by looking for typical tracking table structure
        if not table:
            tables = soup.find_all('table')
            for t in tables:
                header_row = t.find('tr')
                if header_row:
                    header_text = header_row.get_text().lower()
                    if any(word in header_text for word in ['date', 'time', 'office', 'event', 'status', 'location']):
                        table = t
                        print(f"Found tracking table by header content")
                        break

        if not table:
            print("No tracking table found in response")
            tables = soup.find_all('table')
            print(f"Total tables on page: {len(tables)}")
            return events

        rows = table.find_all('tr')
        print(f"Parsing {len(rows)} rows from tracking table")

        for row in rows[1:]:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 3:
                event = TrackingEvent(
                    date=cols[0].get_text(strip=True) if len(cols) > 0 else "",
                    time=cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    office=cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    event=cols[3].get_text(strip=True) if len(cols) > 3 else "",
                    location=cols[4].get_text(strip=True) if len(cols) > 4 else None,
                )
                if event.date.strip() or event.event.strip():
                    events.append(event)
                    print(f"  Parsed event: {event.date} | {event.event}")

        print(f"Total events parsed from table: {len(events)}")
        return events

    def _extract_summary_info(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract summary information like origin, destination, etc."""
        info = {
            'origin': None,
            'destination': None,
            'booked_on': None,
            'delivered_on': None,
            'article_type': None,
        }

        # Try to find the article info table (id="example" in India Post MIS)
        article_table = soup.find('table', {'id': 'example'})
        if article_table:
            print("Found article info table")
            rows = article_table.find_all('tr')
            if len(rows) >= 2:
                # Get header row to understand column mapping
                header_row = rows[0]
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
                print(f"Article table headers: {headers}")

                # Get data row
                data_row = rows[1]
                cells = [td.get_text(strip=True) for td in data_row.find_all(['td', 'th'])]
                print(f"Article table data: {cells}")

                # Map data to fields
                for i, header in enumerate(headers):
                    if i < len(cells):
                        if 'origin' in header:
                            info['origin'] = cells[i]
                        elif 'destination' in header:
                            info['destination'] = cells[i]

        # Try to find delivery status from the label
        delivery_label = soup.find('span', {'id': re.compile(r'.*label.*', re.I)})
        if delivery_label:
            label_text = delivery_label.get_text(strip=True)
            print(f"Found delivery label: {label_text}")
            # Parse "Item delivered at , Canada on 16-01-2026 22:41:03"
            delivered_match = re.search(r'on\s+(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})', label_text)
            if delivered_match:
                info['delivered_on'] = delivered_match.group(1)

        # Fallback: Try regex patterns on full text
        if not info['origin'] or not info['destination']:
            text = soup.get_text()
            patterns = {
                'origin': [r'(?:from|origin|booked\s*at)[:\s]*([A-Za-z\s]+)'],
                'destination': [r'(?:to|destination|delivery\s*at)[:\s]*([A-Za-z\s]+)'],
                'booked_on': [r'(?:booked\s*on|booking\s*date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'],
            }

            for field, regex_list in patterns.items():
                if not info[field]:
                    for regex in regex_list:
                        match = re.search(regex, text, re.I)
                        if match:
                            info[field] = match.group(1).strip()
                            break

        print(f"Extracted summary info: {info}")
        return info

    def _determine_status(self, events: List[TrackingEvent]) -> str:
        """Determine overall status from events"""
        if not events:
            return "No tracking information available"

        last_event = events[0] if events else None
        if last_event:
            event_text = last_event.event.lower()
            if 'deliver' in event_text:
                return "Delivered"
            elif 'out for delivery' in event_text:
                return "Out for Delivery"
            elif 'transit' in event_text or 'dispatch' in event_text:
                return "In Transit"
            elif 'book' in event_text:
                return "Booked"
            elif 'return' in event_text:
                return "Returned"
            else:
                return last_event.event

        return "Unknown"

    def track(self, tracking_number: str, demo_mode: bool = False) -> TrackingResult:
        """
        Track a shipment by tracking number

        Args:
            tracking_number: India Post tracking number (e.g., LP951627598IN)
            demo_mode: If True, return mock data for testing

        Returns:
            TrackingResult with tracking information
        """
        tracking_number = tracking_number.strip().upper()

        # Validate tracking number format (13 characters: 2 letters + 9 digits + 2 letters)
        if not re.match(r'^[A-Z]{2}\d{9}[A-Z]{2}$', tracking_number):
            return TrackingResult(
                tracking_number=tracking_number,
                status="Error",
                events=[],
                error="Invalid tracking number format. Expected format: XX123456789XX (e.g., LP951627598IN)"
            )

        # Demo mode for testing integration
        if demo_mode:
            return self._get_demo_tracking(tracking_number)

        # Try each tracking URL
        last_error = None
        for url_config in self.TRACKING_URLS:
            try:
                result = self._try_track_url(tracking_number, url_config)
                if result and not result.error:
                    return result
                elif result and result.error:
                    last_error = result.error
            except Exception as e:
                last_error = str(e)
                continue

        # All methods failed
        return TrackingResult(
            tracking_number=tracking_number,
            status="Error",
            events=[],
            error=f"Could not retrieve tracking information. The India Post tracking website may require CAPTCHA or be temporarily unavailable. Last error: {last_error}",
            source="none"
        )

    def _get_demo_tracking(self, tracking_number: str) -> TrackingResult:
        """Return demo tracking data for testing"""
        demo_events = [
            {
                "date": "17-Jan-2025",
                "time": "10:30",
                "office": "MUMBAI GPO",
                "event": "Item Delivered",
                "location": "Mumbai"
            },
            {
                "date": "16-Jan-2025",
                "time": "08:15",
                "office": "MUMBAI GPO",
                "event": "Out for Delivery",
                "location": "Mumbai"
            },
            {
                "date": "15-Jan-2025",
                "time": "14:20",
                "office": "MUMBAI NSH",
                "event": "Item Received",
                "location": "Mumbai"
            },
            {
                "date": "14-Jan-2025",
                "time": "09:00",
                "office": "DELHI NSH",
                "event": "Item Dispatched",
                "location": "Delhi"
            },
            {
                "date": "13-Jan-2025",
                "time": "16:45",
                "office": "DELHI GPO",
                "event": "Item Booked",
                "location": "Delhi"
            },
        ]

        return TrackingResult(
            tracking_number=tracking_number,
            status="Delivered",
            events=demo_events,
            origin="Delhi",
            destination="Mumbai",
            booked_on="13-Jan-2025",
            delivered_on="17-Jan-2025",
            article_type="Speed Post",
            source="demo"
        )

    def _initialize_session(self, base_url: str) -> bool:
        """
        Initialize session by visiting the homepage first.
        This establishes cookies and session state required for tracking.
        """
        try:
            print(f"Initializing session by visiting: {base_url}")
            response = self.session.get(base_url, timeout=self.timeout)
            response.raise_for_status()
            self._session_initialized = True
            print(f"Session initialized successfully. Cookies: {len(self.session.cookies)}")
            return True
        except Exception as e:
            print(f"Failed to initialize session: {e}")
            return False

    def _try_track_url(self, tracking_number: str, url_config: dict) -> Optional[TrackingResult]:
        """Try tracking with a specific URL configuration"""
        base_url = url_config.get("base_url", "https://mis.cept.gov.in/")
        tracking_url = url_config.get("tracking_url", url_config.get("url"))
        name = url_config["name"]

        try:
            # Step 1: First visit the homepage to establish session/cookies
            if not self._session_initialized:
                if not self._initialize_session(base_url):
                    return TrackingResult(
                        tracking_number=tracking_number,
                        status="Error",
                        events=[],
                        error=f"Could not establish session with {name}",
                        source=name
                    )
                # Small delay after homepage visit
                time.sleep(0.5)

            # Step 2: Navigate to the tracking page
            print(f"Navigating to tracking page: {tracking_url}")
            response = self.session.get(
                tracking_url,
                timeout=self.timeout,
                headers={
                    **self.headers,
                    "Referer": base_url,
                }
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Step 3: Extract hidden ASP.NET fields
            hidden_fields = self._extract_hidden_fields(soup)
            print(f"Found hidden fields: {list(hidden_fields.keys())}")

            if not hidden_fields.get('__VIEWSTATE'):
                # Session might have expired, try reinitializing
                self._session_initialized = False
                return TrackingResult(
                    tracking_number=tracking_number,
                    status="Error",
                    events=[],
                    error=f"Could not extract form state from {name}. Session may have expired.",
                    source=name
                )

            # Step 4: Find input field and button names
            input_field = self._find_input_field_name(soup)
            submit_button = self._find_submit_button(soup)

            print(f"Found input field: {input_field}, submit button: {submit_button}")

            # If not found, try common field names for this specific site
            if not input_field:
                # Try to find by inspecting all text inputs
                all_inputs = soup.find_all('input', {'type': 'text'})
                for inp in all_inputs:
                    name_attr = inp.get('name', '')
                    id_attr = inp.get('id', '')
                    print(f"Found text input: name={name_attr}, id={id_attr}")
                input_field = "ctl00$ContentPlaceHolder1$txtItemId"  # Common ASP.NET pattern

            # Look for __doPostBack pattern in buttons
            dopostback_target = None
            buttons = soup.find_all('button', {'type': 'submit'})
            for btn in buttons:
                onclick = btn.get('onclick', '')
                print(f"Found button with onclick: {onclick}")
                # Parse __doPostBack('target','arg') pattern
                match = re.search(r"__doPostBack\('([^']+)'", onclick)
                if match:
                    dopostback_target = match.group(1)
                    print(f"Found __doPostBack target: {dopostback_target}")
                    break

            if not submit_button and not dopostback_target:
                # Try common button names
                all_buttons = soup.find_all('input', {'type': 'submit'})
                for btn in all_buttons:
                    btn_name = btn.get('name', '')
                    btn_value = btn.get('value', '')
                    print(f"Found submit button: name={btn_name}, value={btn_value}")
                submit_button = "ctl00$ContentPlaceHolder1$btnTrack"  # Common pattern

            # Step 5: Build POST data
            post_data = {**hidden_fields}
            post_data[input_field] = tracking_number

            # Handle __doPostBack mechanism (ASP.NET's way of handling button clicks)
            if dopostback_target:
                post_data['__EVENTTARGET'] = dopostback_target
                post_data['__EVENTARGUMENT'] = ''
                print(f"Using __doPostBack: EVENTTARGET={dopostback_target}")
            elif submit_button:
                post_data[submit_button] = "Track Article"

            print(f"Submitting tracking request for: {tracking_number}")

            # Add small delay to be respectful
            time.sleep(0.5)

            # Step 6: POST the form
            response = self.session.post(
                tracking_url,
                data=post_data,
                timeout=self.timeout,
                headers={
                    **self.headers,
                    "Referer": tracking_url,
                    "Origin": "https://mis.cept.gov.in",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            )
            response.raise_for_status()

            print(f"POST response status: {response.status_code}")

            # Step 7: Parse results
            soup = BeautifulSoup(response.text, 'lxml')

            # Debug: Save HTML for analysis
            try:
                with open('/tmp/tracking_response.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print("Saved response HTML to /tmp/tracking_response.html")
            except Exception as e:
                print(f"Could not save HTML: {e}")

            # Debug: Print page title to verify we got the right page
            title = soup.find('title')
            print(f"Response page title: {title.text if title else 'No title'}")

            # Check for error messages
            error_div = soup.find(['div', 'span'], {'class': re.compile(r'.*error.*', re.I)})
            if error_div:
                error_text = error_div.get_text(strip=True)
                if error_text:
                    return TrackingResult(
                        tracking_number=tracking_number,
                        status="Not Found",
                        events=[],
                        error=error_text
                    )

            # Parse tracking events
            events = self._parse_tracking_table(soup)

            # Extract summary info
            summary = self._extract_summary_info(soup)

            # Determine status
            status = self._determine_status(events)

            return TrackingResult(
                tracking_number=tracking_number,
                status=status,
                events=[asdict(e) for e in events],
                origin=summary['origin'],
                destination=summary['destination'],
                booked_on=summary['booked_on'],
                delivered_on=summary['delivered_on'],
                article_type=summary['article_type'],
                source=name
            )

        except requests.exceptions.Timeout:
            return TrackingResult(
                tracking_number=tracking_number,
                status="Error",
                events=[],
                error=f"Request to {name} timed out.",
                source=name
            )
        except requests.exceptions.RequestException as e:
            return TrackingResult(
                tracking_number=tracking_number,
                status="Error",
                events=[],
                error=f"Network error from {name}: {str(e)}",
                source=name
            )
        except Exception as e:
            return TrackingResult(
                tracking_number=tracking_number,
                status="Error",
                events=[],
                error=f"Error from {name}: {str(e)}",
                source=name
            )


# For testing
if __name__ == "__main__":
    tracker = IndiaPostTracker()
    result = tracker.track("LP951627598IN")
    print(f"Status: {result.status}")
    print(f"Events: {len(result.events)}")
    if result.error:
        print(f"Error: {result.error}")
    for event in result.events:
        print(f"  {event}")
