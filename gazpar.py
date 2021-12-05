#!/usr/bin/python3
# -*- coding: utf-8 -*-
# (C) v1.3.0 2021-12-04 Scrat
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

import urllib.request
import base64
import configparser
import os
import requests
import datetime
import logging
import json
from dateutil.relativedelta import relativedelta

LOGIN_BASE_URI = 'https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth'
API_BASE_URI = 'https://monespace.grdf.fr/'

base64string=""

userName = ""
password = ""
devicerowid = ""
devicerowidm3 = ""
nbDaysImported = 30
dbPath = ""
domoticzserver   = ""
domoticzusername = ""
domoticzpassword = ""

script_dir=os.path.dirname(os.path.realpath(__file__)) + os.path.sep

class GazparServiceException(Exception):
    """Thrown when the webservice threw an exception."""
    pass

def domoticzrequest (url):
  global base64string

  request = urllib.request.Request(url)
  if(domoticzusername != "" and domoticzpassword!= ""):
    base64string = base64.encodebytes(('%s:%s' % (domoticzusername, domoticzpassword)).encode()).decode().replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    
  try:  
    response = urllib.request.urlopen(request)
    return response.read()
  except urllib.error.HTTPError as e:
    print(e.__dict__)
    logging.error("Domoticz call - HttpError :"+str(e.__dict__)+'\n')
    exit()
  except urllib.error.URLError as e:
    print(e.__dict__)
    logging.error("Domoticz call - UrlError :"+str(e.__dict__)+'\n')
    exit()
  
# Date formatting 
def dtostr(date):
    return date.strftime("%Y-%m-%d")
    
def login():
    """Logs the user into the GRDF API.
    """
    session = requests.Session()

    payload = {
               'email': userName,
                'password': password,
                'goto':'https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code%26scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg%20%2FDemande.read%20%2FDemande.write%26client_id=prod_espaceclient%26state=0%26redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch%26nonce=7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag%26by_pass_okta=1%26capp=meg', 
                'capp':'meg'
               }
    headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': 'https://login.monespace.grdf.fr/mire/connexion?goto=https:%2F%2Fsofa-connexion.grdf.fr:443%2Fopenam%2Foauth2%2FexterneGrdf%2Fauthorize%3Fresponse_type%3Dcode%26scope%3Dopenid%2520profile%2520email%2520infotravaux%2520%252Fv1%252Faccreditation%2520%252Fv1%252Faccreditations%2520%252Fdigiconso%252Fv1%2520%252Fdigiconso%252Fv1%252Fconsommations%2520new_meg%2520%252FDemande.read%2520%252FDemande.write%26client_id%3Dprod_espaceclient%26state%3D0%26redirect_uri%3Dhttps%253A%252F%252Fmonespace.grdf.fr%252F_codexch%26nonce%3D7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag%26by_pass_okta%3D1%26capp%3Dmeg&realm=%2FexterneGrdf&capp=meg'
                }
    
    resp1 = session.post(LOGIN_BASE_URI, data=payload, headers=headers)
    #print (resp1.text)
    if resp1.status_code != requests.codes.ok:
        print("Login call - error status :"+resp1.status_code+'\n');
        logging.error("Login call - error status :"+resp1.status_code+'\n')
        exit()
    
    j = json.loads(resp1.text)
    if j['state'] != "SUCCESS":
        print("Login call - error status :"+j['state']+'\n');
        logging.error("Login call - error status :"+j['state']+'\n')
        exit()

    #2nd request
    headers = {
                'Referer': 'https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid profile email infotravaux /v1/accreditation /v1/accreditations /digiconso/v1 /digiconso/v1/consommations new_meg /Demande.read /Demande.write&client_id=prod_espaceclient&state=0&redirect_uri=https://monespace.grdf.fr/_codexch&nonce=7cV89oGyWnw28DYdI-702Gjy9f5XdIJ_4dKE_hbsvag&by_pass_okta=1&capp=meg'
                }

    resp2 = session.get(API_BASE_URI, allow_redirects=True)
    if resp2.status_code != requests.codes.ok:
        print("Login 2nd call - error status :"+resp2.status_code+'\n');
        logging.error("Login 2nd call - error status :"+resp2.status_code+'\n')
        exit()
    
    return session
    
