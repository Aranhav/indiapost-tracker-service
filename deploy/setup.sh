#!/bin/bash

# India Post Tracking API - Ubuntu Server Setup Script
# Run as root or with sudo

set -e

echo "=========================================="
echo "India Post Tracking API - Server Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/indiapost-tracker"
APP_USER="www-data"
REPO_URL="https://github.com/Aranhav/indiapost-tracker-service.git"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv git nginx

echo -e "${YELLOW}Step 2: Creating application directory...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

echo -e "${YELLOW}Step 3: Cloning repository...${NC}"
if [ -d ".git" ]; then
    echo "Repository exists, pulling latest changes..."
    git pull origin main
else
    git clone $REPO_URL .
fi

echo -e "${YELLOW}Step 4: Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${YELLOW}Step 5: Creating environment file...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << EOF
# India Post Tracking API Environment Variables
PYTHONUNBUFFERED=1
EOF
    echo -e "${GREEN}Created .env file${NC}"
else
    echo -e "${YELLOW}.env file already exists, skipping${NC}"
fi

echo -e "${YELLOW}Step 6: Setting permissions...${NC}"
chown -R $APP_USER:$APP_USER $APP_DIR
chmod -R 755 $APP_DIR

echo -e "${YELLOW}Step 7: Installing systemd service...${NC}"
cp deploy/indiapost-tracker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable indiapost-tracker
systemctl start indiapost-tracker

echo -e "${YELLOW}Step 8: Configuring Nginx...${NC}"
cp deploy/nginx.conf /etc/nginx/sites-available/indiapost-tracker
ln -sf /etc/nginx/sites-available/indiapost-tracker /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Service Status:"
systemctl status indiapost-tracker --no-pager
echo ""
echo -e "${GREEN}API is now running at:${NC}"
echo "  - Local: http://127.0.0.1:8000"
echo "  - Via Nginx: http://your-server-ip"
echo ""
echo "Useful commands:"
echo "  - Check status: sudo systemctl status indiapost-tracker"
echo "  - View logs: sudo journalctl -u indiapost-tracker -f"
echo "  - Restart: sudo systemctl restart indiapost-tracker"
echo "  - Stop: sudo systemctl stop indiapost-tracker"
