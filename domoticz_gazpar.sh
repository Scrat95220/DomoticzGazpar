#!/bin/sh

SCRIPT=$(readlink -f "$0")
BASE_DIR=$(dirname "${SCRIPT}")
export BASE_DIR
CFG_FILE="domoticz_gazpar.cfg"
LOG_FILE="domoticz_gazpar.log"
export PYTHONWARNINGS="ignore"

update_db () {
  PY_SCRIPT="gaspar.py"
  PY_SCRIPT="${BASE_DIR}"/"${PY_SCRIPT}"
  python3 "${PY_SCRIPT}" $1 -o "${BASE_DIR}" >> "${BASE_DIR}"/"${LOG_FILE}" 2>&1
  if  [ $? -eq 0 ]; then
    cat "${BASE_DIR}"/req.sql | /usr/bin/sqlite3 "${HOME}"/domoticz/domoticz.db
  fi
}

# check configuration file
if [ -f "${BASE_DIR}"/"${CFG_FILE}" ]
then
  . "${BASE_DIR}"/"${CFG_FILE}"
  export GAZPAR_USERNAME
  export GAZPAR_PASSWORD
  export DOMOTICZ_ID
  export NB_DAYS_IMPORTED
  update_db 
else
    echo "Config file is missing ["${BASE_DIR}"/"${CFG_FILE}"]"
    exit 1
fi

