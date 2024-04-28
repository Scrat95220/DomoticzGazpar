# DomoticzGazpar
Import data from GDRF to Domoticz

## Création du "Virtual Sensor" in Domoticz :
	* Créer un Matériel de Type "Dummy" -> Domoticz / Setup / Hardware / Dummy
	* Créer un "Virtual Sensor" de type : "Managed Counter"
	* Configurer le sensor -> Domoticz / Utility / [Bouton "edit" de votre sensor]
	  * Type Counter : energy
	  * Counter Divider : 0
	  * Meter Offset : 0
	  
	* Créer un Matériel de Type "Dummy" -> Domoticz / Setup / Hardware / Dummy
	* Créer un "Virtual Sensor" de type : "Managed Counter"
	* Configurer le sensor -> Domoticz / Utility / [Bouton "edit" de votre sensor]
	  * Type Counter : gas
	  * Counter Divider : 1000
	  * Meter Offset : 0

## prerequisites :
	* `firefox`+`geckodriver` OR `chromium`+`chromium-driver`
	* python 3
	* xvfb
	* xephyr (recommandé)
	* modules python :
	  * selenium
	  * pyvirtualdisplay
	  * colorama
	  * urllib
	  * Some others

## modules to install - linux

    sudo apt-get install python3 python3-dateutil python3-requests firefox firefox-geckodriver xvfb xserver-xephyr python3-selenium python3-pyvirtualdisplay python3-colorama
	pip install openpyxl
    git clone https://github.com/Scrat95220/DomoticzGazpar.git
	

### rename configuration file, change settings

    cp config.json.exemple config.json
    nano config.json


## Launch

Manually launch

    ./gazpar.py --run