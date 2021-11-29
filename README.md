# DomoticzGazpar
Import data from GDRF to Domoticz

# create a device in Domoticz
- In Domoticz, go to hardware, create a virtual "rfx meter counter" or "Dummy".
- Then in Devices, add it to the devices. (mark down the id for later).
- When in Utility, edit the device and change it to Electric (instant+counter) type.

## modules to install - linux

    sudo apt-get install sqlite3 nodejs npm
    sudo apt-get install python3 python3-dateutil python3-requests
    git clone https://github.com/Scrat95220/DomoticzGazpar.git

### rename configuration file, change login/pass/id

    cp _domoticz_gazpar.cfg domoticz_gazpar.cfg
    nano domoticz_gazpar.cfg

and change:

    GASPAR_USERNAME="nom.prenom@mail.com"
    GASPAR_PASSWORD="password"
    NB_DAYS_IMPORTED=30
    DOMOTICZ_ID=123

Where NB_DAYS_IMPORTED correspond to the number of days to impirt and DOMOTICZ_ID is id device on domoticz. 

Configuration file will not be deleted in future updates.

## testing before launch

Manually launch

    ./domoticz_gazpar.sh

N.B. If login is not ok, you'll get a nodejs error on console for data will be missing (will be changed).

Then check the login credential if they are ok:

    domoticz_gazpar.log

If this is good, you'll get several json files in the directory

## Add to your cron tab (with crontab -e):

    30 7,17 * * * /home/pi/domoticz/DomoticzGazpar/domoticz_gazpar.sh
