#!/bin/sh

SCRIPT=$(readlink -f "$0")
export BASE_DIR=$(dirname "${SCRIPT}")
CFG_FILE="domoticz_gazpar.cfg"

# check configuration file
if [ ! -f "${BASE_DIR}"/"${CFG_FILE}" ]
then
    echo "Config file is missing ["${BASE_DIR}"/"${CFG_FILE}"]"
    exit 1
fi

. "${BASE_DIR}"/"${CFG_FILE}"
export GAZPAR_USERNAME
export GAZPAR_PASSWORD
export DOMOTICZ_ID
export DOMOTICZ_ID_M3
export NB_DAYS_IMPORTED
export LOGGING_LEVEL
export PYTHONWARNINGS="ignore"
export DB="${HOME}/domoticz/domoticz.db"
LOG_FILE="domoticz_gazpar.log"
PY_SCRIPT="gazpar.py"
PY_SCRIPT="${BASE_DIR}"/"${PY_SCRIPT}"
python3 "${PY_SCRIPT}" $1 -o "${BASE_DIR}" >> "${BASE_DIR}"/"${LOG_FILE}" 2>&1
