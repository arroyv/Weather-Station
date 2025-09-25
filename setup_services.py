#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import getpass

# --- Configuration ---
# The absolute path to your project directory
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXEC = sys.executable # Use the same python that runs this script
GUNICORN_EXEC = os.path.join(os.path.dirname(PYTHON_EXEC), 'gunicorn')

# Service file templates
WEATHER_STATION_SERVICE_TPL = """
[Unit]
Description=Weather Station Data Collector (%(name)s)
StartLimitIntervalSec=0

[Service]
User=%(user)s
Group=%(user)s
WorkingDirectory=%(path)s
TimeoutStartSec=0
ExecStartPre=/bin/sleep 90
ExecStart=%(python_exec)s %(path)s/run_weather_station.py --name "%(name)s" --id %(id)s --role %(role)s
Restart=always
RestartSec=90s

[Install]
WantedBy=multi-user.target
"""

DASHBOARD_SERVICE_TPL = """
[Unit]
Description=Weather Station Dashboard
After=network-online.target

[Service]
User=%(user)s
Group=%(user)s
WorkingDirectory=%(path)s
ExecStart=%(gunicorn_exec)s --workers 3 --bind 0.0.0.0:5000 app:app
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
"""

def run_command(command, as_root=True):
    """Runs a shell command, optionally with sudo."""
    if as_root and os.geteuid() != 0:
        command.insert(0, 'sudo')
    print(f"  > Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] Command failed: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"  [ERROR] Command not found: {command[0]}", file=sys.stderr)
        return False

def check_root():
    """Checks if the script is being run as root."""
    if os.geteuid() != 0:
        print("[ERROR] This script must be run with sudo.", file=sys.stderr)
        print("        Please run as: sudo /path/to/your/venv/bin/python3 setup_services.py <command>", file=sys.stderr)
        sys.exit(1)

def do_install():
    """Interactive installer for the services."""
    check_root()
    
    # Get the username of the user who invoked sudo
    user = os.getenv('SUDO_USER')
    if not user:
        print("[Warning] Could not determine username from SUDO_USER. Falling back to current user.")
        user = getpass.getuser()

    print(f"--- Weather Station Service Installer (for user: {user}) ---")
    
    # --- Get Station Info ---
    try:
        station_type = input("Is this a [1] Base Station or [2] Remote Station? [1]: ") or "1"
        if station_type == '1':
            role = 'base'
        elif station_type == '2':
            role = 'remote'
        else:
            print("Invalid selection. Aborting.")
            return

        station_name = input(f"Enter a name for this {role} station: ")
        station_id = input(f"Enter a unique numeric ID for this {role} station: ")
        
        if not station_name or not station_id.isdigit():
            print("Invalid name or ID. Aborting.")
            return

    except (EOFError, KeyboardInterrupt):
        print("\nInstallation cancelled.")
        return

    # --- Create Weather Station Service ---
    print("\n[1/2] Creating weather-station.service...")
    service_config = {
        'user': user,
        'path': PROJECT_PATH,
        'python_exec': PYTHON_EXEC,
        'name': station_name,
        'id': station_id,
        'role': role
    }
    service_content = WEATHER_STATION_SERVICE_TPL % service_config
    service_path = "/etc/systemd/system/weather-station.service"
    try:
        with open(service_path, "w") as f:
            f.write(service_content)
        print(f"  > Wrote service file to {service_path}")
    except IOError as e:
        print(f"  [ERROR] Could not write service file: {e}", file=sys.stderr)
        return

    # --- Create Dashboard Service (if base station) ---
    if role == 'base':
        print("\n[2/2] Creating weather-dashboard.service...")
        if not (os.path.isfile(GUNICORN_EXEC) and os.access(GUNICORN_EXEC, os.X_OK)):
            print(f"\n[ERROR] `gunicorn` was not found at {GUNICORN_EXEC}", file=sys.stderr)
            print(f"        Please ensure it's installed in your virtual environment: pip install gunicorn", file=sys.stderr)
            if os.path.exists(service_path):
                os.remove(service_path)
                print(f"\nRemoved partially created file: {service_path}")
            return

        dashboard_config = {
            'user': user,
            'path': PROJECT_PATH,
            'gunicorn_exec': GUNICORN_EXEC
        }
        dashboard_content = DASHBOARD_SERVICE_TPL % dashboard_config
        dashboard_path = "/etc/systemd/system/weather-dashboard.service"
        try:
            with open(dashboard_path, "w") as f:
                f.write(dashboard_content)
            print(f"  > Wrote service file to {dashboard_path}")
        except IOError as e:
            print(f"  [ERROR] Could not write service file: {e}", file=sys.stderr)
            return

    # --- Reload systemd ---
    print("\nReloading systemd daemon...")
    run_command(['systemctl', 'daemon-reload'], as_root=False)

    # --- Ask to enable ---
    try:
        enable = input("\nEnable services to run on boot? (y/n) [y]: ").lower() or 'y'
        if enable == 'y':
            do_enable()
            start = input("Reboot now to start services? (y/n) [y]: ").lower() or 'y'
            # start = input("Start services now? (y/n) [y]: ").lower() or 'y'
            if start == 'y':
                do_reboot()
                # do_start()
    except (EOFError, KeyboardInterrupt):
        print("\nSkipping enable/start.")

    print("\n--- Installation Complete ---")

def do_uninstall():
    """Removes the service files and stops the services."""
    check_root()
    print("--- Uninstalling Services ---")
    do_disable()
    
    ws_service = "/etc/systemd/system/weather-station.service"
    wd_service = "/etc/systemd/system/weather-dashboard.service"
    
    if os.path.exists(ws_service):
        os.remove(ws_service)
        print(f"Removed {ws_service}")
        
    if os.path.exists(wd_service):
        os.remove(wd_service)
        print(f"Removed {wd_service}")
        
    run_command(['systemctl', 'daemon-reload'], as_root=False)
    print("\n--- Uninstall Complete ---")

def do_enable():
    """Enables services to start on boot."""
    check_root()
    print("Enabling weather-station.service...")
    run_command(['systemctl', 'enable', 'weather-station.service'], as_root=False)
    if os.path.exists("/etc/systemd/system/weather-dashboard.service"):
        print("Enabling weather-dashboard.service...")
        run_command(['systemctl', 'enable', 'weather-dashboard.service'], as_root=False)

def do_disable():
    """Disables and stops services from starting on boot."""
    check_root()
    print("Disabling weather-station.service...")
    run_command(['systemctl', 'disable', '--now', 'weather-station.service'], as_root=False)
    if os.path.exists("/etc/systemd/system/weather-dashboard.service"):
        print("Disabling weather-dashboard.service...")
        run_command(['systemctl', 'disable', '--now', 'weather-dashboard.service'], as_root=False)

def do_reboot():
    """Reboot the system after enabling services."""
    check_root()
    run_command(['sudo', 'reboot'], as_root=True)

def do_start():
    """Starts the services."""
    check_root()
    print("Starting weather-station.service...")
    run_command(['systemctl', 'start', 'weather-station.service'], as_root=False)
    if os.path.exists("/etc/systemd/system/weather-dashboard.service"):
        print("Starting weather-dashboard.service...")
        run_command(['systemctl', 'start', 'weather-dashboard.service'], as_root=False)

def do_stop():
    """Stops the services."""
    check_root()
    print("Stopping weather-station.service...")
    run_command(['systemctl', 'stop', 'weather-station.service'], as_root=False)
    if os.path.exists("/etc/systemd/system/weather-dashboard.service"):
        print("Stopping weather-dashboard.service...")
        run_command(['systemctl', 'stop', 'weather-dashboard.service'], as_root=False)

def do_status():
    """Checks the status of the services."""
    print("--- Service Status ---")
    run_command(['systemctl', 'status', 'weather-station.service', 'weather-dashboard.service'], as_root=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A helper script to manage weather station systemd services.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('command', choices=['install', 'uninstall', 'enable', 'disable', 'start', 'stop', 'status'],
                        help="""
    install     - Run the interactive installer to create the service files.
    uninstall   - Stop the services and remove the service files.
    enable      - Enable the services to start on boot.
    disable     - Disable and stop the services from starting on boot.
    start       - Start the services now.
    stop        - Stop the services now.
    status      - Check the current status of the services.
    reboot      - Reboot the system for services to start.
    """)

    args = parser.parse_args()

    # Map command strings to functions
    commands = {
        'install': do_install,
        'uninstall': do_uninstall,
        'enable': do_enable,
        'disable': do_disable,
        'start': do_start,
        'stop': do_stop,
        'status': do_status,
        'reboot': do_reboot,
    }
    
    # Execute the function corresponding to the command
    commands[args.command]()
