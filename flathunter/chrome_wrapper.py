"""Chrome needs some special handling to work out where the correct
binary is, to attach the correct selenium chromedriver, and to set
the correct version number"""
import re
import subprocess
import undetected_chromedriver as uc

from flathunter.logging import logger

CHROME_VERSION_REGEXP = re.compile(r'.* (\d+\.\d+\.\d+\.\d+)( .*)?')

def get_command_output(args):
    """Run a command and return the first line of stdout"""
    try:
        with subprocess.Popen(args,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True) as process:
            if process.stdout is None:
                return None
            return process.stdout.readline()
    except FileNotFoundError:
        return None

def get_chrome_version():
    """Determine the correct name for the chrome binary"""
    for binary_name in ['google-chrome', 'chromium', 'chrome']:
        try:
            version = get_command_output([binary_name, '--version'])
            if version is None:
                continue
            match = CHROME_VERSION_REGEXP.match(version)
            if match is None:
                continue
            return int(match.group(1).split('.')[0])
        except FileNotFoundError:
            pass
    return None

def get_chrome_driver(driver_arguments):
    """Configure Chrome WebDriver"""
    logger.info('Initializing Chrome WebDriver for crawler...')
    chrome_options = uc.ChromeOptions() # pylint: disable=no-member
    if driver_arguments is not None:
        for driver_argument in driver_arguments:
            chrome_options.add_argument(driver_argument)
    chrome_version = get_chrome_version()
    driver = uc.Chrome(version_main=chrome_version, options=chrome_options) # pylint: disable=no-member

    driver.execute_cdp_cmd('Network.setBlockedURLs',
        {"urls": ["https://api.geetest.com/get.*"]})
    driver.execute_cdp_cmd('Network.enable', {})
    return driver
