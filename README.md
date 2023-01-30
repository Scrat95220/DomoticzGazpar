# DomoticzGazpar
Import data from GDRF to Domoticz

# create a device in Domoticz
- In Domoticz, go to hardware, create a virtual "Managed counter".
  You may as well create a virtual 'Managed counter, Gas' device in m3 (to do so : create first a Managed counter, then modify it in the Utility tab to change Switch type to Gas)
- Then in Devices, add it to the devices. (mark down the id for later).

## modules to install - linux

    sudo apt-get install python3 python3-dateutil python3-requests
	pip install openpyxl
    git clone https://github.com/Scrat95220/DomoticzGazpar.git
	
## Workaround due to the CATPCHA issue
- The script will try to import the GRDF xlsx file if the connection to the API fail.
- Go to the GRDF website, import the XLSX data in "Jour". Use de attribute XLS_PATH for set the path of your file (example: grdf.xlsx)

### rename configuration file, change settings

    cp _domoticz_gazpar.cfg domoticz_gazpar.cfg
    nano domoticz_gazpar.cfg

and change:

    GAZPAR_USERNAME=nom.prenom@mail.com
    GAZPAR_PASSWORD=password
    NB_DAYS_IMPORTED=30
	XLS_PATH=path to your xlsx file imported
    DOMOTICZ_ID=123
    DOMOTICZ_ID_M3=456
	DB_PATH=/home/pi/domoticz (if needed)
	HOSTNAME=https://localhost:8080 
	USERNAME = 
	PASSWORD = 

Where NB_DAYS_IMPORTED correspond to the number of days to import and DOMOTICZ_ID is id device on domoticz and
DOMOTICZ_ID_M3 is the id device of a virtual 'Smart Meter, Gas' device in m3 if exists

Configuration file will not be deleted in future updates.

## testing before launch

Manually launch

    ./gazpar.py


Then check the login credential if they are ok:

    domoticz_gazpar.log

If this is good, you'll get several json files in the directory

## Add to your cron tab (with crontab -e):

    30 7,17 * * * python3 /home/pi/domoticz/DomoticzGazpar/gazpar.py
