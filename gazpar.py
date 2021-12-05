#!/usr/bin/python3
# -*- coding: utf-8 -*-
# (C) v1.0 2021-11-29 Scrat
"""Generates energy consumption JSON files from GRDf consumption data
collected via their  website (API).
"""

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import configparser
import os
import requests
import datetime
import logging
import logging.config
import sys
import json
from dateutil.relativedelta import relativedelta
import sqlite3

LOGIN_BASE_URI = 'https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth'
API_BASE_URI = 'https://monespace.grdf.fr/'

userName = ""
password = ""
devicerowid = ""
devicerowidm3 = ""
nbDaysImported = 7
database = ""

script_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
configuration_file = script_dir + '/domoticz_gazpar.cfg'
logging.config.fileConfig(configuration_file, defaults={
                          'logfilename': script_dir + '/domoticz_gazpar.log'}, disable_existing_loggers=False)

logger = logging.getLogger(__name__)


class GazparServiceException(Exception):
    """Thrown when the webservice threw an exception."""
    pass

# Date formatting


def dtostr(date):
    return date.strftime("%Y-%m-%d")


def login(username, password):
    """Logs the user into the GRDF API.
    """
    session = requests.Session()

    payload = {
        'email': username,
        'password': password,
        'goto': 'https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code%26scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg%20%2FDemande.read%20%2FDemande.write%26client_id=prod_espaceclient%26state=0%26redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch%26nonce=7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag%26by_pass_okta=1%26capp=meg',
                'capp': 'meg'
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'https://login.monespace.grdf.fr/mire/connexion?goto=https:%2F%2Fsofa-connexion.grdf.fr:443%2Fopenam%2Foauth2%2FexterneGrdf%2Fauthorize%3Fresponse_type%3Dcode%26scope%3Dopenid%2520profile%2520email%2520infotravaux%2520%252Fv1%252Faccreditation%2520%252Fv1%252Faccreditations%2520%252Fdigiconso%252Fv1%2520%252Fdigiconso%252Fv1%252Fconsommations%2520new_meg%2520%252FDemande.read%2520%252FDemande.write%26client_id%3Dprod_espaceclient%26state%3D0%26redirect_uri%3Dhttps%253A%252F%252Fmonespace.grdf.fr%252F_codexch%26nonce%3D7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag%26by_pass_okta%3D1%26capp%3Dmeg&realm=%2FexterneGrdf&capp=meg'
    }
    try:
        resp1 = session.post(LOGIN_BASE_URI, data=payload, headers=headers)
    except requests.exceptions.RequestException as err:
        loggig.error(
            "Error while connecting to https://sofa-connexion.grdf.fr")
        logging.error("Error %s", err)
        raise SystemExit(e)

    if resp1.status_code != requests.codes.ok:
        loggig.error("Login call - error status : %s", resp1.status_code)
        sys.exit(1)

    # 2nd request
    headers = {
        'Referer': 'https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid profile email infotravaux /v1/accreditation /v1/accreditations /digiconso/v1 /digiconso/v1/consommations new_meg /Demande.read /Demande.write&client_id=prod_espaceclient&state=0&redirect_uri=https://monespace.grdf.fr/_codexch&nonce=7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag&by_pass_okta=1&capp=meg'
    }

    resp2 = session.get(API_BASE_URI, allow_redirects=True)
    if resp2.status_code != requests.codes.ok:
        logging.error("Login 2nd call - error status : %s", resp2.status_code)

    return session


