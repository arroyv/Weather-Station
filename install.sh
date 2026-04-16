#!/bin/bash
set -e

echo "Beginning installation of Weather Station..."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "Adding current user to required groups..." 
if ! sudo usermod -a -G dialout,gpio "$USER"
then 
    echo "Error. Failed to add $USER to dialout and gpio groups." 
    exit 1
fi
echo "Added $USER to dialout and gpio groups." 
echo "Please log out/in for this to fully apply." 

echo "Creating virtual environment..." 
if [ ! -d "$VENV_DIR" ]
then 
    python3 -m venv "$VENV_DIR"
fi 

echo "Installing required libraries..."
if ! "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
then
    echo "Error. Failed to install required libraries." 
    exit 1
fi

echo "Setting up environment variables..."
if [ ! -f "$PROJECT_DIR/.env" ]
then 
    cat > "$PROJECT_DIR/.env" <<EOF
ADAFRUIT_IO_USERNAME=""
ADAFRUIT_IO_KEY=""
EOF
    echo "Created .env file. If Adafruit IO is enabled, please update .env with your ADAFRUIT_IO_USERNAME and ADAFRUIT_IO_KEY."
fi

echo "Setting up systemd service..." 
if ! sudo "$VENV_DIR/bin/python" "$PROJECT_DIR/setup_services.py" install
then
    echo "Error. Failed to install systemd services." 
    exit 1
fi

echo "Nice!, Your installation has completed successfully!" 