def update_counters(session, start_date, end_date):
    #print('start_date: ' + start_date)
    #print('end_date: ' + end_date)
    
    #3nd request- Get NumPCE
    resp3 = session.get('https://monespace.grdf.fr/api/e-connexion/users/pce/historique-consultation')
    if resp3.status_code != requests.codes.ok:
        print("Get NumPce call - error status :",resp3.status_code, '\n');
        logging.error("Get NumPce call - error status :",resp3.status_code, '\n')
        exit()
    #print(resp3.text)
    
    j = json.loads(resp3.text)
    numPce = j[0]['numPce']
    
    data = get_data_with_interval(session, 'Mois', numPce, start_date, end_date)
    
    #print(data)
    j = json.loads(data)
    #print (j)
    index = j[str(numPce)]['releves'][0]['indexDebut']      
    #print(index)
    
    f = open(script_dir +"/req.sql", "w")
    for releve in j[str(numPce)]['releves']:
        #print(releve)
        req_date = releve['journeeGaziere']
        conso = releve['energieConsomme']
        volume = releve['volumeBrutConsomme']
        indexm3 = releve['indexDebut']
        try :
            index = index + conso
        except TypeError:
            print(req_date, conso, index, "Invalid Entry")
            continue;
        
        #print(req_date, conso, index)
        if devicerowid:
            domoticzrequest("http://" + domoticzserver + "/json.htm?type=command&param=udevice&idx=" + devicerowid + "&nvalue=0&svalue=" +str(index)+ ";" + str(int(conso)*1000) + ";" +req_date)
        if devicerowidm3:
            domoticzrequest("http://" + domoticzserver + "/json.htm?type=command&param=udevice&idx=" + devicerowidm3 + "&nvalue=0&svalue=" +str(indexm3)+ ";" + str(int(volume)) + ";" +req_date)
        
def get_data_with_interval(session, resource_id, numPce, start_date=None, end_date=None):
    r=session.get('https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut='+ start_date + '&dateFin=' + end_date + '&pceList[]=' + str(numPce))
    if r.status_code != requests.codes.ok:
        print("Get data - error status :"+r.status_code+'\n');
        logging.error("Get data - error status :",r.status_code, '\n')
        exit()
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
    global dbPath
    global domoticzserver
    global domoticzusername
    global domoticzpassword
    
    userName = config['GRDF']['GAZPAR_USERNAME']
    password = config['GRDF']['GAZPAR_PASSWORD']
    devicerowid = config['DOMOTICZ']['DOMOTICZ_ID']
    devicerowidm3 = config['DOMOTICZ']['DOMOTICZ_ID_M3']
    nbDaysImported = config['GRDF']['NB_DAYS_IMPORTED']
    dbPath = config['DOMOTICZ_SETTINGS']['DB_PATH']
    domoticzserver   = config['DOMOTICZ_SETTINGS']['HOSTNAME']
    domoticzusername = config['DOMOTICZ_SETTINGS']['USERNAME']
    domoticzpassword = config['DOMOTICZ_SETTINGS']['PASSWORD']
    
    
    #print("config : " + userName + "," + password + "," + devicerowid + "," + devicerowidm3 + "," + nbDaysImported )

# Main script 
def main():
    logging.basicConfig(filename=script_dir + '/domoticz_gazpar.log', format='%(asctime)s %(message)s', filemode='w', level=logging.INFO)

    try:
        # Get Configuration
        logging.info("Get configuration")
        get_config()
        
        # Login to GRDF API
        logging.info("logging in as %s...", userName)
        token = login()
        logging.info("logged in successfully!")

        today = datetime.date.today()

        # Update Counters Domoticz
        logging.info("retrieving data...")
        update_counters(token, dtostr(today - relativedelta(days=int(nbDaysImported))), \
                                             dtostr(today))
                                             
        logging.info("got data!")
    except GazparServiceException as exc:
        logging.error(exc)
        exit()

if __name__ == "__main__":
    main()
