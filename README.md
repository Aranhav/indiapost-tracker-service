# India Post Tracking Microservice

A Python FastAPI microservice for tracking India Post shipments by scraping the official MIS CEPT tracking portal.

## Features

- Track single shipment by tracking number
- Bulk tracking (up to 10 shipments at once)
- RESTful API with Swagger documentation
- Docker support for easy deployment
- Ubuntu server deployment with systemd and Nginx
- CORS enabled for cross-origin requests

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Health check |
| GET | `/track/{tracking_number}` | Track single shipment |
| GET | `/track?id={tracking_number}` | Track single shipment (query param) |
| POST | `/track/bulk` | Track multiple shipments |

## Quick Start

### Option 1: Run with Python (Development)

```bash
# Clone the repository
git clone https://github.com/Aranhav/indiapost-tracker-service.git
cd indiapost-tracker-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 8000
```

### Option 2: Run with Docker

```bash
# Build and run
docker-compose up --build

# Or manually
docker build -t indiapost-tracker .
docker run -p 8000:8000 indiapost-tracker
```

### Option 3: Deploy on Ubuntu Server

```bash
# SSH into your server
ssh user@your-server-ip

# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/Aranhav/indiapost-tracker-service/main/deploy/setup.sh | sudo bash
```

Or manually:

```bash
# Clone repository
sudo git clone https://github.com/Aranhav/indiapost-tracker-service.git /opt/indiapost-tracker
cd /opt/indiapost-tracker

# Run setup
sudo bash deploy/setup.sh
```

## Ubuntu Server Deployment

### Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Root or sudo access
- Python 3.8+

### Manual Setup Steps

1. **Install dependencies:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx
```

2. **Clone repository:**
```bash
sudo mkdir -p /opt/indiapost-tracker
sudo git clone https://github.com/Aranhav/indiapost-tracker-service.git /opt/indiapost-tracker
cd /opt/indiapost-tracker
```

3. **Setup Python environment:**
```bash
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

4. **Create environment file:**
```bash
sudo cp .env.example .env
```

5. **Set permissions:**
```bash
sudo chown -R www-data:www-data /opt/indiapost-tracker
```

6. **Install systemd service:**
```bash
sudo cp deploy/indiapost-tracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable indiapost-tracker
sudo systemctl start indiapost-tracker
```

7. **Configure Nginx:**
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/indiapost-tracker
sudo ln -sf /etc/nginx/sites-available/indiapost-tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Service Management

```bash
# Check status
sudo systemctl status indiapost-tracker

# View logs
sudo journalctl -u indiapost-tracker -f

# Restart service
sudo systemctl restart indiapost-tracker

# Stop service
sudo systemctl stop indiapost-tracker

# Update to latest version
cd /opt/indiapost-tracker
sudo bash deploy/update.sh
```

### SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

## Usage Examples

### Track Single Shipment

```bash
# Using path parameter
curl http://localhost:8000/track/LP951627598IN

# Using query parameter
curl "http://localhost:8000/track?id=LP951627598IN"

# Demo mode (returns mock data for testing)
curl "http://localhost:8000/track/LP951627598IN?demo=true"
```

### Response Format

```json
{
  "success": true,
  "tracking_number": "LP951627598IN",
  "status": "Delivered",
  "events": [
    {
      "date": "16-01-2026",
      "time": "22:41:03",
      "office": "",
      "event": "Delivered",
      "location": null
    }
  ],
  "origin": "India",
  "destination": "Canada",
  "booked_on": null,
  "delivered_on": null,
  "article_type": null,
  "error": null,
  "source": "MIS CEPT",
  "timestamp": "2026-01-17T05:50:33.530242"
}
```

### Bulk Tracking

```bash
curl -X POST http://localhost:8000/track/bulk \
  -H "Content-Type: application/json" \
  -d '{"tracking_numbers": ["LP951627598IN", "EE123456789IN"]}'
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Integration with Next.js App

```typescript
// In your Next.js app
const trackShipment = async (trackingNumber: string) => {
  const response = await fetch(
    `http://your-server-ip:8000/track/${trackingNumber}`
  );
  const data = await response.json();
  return data;
};
```

## File Structure

```
indiapost-tracker-service/
├── main.py              # FastAPI application
├── tracker.py           # Scraping logic
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose config
├── .env.example         # Environment template
├── .gitignore           # Git ignore file
├── README.md            # This file
└── deploy/
    ├── setup.sh                    # Ubuntu setup script
    ├── update.sh                   # Update script
    ├── indiapost-tracker.service   # Systemd service
    └── nginx.conf                  # Nginx configuration
```

## Notes

- The scraper works with the India Post MIS CEPT portal
- Be respectful with request rates to avoid IP blocking
- For production, consider adding caching and rate limiting
- The official India Post tracking may require CAPTCHA in some cases

## License

MIT

