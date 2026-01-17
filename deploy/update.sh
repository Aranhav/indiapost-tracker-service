#!/bin/bash

# India Post Tracking API - Update Script
# Run as root or with sudo

set -e

APP_DIR="/opt/indiapost-tracker"

echo "Updating India Post Tracking API..."

cd $APP_DIR

# Pull latest changes
echo "Pulling latest changes from GitHub..."
git pull origin main

# Activate virtual environment and update dependencies
echo "Updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Restart service
echo "Restarting service..."
systemctl restart indiapost-tracker

echo "Update complete!"
systemctl status indiapost-tracker --no-pager
