"""Chrome needs some special handling to work out where the correct
binary is, to attach the correct selenium chromedriver, and to set
the correct version number"""
import os
import re
import shutil
import subprocess
from platform import machine
from typing import List
from sys import platform
import undetected_chromedriver as uc

from flathunter.logging import logger
from flathunter.exceptions import ChromeNotFound

CHROME_VERSION_REGEXP = re.compile(r'.* (\d+\.\d+\.\d+\.\d+)( .*)?')
WINDOWS_CHROME_REG_PATH = r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon'
WINDOWS_CHROME_REG_REGEXP = re.compile(r'\s*version\s*REG_SZ\s*(\d+)\..*')
CHROME_BINARY_NAMES = ['google-chrome', 'chromium', 'chrome', 'chromium-browser',
                       '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']

def get_command_output(args) -> List[str]:
    """Run a command and return stdout"""
    try:
        with subprocess.Popen(args,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True) as process:
            if process.stdout is None:
                return []
            return process.stdout.readlines()
    except FileNotFoundError:
        return []

def get_chrome_version() -> int:
    """Determine the correct name for the chrome binary"""
    for binary_name in CHROME_BINARY_NAMES:
        try:
            version_output = get_command_output([binary_name, '--version'])
            if not version_output:
                continue
            match = CHROME_VERSION_REGEXP.match(version_output[0])
            if match is None:
                continue
            return int(match.group(1).split('.')[0])
        except FileNotFoundError:
            pass
    try:
        # on Windows, Chrome doesn't respond to --version, but we can find
        # the version in the registry
        output = get_command_output(
            ['reg', 'query', WINDOWS_CHROME_REG_PATH, '/v', 'version']
        )
        version_matches = (WINDOWS_CHROME_REG_REGEXP.match(l) for l in output)
        version_matches = [m for m in version_matches if m is not None]
        if version_matches:
            return int(version_matches[0].group(1))
    except FileNotFoundError:
        pass
    raise ChromeNotFound()

ARM_MACHINES = ('armv6l', 'armv7l', 'aarch64', 'arm64')
SYSTEM_CHROMEDRIVER_PATH = '/usr/bin/chromedriver'

def get_system_chromedriver_path():
    """Return a pre-patched copy of the system chromedriver for ARM platforms.

    undetected_chromedriver only downloads x86-64 chromedriver builds. On ARM
    (Raspberry Pi, ARM NAS, etc.) running such a build fails with
    "OSError: [Errno 8] Exec format error". When the OS provides a matching ARM
    chromedriver, copy it into uc's cache directory, patch it in place, and return
    the path so it can be passed to uc.Chrome via driver_executable_path.

    Returns None on non-ARM platforms or when no system chromedriver is installed,
    in which case uc downloads and manages the driver as usual."""
    if machine() not in ARM_MACHINES:
        return None
    if not os.path.exists(SYSTEM_CHROMEDRIVER_PATH):
        return None
    cache_dir = os.path.expanduser('~/.local/share/undetected_chromedriver')
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, 'undetected_chromedriver')
    shutil.copy2(SYSTEM_CHROMEDRIVER_PATH, cache)
    os.chmod(cache, 0o755)
    # patch_exe() rewrites the cdc_ markers in place; this also makes uc treat the
    # binary as already-patched and skip its (x86-64-only) download step.
    uc.Patcher(executable_path=cache).patch_exe()
    return cache

def get_chrome_driver(driver_arguments):
    """Configure Chrome WebDriver"""
    logger.info('Initializing Chrome WebDriver for crawler...')
    chrome_options = uc.ChromeOptions() # pylint: disable=no-member
    if platform == "darwin":
        chrome_options.add_argument("--headless")
    if driver_arguments is not None:
        for driver_argument in driver_arguments:
            chrome_options.add_argument(driver_argument)
    chrome_version = get_chrome_version()
    chrome_options.add_argument("--headless=new")
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    driver_path = get_system_chromedriver_path()
    driver = uc.Chrome(
        version_main=chrome_version,
        options=chrome_options,
        driver_executable_path=driver_path,
    ) # pylint: disable=no-member

    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                         "AppleWebKit/537.36 (KHTML, like Gecko)"
                         "Chrome/120.0.0.0 Safari/537.36"
        },
    )

    driver.execute_cdp_cmd('Network.setBlockedURLs',
        {"urls": ["https://api.geetest.com/get.*"]})
    driver.execute_cdp_cmd('Network.enable', {})
    return driver
