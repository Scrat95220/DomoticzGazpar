#!/usr/bin/env python3
"""
@author: Scrat
"""
# grdf
# Copyright (C) 2024 Scrat
#
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
#
#
################################################################################
# SCRIPT DEPENDENCIES
################################################################################
import sys
import os
import signal
import time
import csv
import json
import logging
import argparse
import base64
import re
import subprocess
import glob
import openpyxl
import ssl
import urllib.request
from datetime import datetime
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode
from shutil import which

VERSION = "v1.3"

try:
    # Only add packages that are not built-in here
    import requests
    from colorama import Fore, Style
    from pyvirtualdisplay import Display, xauth
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError as exc:
    print(
        "Error: failed to import python required module : " + str(exc),
        file=sys.stderr,
    )
    sys.exit(2)

################################################################################
# Output Class in charge of managing all script output to file or console
################################################################################
class Output:
    def __init__(self, logs_folder=None, debug=False):
        self.__debug = debug
        self.__logger = logging.getLogger()
        self.__print_buffer = ""
        logs_folder = (
            os.path.dirname(os.path.realpath(__file__))
            if logs_folder is None
            else logs_folder
        )
        logfile = logs_folder + "/gazpar.log"

        # By default log to console
        self.print = self.__print_to_console

        # In standard mode log to a file
        if self.__debug is False:
            # Check if we can create logfile
            try:
                open(logfile, "a+", encoding="utf_8").close()
            except Exception as e:
                raise RuntimeError('"%s" %s' % (logfile, e,))

            # Set the logfile format
            file_handler = RotatingFileHandler(logfile, "a", 1000000, 1)
            formatter = logging.Formatter("%(asctime)s : %(message)s")
            file_handler.setFormatter(formatter)
            self.__logger.setLevel(logging.INFO)
            self.__logger.addHandler(file_handler)
            self.print = self.__print_to_logfile

    def __print_to_console(self, string="", st=None, end=None):
        if st:
            st = st.upper()
            st = st.replace("OK", Fore.GREEN + "OK")
            st = st.replace("WW", Fore.YELLOW + "WW")
            st = st.replace("EE", Fore.RED + "EE")
            st = "[" + st + Style.RESET_ALL + "] "

        if end is not None:
            st = st + " " if st else ""
            print(st + "%-75s" % (string,), end="", flush=True)
            self.__print_buffer = self.__print_buffer + string
        elif self.__print_buffer:
            st = st if st else "[--] "
            print(st + string.rstrip())
            self.__print_buffer = ""
        else:
            st = st if st else "[--]"
            print(("{:75s}" + st).format(string.rstrip()))
            self.__print_buffer = ""

    def __print_to_logfile(self, string="", st=None, end=None):
        if end is not None:
            self.__print_buffer = self.__print_buffer + string
        else:
            st = st if st else "--"
            self.__logger.info(
                "%s : %s %s",
                st.upper().lstrip(),
                self.__print_buffer.lstrip().rstrip(),
                string.lstrip().rstrip()
            )
            self.__print_buffer = ""


def document_initialised(driver):
    return driver.execute_script("return true;")

