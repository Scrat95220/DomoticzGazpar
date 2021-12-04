# DomoticzGazpar
Import data from GDRF to Domoticz

# create a device in Domoticz
- In Domoticz, go to hardware, create a virtual "rfx meter counter" or "Dummy".
  You may as well create a virtual 'Smart Meter, Gas' device in m3
- Then in Devices, add it to the devices. (mark down the id for later).
- When in Utility, edit the device and change it to Electric (instant+counter) type.

## modules to install - linux

    sudo apt-get install sqlite3
    sudo apt-get install python3 python3-dateutil python3-requests
    git clone https://github.com/Scrat95220/DomoticzGazpar.git

### rename configuration file, change login/pass/id

    cp _domoticz_gazpar.cfg domoticz_gazpar.cfg
    nano domoticz_gazpar.cfg

and change:

    GAZPAR_USERNAME=nom.prenom@mail.com
    GAZPAR_PASSWORD=password
    NB_DAYS_IMPORTED=30
    DOMOTICZ_ID=123
    DOMOTICZ_ID_M3=456
	DB_PATH=/home/pi/domoticz (if needed)

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

    30 7,17 * * * /home/pi/domoticz/DomoticzGazpar/python3 gazpar.py