def generate_db_script(session, start_date, end_date):
    """Retreives monthly energy consumption data."""
    logging.debug('start_date: ' + start_date)
    logging.debug('  end_date: ' + end_date)

    # 3nd request- Get NumPCE
    resp3 = session.get(
        'https://monespace.grdf.fr/api/e-connexion/users/pce/historique-consultation')
    if resp3.status_code != requests.codes.ok:
        logging.error("Get NumPce call - error status : %s", resp3.status_code)

    logging.debug("Get NumPce: %s", resp3.text)

    j = json.loads(resp3.text)
    numPce = j[0]['numPce']

    data = get_data_with_interval(
        session, 'Mois', numPce, start_date, end_date)

    j = json.loads(data)

    index = j[str(numPce)]['releves'][0]['indexDebut']

    conn = sqlite3.connect(database)
    # This attaches the tracer
    conn.set_trace_callback(logging.debug)
    c = conn.cursor()
    logging.info("Updating Database...")
    f = open("req.sql", "w")
    for releve in j[str(numPce)]['releves']:
        # print(releve)
        req_date = releve['journeeGaziere']
        conso = releve['energieConsomme']
        volume = releve['volumeBrutConsomme']
        indexm3 = releve['indexDebut']
        try:
            index = index + conso
        except TypeError:
            logging.warning("Invalid Entry %s", req_date)
            continue
        if devicerowid:
            try:
                c.execute("DELETE FROM Meter_Calendar WHERE devicerowid = ? and date = ?",
                          (devicerowid, req_date))
                c.execute("INSERT INTO Meter_Calendar (DeviceRowID,Value,Counter,Date) VALUES (?,?,?,?)",
                          (devicerowid, int(conso) * 1000, index, req_date))
            except sqlite3.Error as err:
                logging.warning("sqlite3 error: %s", err)

        if devicerowidm3:
            try:
                c.execute("DELETE FROM Meter_Calendar WHERE devicerowid = ? and date = ?",
                          (devicerowidm3, req_date))
                c.execute("INSERT INTO Meter_Calendar (DeviceRowID,Value,Counter,Date) VALUES (?,?,?,?)",
                          (devicerowidm3, int(volume) * 1000, indexm3, req_date))
            except sqlite3.Error as err:
                logging.warning("sqlite3 error: %s", err)

    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if devicerowid:
        c.execute("UPDATE DeviceStatus SET lastupdate = ? WHERE id = ?",
                  (today, devicerowid))
    if devicerowidm3:
        c.execute("UPDATE DeviceStatus SET lastupdate = ? WHERE id = ?",
                  (today, devicerowidm3))

    # Trace of all changes within logging DEBUG level
    c.fetchone()
    # Log all changes made to database
    logging.info("Database Total Changes: %s", str(conn.total_changes))
    conn.commit()
    conn.close()


def get_data_with_interval(session, resource_id, numPce, start_date=None, end_date=None):
    r = session.get('https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut=' +
                    start_date + '&dateFin=' + end_date + '&pceList[]=' + str(numPce))
    if r.status_code != requests.codes.ok:
        logging.error("error status : %s", r.status_code )
    return r.text


def get_config():
    configuration_file = script_dir + '/domoticz_gazpar.cfg'
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(configuration_file)
    global userName
    global password
    global devicerowid
    global devicerowidm3
    global nbDaysImported
    global database

    userName = config['GRDF']['GAZPAR_USERNAME']
    password = config['GRDF']['GAZPAR_PASSWORD']
    devicerowid = config['DOMOTICZ']['DOMOTICZ_ID']
    devicerowidm3 = config['DOMOTICZ']['DOMOTICZ_ID_M3']
    nbDaysImported = config['GRDF']['NB_DAYS_IMPORTED']
    database = config['SETTINGS']['DB_PATH'] + "/domoticz.db"
    logging.info("Database is %s", database)

# Main script

def main():

    try:
        logging.debug("Get configuration")
        get_config()

        logging.info("logging in as %s...", userName)
        token = login(userName, password)
        logging.info("logged in successfully!")

        today = datetime.date.today()

        # Generate DB script
        logging.info("retrieving data...")
        generate_db_script(token, dtostr(today - relativedelta(days=int(nbDaysImported))),
                           dtostr(today))

        #logging.info("got data!")
    except GazparServiceException as err:
        logging.error(err)
        sys.exit(1)


if __name__ == "__main__":
    main()