################################################################################
# Configuration Class toparse and load config.json
################################################################################
class Configuration:
    def __init__(self, super_print=None, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print   # type:ignore[assignment]

    def load_configuration_file(self, configuration_file):
        self.print(
            "Loading configuration file : " + configuration_file, end=""
        )  #############################################################
        try:
            with open(configuration_file, encoding="utf_8") as conf_file:
                content = json.load(conf_file)
        except json.JSONDecodeError as e:
            raise RuntimeError("json format error : " + str(e))
        except Exception:
            raise
        else:
            self.print(st="OK")
            return content


    def print(self, string="", st=None, end=None):
        st = "[" + st + "] " if st else ""
        if end is None:
            print(st + string)
        else:
            print(st + string + " ", end="", flush="True")  # type:ignore[call-overload]


################################################################################
# Object that retrieve the historical data from Grdf website
################################################################################
class GrdfCrawler:
    site_url = "https://monespace.grdf.fr/"
    download_filename = "Donnees_informatives*.xlsx"

    def __init__(self, config_dict, super_print=None, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print  # type:ignore[has-type]

        self.__display = None
        self.__browser = None  # type: webdriver.Firefox
        self.__wait = None  # type: WebDriverWait
        install_dir = os.path.dirname(os.path.realpath(__file__))
        self.configuration = {
            # Mandatory config values
            "grdf_login": None,
            "grdf_password": None,
            # Optional config values
            "geckodriver": which("geckodriver")
            if which("geckodriver")
            else install_dir + "/geckodriver",
            "firefox": which("firefox")
            if which("firefox")
            else install_dir + "/firefox",
            "chromium": which("chromium")
            if which("chromium")
            else which("chromium-browser") if which("chromium-browser")
            else install_dir + "/chromium",
            "chromedriver": which("chromedriver")
            if which("chromedriver")
            else install_dir + "/chromedriver",
            "timeout": "30",
            "download_folder": install_dir + os.path.sep,
            "logs_folder": install_dir + os.path.sep,
        }

        self.print("Start loading grdf configuration")
        try:
            self._load_configururation_items(config_dict)
            self.print("End loading grdf configuration", end="")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.__full_path_download_file = (
            str(self.configuration["download_folder"]) + self.download_filename
        )


    # Load configuration items
    def _load_configururation_items(self, config_dict):
        for param in list((self.configuration).keys()):
            if param not in config_dict:
                if self.configuration[param] is not None:
                    self.print(
                        '    "'
                        + param
                        + '" = "'
                        + str(self.configuration[param])
                        + '"',
                        end="",
                    )
                    self.print(
                        "param is not found in config file, using default value",
                        "WW",
                    )
                else:
                    self.print('    "' + param + '"', end="")
                    raise RuntimeError(
                        "param is missing in configuration file"
                    )
            else:
                if (
                    param in ("download_folder", "logs_folder",)
                ) and config_dict[param][-1] != os.path.sep:
                    self.configuration[param] = (
                        str(config_dict[param]) + os.path.sep
                    )
                else:
                    self.configuration[param] = config_dict[param]

                if param == "grdf_password":
                    self.print(
                        '    "'
                        + param
                        + '" = "'
                        + "*" * len(str(self.configuration[param]))
                        + '"',
                        end="",
                    )
                else:
                    self.print(
                        '    "'
                        + param
                        + '" = "'
                        + str(self.configuration[param])
                        + '"',
                        end="",
                    )

                self.print(st="OK")

    # INIT DISPLAY & BROWSER
    def init_browser_firefox(self):
        self.print(
            "Start virtual display", end=""
        )  #############################################################
        # website needs at least 1600x1200 to render all components
        if self.__debug:
            self.__display = Display(visible=1, size=(1600, 1200))
        else:
            self.__display = Display(visible=0, size=(1600, 1200))
        try:
            self.__display.start()
        except Exception as e:
            raise RuntimeError(
                str(e)
                + "if you launch the script through a ssh connection with '--debug' ensure X11 forwarding is activated"
            )
        else:
            self.print(st="OK")

        self.print(
            "Setup Firefox profile", end=""
        )  #############################################################
        try:
            # Enable Download
            opts = webdriver.FirefoxOptions()
            fp = webdriver.FirefoxProfile()
            opts.profile = fp
            fp.set_preference(
                "browser.download.dir", self.configuration["download_folder"]
            )
            fp.set_preference("browser.download.folderList", 2)
            fp.set_preference(
                "browser.helperApps.neverAsk.saveToDisk", "text/csv"
            )
            fp.set_preference(
                "browser.download.manager.showWhenStarting", False
            )
            fp.set_preference(
                "browser.helperApps.neverAsk.openFile", "text/csv"
            )
            fp.set_preference("browser.helperApps.alwaysAsk.force", False)

            # Set firefox binary to use
            opts.binary_location = FirefoxBinary(str(self.configuration["firefox"]))

            service = FirefoxService(self.configuration["geckodriver"])
            if not hasattr(service, 'process'):
                # Webdriver may complain about missing process.
                service.process = None

            # Enable the browser
            try:
                self.__browser = webdriver.Firefox(
                    options=opts,
                    service_log_path=str(self.configuration["logs_folder"])
                    + "/geckodriver.log",
                    service=service,
                )
            except Exception as e:
                raise RuntimeError(
                    str(e)
                    + "if you launch the script through a ssh connection with '--debug' ensure X11 forwarding is activated, and you have a working X environment. debug mode start Firefox and show all clicks over the website"
                )
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print(
            "Start Firefox", end=""
        )  #############################################################
        try:
            # self.__browser.maximize_window()
            # replacing maximize_window by set_window_size to get the window full screen
            self.__browser.set_window_size(1600, 1200)
            timeout = int(self.configuration["timeout"])  # type: ignore[arg-type]
            self.__wait = WebDriverWait(
                self.__browser, timeout=timeout
            )
        except Exception:
            raise
        else:
            self.print(st="OK")

    def init_browser_chrome(self):
        # Set Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-modal-animations")
        options.add_argument("--disable-login-animations")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-wndows")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-popup-blocking")
        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": self.configuration[
                    "download_folder"
                ],
                "profile.default_content_settings.popups": 0,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "extensions_to_open": "text/csv",
                "safebrowsing.enabled": True,
            },
        )

        self.print(
            "Start virtual display (chromium)", end=""
        )  #############################################################
        if self.__debug:
            self.__display = Display(visible=1, size=(1280, 1024))
        else:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            try:
                self.__display = Display(visible=0, size=(1280, 1024))
            except Exception:
                raise

        try:
            self.__display.start()
        except Exception:
            raise
        else:
            self.print(st="OK")

        self.print(
            "Start the browser", end=""
        )  #############################################################
        try:
            self.__browser = webdriver.Chrome(
                executable_path=self.configuration["chromedriver"],
                options=options,
            )
            self.__browser.maximize_window()
            timeout = int(self.configuration["timeout"])  # type: ignore[arg-type]
            self.__wait = WebDriverWait(
                self.__browser, timeout
            )
        except Exception:
            raise
        else:
            self.print(st="OK")

    def sanity_check(self, debug=False):  # pylint: disable=unused-argument

        self.print(
            "Check download location integrity", end=""
        )  #############################################################
        if os.path.exists(self.__full_path_download_file):
            self.print(
                self.__full_path_download_file
                + " already exists, will be removed",
                "WW",
            )
        else:
            try:
                open(self.__full_path_download_file, "a+", encoding="utf_8").close()
            except Exception as e:
                raise RuntimeError(
                    '"%s" %s' % (self.__full_path_download_file, e,)
                )
            else:
                self.print(st="ok")

        #############################################################
        try:
            self.print( "Remove temporary download file", end="")
            os.remove(self.__full_path_download_file)
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print(
            'Check availability of "geckodriver"+"firefox" or "chromedriver"+"chromium"', end=""

        )  #############################################################
        if ( os.access(str(self.configuration["geckodriver"]), os.X_OK) and
           os.access(str(self.configuration["firefox"]), os.X_OK)):
            self.print(st="ok")
            self.print(
                "Check firefox browser version", end=""
            )  #############################################################
            try:
                major, minor = self.__get_firefox_version()
            except Exception:
                raise
            else:
                if (major, minor) < (60, 9):
                    self.print(
                        "Firefox version ("
                        + str(major)
                        + "."
                        + str(minor)
                        + " is too old (< 60.9) script may fail",
                        st="WW",
                    )
                else:
                    self.print(st="ok")
        elif (os.access(str(self.configuration["chromedriver"]), os.X_OK) and
             os.access(str(self.configuration["chromium"]), os.X_OK)):
            self.print(st="ok")
        else:
            raise OSError(
                '"%s"/"%s" or "%s"/"%s": no valid pair of executables found' % (
                  self.configuration["geckodriver"],
                  self.configuration["firefox"],
                  self.configuration["chromedriver"],
                  self.configuration["chromium"],
                )
            )



    def __get_firefox_version(self):
        try:
            output = subprocess.check_output(
                [str(self.configuration["firefox"]), "--version"]
            )
        except Exception:
            raise

        try:
            major, minor = map(
                int, re.search(r"(\d+).(\d+)", str(output)).groups()  # type:ignore[union-attr]
            )
        except Exception:
            raise

        return major, minor


    def clean_up(self, debug=False, keep_csv=False):
        self.print(
            "Close Browser", end=""
        )  #############################################################
        if self.__browser:
            try:
                self.__browser.quit()
            except Exception as _e:
                os.kill(self.__browser.service.process.pid, signal.SIGTERM)
                self.print(
                    "selenium didn't properly close the process, so we kill firefox manually (pid="
                    + str(self.__browser.service.process.pid)
                    + ")",
                    "WW",
                )
            else:
                self.print(st="OK")
        else:
            self.print(st="OK")

        self.print(
            "Close Display", end=""
        )  #############################################################
        if self.__display:
            try:
                self.__display.stop()
            except:
                raise
            else:
                self.print(st="ok")

        # Remove downloaded file
        try:
            file_list = glob.glob(self.__full_path_download_file)
            for file_path in file_list:
                if not debug and not keep_csv and os.path.exists(file_path):
                    #############################################################
                    # Remove file
                    self.print( "Remove downloaded file " + file_path, end="")
                    os.remove(file_path)
                else:
                    self.print(st="ok")
        except Exception as e:
            self.print(str(e), st="EE")

    def wait_until_disappeared(self, method, key, wait_message=None):
        """Wait until element is gone"""
        if wait_message is None:
            wait_message = "Wait for missing %s" % (key,)
        self.print(wait_message, end="")

        ep = EC.visibility_of_element_located(
            (
                method,
                key,
            )
        )

        timeout_message = "Failed, page timeout (timeout=%s)" % (
            str(self.configuration["timeout"]),
        )
        self.__wait.until_not(ep, message=timeout_message)

        self.print(st="ok")

    def click_in_view(  # pylint: disable=R0913
        self, method, key, click_message=None, wait_message=None, delay=0
    ):
        """
        1. Wait until element is visible
        2. Wait for delay.
        3. Bring into view (location may have changed)
        4. Click
        """
        # Wait until element is visible
        ep = EC.visibility_of_element_located(
            (
                method,
                key,
            )
        )

        if wait_message is None:
            wait_message = "Wait for Button %s" % (key,)
        self.print(wait_message, end="")

        timeout_message = "Failed, page timeout (timeout=%s)" % (
            str(self.configuration["timeout"]),
        )
        el = self.__wait.until(ep, message=timeout_message)

        self.print(st="ok")

        if delay != 0.0:
            self.print("Wait before clicking (%.1fs)" % (delay,), end="")
            self.print(st="~~")
            time.sleep(delay)

        # Bring the element into view
        el.location_once_scrolled_into_view

        # Click
        if click_message is None:
            click_message = "Click on %s" % (key,)
        self.print(click_message, end="")

        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")

    def get_file(self):

        ###### Wait for Connexion #####
        self.print("Connexion au site GRDF", end="")

        self.__browser.get(self.__class__.site_url)
        self.print(st="ok")

        ###### Wait for Email #####
        self.print("Waiting for Email", end="")

        ee = EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[id="input27"]')
        )
        el_email = self.__wait.until(
            ee,
            message="failed, page timeout (timeout="
            + str(self.configuration["timeout"])
            + ")",
        )
        self.print(st="ok")

        ###### Type Email #####
        self.print("Type Email", end="")
        el_email.clear()
        el_email.send_keys(self.configuration["grdf_login"])
        self.print(st="ok")

        ###### Click Submit #####
        self.click_in_view(
            By.CLASS_NAME,
            "button",
            wait_message="Waiting for submit button",
            click_message="Click on submit button",
            delay=1,
        )

        time.sleep(10)

        ###### Wait until spinner is gone #####
        self.wait_until_disappeared(By.CSS_SELECTOR, "auth-content-inner")
        time.sleep(1)
        
        ###### Wait for Password #####
        self.print("Waiting for Password", end="")

        ep = EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[type="password"]')
        )
        el_password = self.__wait.until(
            ep,
            message="failed, page timeout (timeout="
            + str(self.configuration["timeout"])
            + ")",
        )
        self.print(st="ok")

        ###### Type Password #####
        self.print("Type Password", end="")
        el_password.clear()
        el_password.send_keys(self.configuration["grdf_password"])
        self.print(st="ok")

        ###### Click Submit #####
        self.click_in_view(
            By.CLASS_NAME,
            "button",
            wait_message="Waiting for submit button",
            click_message="Click on submit button",
            delay=1,
        )

        time.sleep(3)

        ###### Wait until spinner is gone #####
        self.wait_until_disappeared(By.CSS_SELECTOR, "auth-content-inner")
        time.sleep(1)

        ### Consommation detaillée

        self.print("Wait for Voir ma consommation détaillée", end="")
        ep = EC.visibility_of_element_located(
            (
                By.XPATH,
                "//a[contains(text(), ' Voir ma consommation détaillée')]",
            )
        )
        el = self.__wait.until(
            ep,
            message="failed, page timeout (timeout="
            + str(self.configuration["timeout"])
            + ")",
        )
        self.print(st="ok")

        time.sleep(2)

        menu_type = str(el.get_attribute("innerHTML"))

        ###### Click on button #####
        self.print("Click on button : " + menu_type, end="")

        el.click()

        self.print(st="ok")
       
        ###### Click Jour #####
        self.click_in_view(
            By.XPATH,
            "//label[contains(text(), 'Jour')]",
            wait_message="Wait for Jour",
            click_message="Click on Jour",
            delay=2,
        )
        
        ###### Click Telechargement #####       
        self.click_in_view(
            By.CLASS_NAME,
            "button-download",
            wait_message="Wait for button Téléchargement",
            click_message="Click on button Téléchargement",
            delay=2,
        )
        
        ###### Click Telecharger #####     
        element = self.__browser.find_element_by_class_name('forms-button')
        self.__browser.execute_script("arguments[0].click();", element)        

        self.print(
            "Wait for end of download to " + self.__full_path_download_file,
            end="",
        )  #############################################################
        t = int(str(self.configuration["timeout"]))
        while t > 0 and not glob.glob(self.__full_path_download_file):
            time.sleep(1)
            t -= 1
        if glob.glob(self.__full_path_download_file):
            self.print(st="ok")
            file_list = glob.glob(self.__full_path_download_file)
        else:
            try:
                error_img = "%serror.png" % (
                    self.configuration["logs_folder"],
                )
                self.print("Get & Save '%s'" % (error_img,), end="")
                # img = self.__display.waitgrab()
                self.__browser.get_screenshot_as_file(error_img)
            except Exception as e:
                self.print("Exception while getting image: %s" % (e,), end="")
            raise RuntimeError("File download timeout")

        self.print(st="FileName:" + file_list[0])
        return file_list[0]


