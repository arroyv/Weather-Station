#!/usr/bin/env bash
set -euo pipefail

VENV_DIR_NAME="venv"                 
PYTHON_BIN="${PYTHON_BIN:-python3}" 
# STATION_TYPE: 1 = base station, 2 = remote station
STATION_TYPE="${STATION_TYPE:-}"
STATION_NAME="${STATION_NAME:-}"
STATION_ID="${STATION_ID:-}"
ENABLE_ON_BOOT="${ENABLE_ON_BOOT:-y}"
START_NOW="${START_NOW:-y}"
# =================================

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${APP_DIR}/${VENV_DIR_NAME}"
REQ_FILE="${APP_DIR}/requirements.txt"
SETUP_SERVICES="${APP_DIR}/setup_services.py"

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo:"
  echo "  sudo ./install.sh"
  exit 1
fi

APP_USER="${SUDO_USER:-$USER}"

echo "== Unified Installer =="
echo "Project: ${APP_DIR}"
echo "User:    ${APP_USER}"
echo

# 1) Create venv
echo "[1/6] Creating/using venv at ${VENV_DIR}"
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "[2/6] Installing Python deps from requirements.txt"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${REQ_FILE}"

echo "      Installing gunicorn (needed for base-station web server)"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install gunicorn

if [[ -z "${STATION_TYPE}" ]]; then
  read -r -p "Is this a [1] Base Station or [2] Remote Station? [1]: " STATION_TYPE
  STATION_TYPE="${STATION_TYPE:-1}"
fi

if [[ -z "${STATION_NAME}" ]]; then
  read -r -p "Enter a name for this station: " STATION_NAME
fi

if [[ -z "${STATION_ID}" ]]; then
  read -r -p "Enter a unique numeric ID for this station: " STATION_ID
fi

# Basic validation
if [[ "${STATION_TYPE}" != "1" && "${STATION_TYPE}" != "2" ]]; then
  echo "ERROR: STATION_TYPE must be 1 (base) or 2 (remote)."
  exit 1
fi
if [[ -z "${STATION_NAME}" ]]; then
  echo "ERROR: STATION_NAME is required."
  exit 1
fi
if ! [[ "${STATION_ID}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: STATION_ID must be numeric."
  exit 1
fi

echo
echo "[3/6] Installing systemd services via setup_services.py"
printf "%s\n%s\n%s\n%s\n%s\n" \
  "${STATION_TYPE}" \
  "${STATION_NAME}" \
  "${STATION_ID}" \
  "${ENABLE_ON_BOOT}" \
  "${START_NOW}" \
  | "${VENV_DIR}/bin/python" "${SETUP_SERVICES}" install

echo
echo "[4/6] Showing service status"
systemctl status weather-station.service --no-pager || true

if [[ -f /etc/systemd/system/weather-dashboard.service ]]; then
  systemctl status weather-dashboard.service --no-pager || true
fi

echo
echo "[5/6] Recent logs"
journalctl -u weather-station.service -n 30 --no-pager || true
if [[ -f /etc/systemd/system/weather-dashboard.service ]]; then
  journalctl -u weather-dashboard.service -n 30 --no-pager || true
fi

echo
echo "[6/6] Done"
echo "Follow logs:"
echo "  journalctl -u weather-station.service -f"
echo "  journalctl -u weather-dashboard.service -f   # base station only"