################################################################################
# Object injects historical data into domoticz
################################################################################
class DomoticzInjector:
    def __init__(self, config_dict, super_print, debug=False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print  # type:ignore[has-type]

        self.configuration = {
            # Mandatory config values
            "domoticz_idx": None,
            "domoticz_server": None,
            "grdf_nbDaysImported": 0,
            # Optional config values
            "domoticz_idx_m3": None,
            "domoticz_login": "",
            "domoticz_password": "",
            "timeout": "30",
            "download_folder": os.path.dirname(os.path.realpath(__file__))
            + os.path.sep,
        }
        self.print("Start Loading Domoticz configuration")
        try:
            self._load_configururation_items(config_dict)
            self.print("End loading domoticz configuration", end="")
        except Exception:
            raise
        else:
            self.print(st="ok")

    def open_url(self, uri, data=None):  # pylint: disable=unused-argument
        # Generate URL
        global base64string

        context = ssl._create_unverified_context()        
        request = urllib.request.Request(str(self.configuration["domoticz_server"]) + uri)

        if self.configuration["domoticz_login"] != "" and self.configuration["domoticz_password"] != "":
            base64string = base64.encodebytes(('%s:%s' % (self.configuration["domoticz_login"], self.configuration["domoticz_password"])).encode()).decode().replace('\n', '')
            request.add_header("Authorization", "Basic %s" % base64string)

        try:
            response = urllib.request.urlopen(request, timeout=int(str(self.configuration["timeout"])), context=context)
        except urllib.error.HTTPError as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError("url=" + request + " : " + str(e))
        except urllib.error.URLError as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError("url=" + request + " : " + str(e))

        # HANDLE SERVER ERROR CODE
        if not response.status == 200:
            raise RuntimeError(
                "url="
                + request
                + " - (code = "
                + str(response.status)
                + ")\ncontent="
                + str(response.data)
            )
        
        return json.loads(str(response.read().decode(response.headers.get_content_charset())))

    # Load configuration items
    def _load_configururation_items(self, config_dict):
        for param in list((self.configuration).keys()):
            if param not in config_dict:
                if self.configuration[param] is not None:
                    self.print(
                        '    "%s" = "%s"' % (
                            param,
                            self.configuration[param],
                        ),
                        end="",
                    )
                    self.print(
                        "param is not found in config file, using default value",
                        "WW",
                    )
                else:
                    self.print('    "' + param + '"', end="")
                    raise RuntimeError(
                        "param is missing in configuration file"
                    )
            else:
                if (
                    param == "download_folder"
                    and str(config_dict[param])[-1] != os.path.sep
                ):
                    self.configuration[param] = (
                        str(config_dict[param]) + os.path.sep
                    )
                else:
                    self.configuration[param] = config_dict[param]

                if re.match(r".*(token|password).*", param, re.IGNORECASE):
                    self.print(
                        '    "'
                        + param
                        + '" = "'
                        + "*" * len(str(self.configuration[param]))
                        + '"',
                        end="",
                    )
                else:
                    self.print(
                        '    "'
                        + param
                        + '" = "'
                        + str(self.configuration[param])
                        + '"',
                        end="",
                    )

                self.print(st="OK")

    def sanity_check(self, debug=False):  # pylint: disable=unused-argument
        self.print(
            "Check domoticz connectivity", st="--", end=""
        )  #############################################################
        response = self.open_url("/json.htm?type=command&param=getversion")
        if response["status"].lower() == "ok":
            self.print(st="ok")

        self.print(
            "Check domoticz Device", end=""
        )  #############################################################
        # generate 2 urls, one for historique, one for update
        response = self.open_url(
            "/json.htm?type=devices&rid=" + str(self.configuration["domoticz_idx"])
        )

        if not "result" in response:
            raise RuntimeError(
                "device "
                + str(self.configuration["domoticz_idx"])
                + " could not be found on domoticz server "
                + str(self.configuration["domoticz_server"])
            )
        else:
            properly_configured = True
            dev_AddjValue = response["result"][0]["AddjValue"]
            dev_AddjValue2 = response["result"][0]["AddjValue2"]
            dev_SubType = response["result"][0]["SubType"]
            dev_Type = response["result"][0]["Type"]
            dev_SwitchTypeVal = response["result"][0]["SwitchTypeVal"]
            dev_Name = response["result"][0]["Name"]

            self.print(st="ok")

            # Retrieve Device Name
            self.print(
                '    Device Name            : "'
                + dev_Name
                + '" (idx='
                + self.configuration["domoticz_idx"]
                + ")",
                end="",
            )  #############################################################
            self.print(st="ok")

            # Checking Device Type
            self.print(
                '    Device Type            : "' + dev_Type + '"', end=""
            )  #############################################################
            if dev_Type == "General":
                self.print(st="ok")
            else:
                self.print(
                    'wrong sensor type. Go to Domoticz/Hardware - Create a pseudo-sensor type "Managed Counter"',
                    st="EE",
                )
                properly_configured = False

            # Checking device subtype
            self.print(
                '    Device SubType         : "' + dev_SubType + '"', end=""
            )  #############################################################
            if dev_SubType == "Managed Counter":
                self.print(st="ok")
            else:
                self.print(
                    'wrong sensor type. Go to Domoticz/Hardware - Create a pseudo-sensor type "Managed Counter"',
                    st="ee",
                )
                properly_configured = False

            # Checking for SwitchType
            self.print(
                '    Device SwitchType      : "' + str(dev_SwitchTypeVal),
                end="",
            )  #############################################################
            if dev_SwitchTypeVal == 0:
                self.print(st="ok")
            else:
                self.print(
                    "wrong switch type. Go to Domoticz - Select your counter - click edit - change type to Energy",
                    st="ee",
                )
                properly_configured = False

            # Checking for Counter Divider
            self.print(
                '    Device Counter Divided : "' + str(dev_AddjValue2) + '"',
                end="",
            )  #############################################################
            if dev_AddjValue2 == 0:
                self.print(st="ok")
            else:
                self.print(
                    'wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 0',
                    st="ee",
                )
                properly_configured = False

            # Checking Meter Offset
            self.print(
                '    Device Meter Offset    : "' + str(dev_AddjValue) + '"',
                end="",
            )  #############################################################
            if dev_AddjValue == 0:
                self.print(st="ok")
            else:
                self.print(
                    'wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0',
                    st="ee",
                )
                properly_configured = False

            if properly_configured is False:
                raise RuntimeError(
                    "Set your device correctly and run the script again"
                )

    def update_device(self, xlsx_file):
        devicerowid = str(self.configuration["domoticz_idx"])
        devicerowidm3 = str(self.configuration["domoticz_idx_m3"])
        nbDaysImported = self.configuration["grdf_nbDaysImported"]
        
        workbook = openpyxl.load_workbook(xlsx_file)
        sheet = workbook.active 
        nbRows = sheet.max_row
        index = sheet.cell(row=10, column=4).value
            
        if(int(nbDaysImported)>nbRows):
            self.print("nbDaysImported max allowed is " + str(nbRows-9))
            exit()
            
        #i : inital date to import
        i=nbRows-int(nbDaysImported)+1
        while nbRows+1 > i:
            req_date = sheet.cell(row=i, column=2).value
            conso = sheet.cell(row=i, column=6).value
            indexm3 = sheet.cell(row=i, column=4).value
            req_date_time = sheet.cell(row=i, column=2).value 
            volume = sheet.cell(row=i, column=5).value 
            
            i = i+1
            
            try :
                index = index + conso
            except TypeError:
                self.print(req_date, conso, index, "Invalid Entry")
                continue;
                
            date_time = datetime.strptime(req_date_time, '%d/%m/%Y').strftime("%Y-%m-%d %H:%M:%S")
            req_date = datetime.strptime(req_date, '%d/%m/%Y').strftime("%Y-%m-%d")
            
            #print(req_date, conso, index)
            if devicerowid:
                
                # Generate URLs, for historique and for update
                args = {'type': 'command', 'param': 'udevice', 'idx': devicerowid, 'svalue': str(index) + ";" + str(int(conso)*1000) + ";" + req_date}
                url_historique = '/json.htm?' + urlencode(args)
                 
                args['svalue'] = str(index)  + ";" + str(int(conso)*1000) + ";" + date_time
                url_daily = '/json.htm?' + urlencode(args)

                args['svalue'] = str(int(conso)*1000)
                url_current = '/json.htm?' + urlencode(args)
                self.print(url_current)
                
                #print(url_historique)
                self.open_url(url_historique)
                
            if devicerowidm3:
                
                # Generate URLs, for historique and for update
                args_m3 = {'type': 'command', 'param': 'udevice', 'idx': devicerowidm3, 'svalue': str(indexm3) + ";" + str(volume) + ";" + req_date}
                url_historique_m3 = '/json.htm?' + urlencode(args_m3)
                
                args_m3['svalue'] = str(indexm3)  + ";" + str(volume) + ";" + date_time
                url_daily_m3 = '/json.htm?' + urlencode(args_m3)

                args_m3['svalue'] = str(volume)
                url_current_m3 = '/json.htm?' + urlencode(args_m3)
                
                self.open_url(url_historique_m3)
                
        
        if devicerowid:
            self.open_url(url_current)
            self.open_url(url_daily)
        
        if devicerowidm3:
            self.open_url(url_current_m3)
            self.open_url(url_daily_m3)


    def clean_up(self, debug=False):
        pass

def exit_on_error(grdf_obj=None, domoticz=None, string="", debug=False):
    try:
        o
    except:
        print(string)
    else:
        o.print(string, st="EE")

    if grdf_obj is not None:
        grdf_obj.clean_up(debug)
    if domoticz:
        domoticz.clean_up(debug)
    try:
        o
    except:
        print("Ended with error%s" % ("" if debug else " : // re-run the program with '--debug' option",))
    else:
        o.print(
            "Ended with error%s" % ("" if debug else " : // re-run the program with '--debug' option",),
            st="EE",
        )
    sys.exit(2)


if __name__ == "__main__":
    # Default config value
    script_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
    default_logfolder = script_dir
    default_configuration_file = script_dir + "/config.json"

    # COMMAND LINE OPTIONS
    parser = argparse.ArgumentParser(
        description="Load Gaz consumption from GRDF website into domoticz"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="active graphical debug mode (only for troubleshooting)",
    )
    parser.add_argument(
        "-l",
        "--logs-folder",
        help="specify the logs location folder (" + default_logfolder + ")",
        default=default_logfolder,
        nargs=1,
    )
    parser.add_argument(
        "-c",
        "--config",
        help="specify configuration location ("
        + default_configuration_file
        + ")",
        default=default_configuration_file,
        nargs=1,
    )
    parser.add_argument(
        "-r",
        "--run",
        action="store_true",
        help="run the script",
        required=True,
    )
    parser.add_argument(
        "-k",
        "--keep_csv",
        action="store_true",
        help="Keep the downloaded CSV file",
        required=False,
    )
    args = parser.parse_args()

    # Init output
    try:
        o = Output(
            logs_folder=str(args.logs_folder).strip("[]'"), debug=args.debug
        )
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Print debug message
    if args.debug:
        o.print("DEBUG MODE ACTIVATED", end="")
        o.print("only use '--debug' for troubleshooting", st="WW")

    # Load configuration
    try:
        c = Configuration(debug=args.debug, super_print=o.print)
        configuration_json = c.load_configuration_file(
            str(args.config).strip("[]'")
        )
        configuration_json["logs_folder"] = str(args.logs_folder).strip("[]'")
    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Create objects
    try:
        grdf = GrdfCrawler(
            configuration_json, super_print=o.print, debug=args.debug
        )
        server_type = configuration_json.get("type",None)
        server = DomoticzInjector(
            configuration_json, super_print=o.print, debug=args.debug
        )

    except Exception as exc:
        exit_on_error(string=str(exc), debug=args.debug)

    # Check requirements
    try:
        grdf.sanity_check(args.debug)
    except Exception as exc:
        exit_on_error(grdf, server, str(exc), debug=args.debug)

    try:
        server.sanity_check(args.debug)
    except Exception as exc:
        exit_on_error(grdf, server, str(exc), debug=args.debug)

    try:
        grdf.init_browser_firefox()
    except (Exception, xauth.NotFoundError) as exc:
        o.print(st="~~")
        try:
            grdf.init_browser_chrome()
        except Exception as exc_inner:
            exit_on_error(grdf, server, str(exc_inner), debug=args.debug)

    try:
        data_file = grdf.get_file()
    except Exception as exc:
        # Retry once on failure to manage stalement exception that occur sometimes
        try:
            o.print(
                "Encountered error" + str(exc).rstrip() + "// -> Retrying once",
                st="ww",
            )
            data_file = grdf.get_file()
        except Exception as exc_inner:
            exit_on_error(grdf, server, str(exc_inner), debug=args.debug)

    try:
        server.update_device(data_file)
    except Exception as exc:
        exit_on_error(grdf, server, str(exc), debug=args.debug)

    grdf.clean_up(debug=args.debug, keep_csv=args.keep_csv)
    o.print("Finished on success")
    sys.exit(0)
