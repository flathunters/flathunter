import os
import pytest
import unittest
from unittest.mock import patch

from flathunter.chrome_wrapper import (
    get_chrome_version,
    get_system_chromedriver_path,
    CHROME_BINARY_NAMES,
)
from flathunter.exceptions import ChromeNotFound


def calc_linux_binary_names():
	"""
	Creates a list containing empty lists for each name in CHROME_BINARY_NAMES that does not start with a forward slash.
	"""
	return [[] for name in CHROME_BINARY_NAMES if not name.startswith('/')]


"""
The list of mock commands get_command_output should return as an output.

The first returns should all be empty [] so the get_chrome_version function at flathunter/chrome_wrapper.py:31
thinks no linux chrome is installed and then checks for windows registry entry at flathunter/chrome_wrapper.py:46
Therefore prepending calc_linux_binary_names().
Append the same amount empty returns to the end so flathunter/chrome_wrapper.py:31 is forced to check for windows
again and self.assertEqual(get_chrome_version(), 116) works out
"""
CHROME_VERSION_RESULTS = calc_linux_binary_names() + [
	['Chromium 107.0.5304.87 built on Debian bookworm/sid, running on Debian bookworm/sid'],
	['Google Chrome 107.0.5304.110'],
	['Chromium 107.0.5304.87 built on Debian 11.5, running on Debian 11.5'],
] + calc_linux_binary_names()

"""
The first return should be empty ([]) so the system thinks no chrome installed at all and
self.assertEqual(get_chrome_version(), None) works out correctly
"""
REG_VERSION_RESULTS = [
	[],
	[
		'',
		r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon',
		'    version    REG_SZ    116.0.5845.141',
		'',
	]
]

def my_subprocess_mock(args, static={ 'chrome_calls': 0, 'reg_calls': 0 }):
    if 'chrom' in args[0]:
        static['chrome_calls'] += 1
        return CHROME_VERSION_RESULTS[static['chrome_calls'] - 1]
    if 'reg' in args[0]:
        static['reg_calls'] += 1
        return REG_VERSION_RESULTS[static['reg_calls'] - 1]

class ChromeWrapperTest(unittest.TestCase):

    @patch("flathunter.chrome_wrapper.get_command_output")
    def test_parse_chrome_version(self, subprocess_mock):
        subprocess_mock.side_effect = my_subprocess_mock
        with pytest.raises(ChromeNotFound):
            self.assertEqual(get_chrome_version(), None)
        self.assertEqual(get_chrome_version(), 107)
        self.assertEqual(get_chrome_version(), 107)
        self.assertEqual(get_chrome_version(), 107)
        self.assertEqual(get_chrome_version(), 116)


class SystemChromedriverPathTest(unittest.TestCase):

    @patch("flathunter.chrome_wrapper.machine", return_value="x86_64")
    @patch("flathunter.chrome_wrapper.os.path.exists", return_value=True)
    def test_returns_none_on_non_arm(self, _exists_mock, _machine_mock):
        """Non-ARM platforms let uc manage the driver, even if a system driver exists."""
        self.assertIsNone(get_system_chromedriver_path())

    @patch("flathunter.chrome_wrapper.machine", return_value="aarch64")
    @patch("flathunter.chrome_wrapper.os.path.exists", return_value=False)
    def test_returns_none_on_arm_without_system_driver(self, _exists_mock, _machine_mock):
        """On ARM without a system chromedriver there is nothing to fall back to."""
        self.assertIsNone(get_system_chromedriver_path())

    @patch("flathunter.chrome_wrapper.uc.Patcher")
    @patch("flathunter.chrome_wrapper.os.chmod")
    @patch("flathunter.chrome_wrapper.shutil.copy2")
    @patch("flathunter.chrome_wrapper.os.makedirs")
    @patch("flathunter.chrome_wrapper.os.path.exists", return_value=True)
    @patch("flathunter.chrome_wrapper.machine", return_value="armv7l")
    def test_copies_and_patches_on_arm(
        self, _machine_mock, _exists_mock, _makedirs_mock,
        copy_mock, _chmod_mock, patcher_mock
    ):
        """On ARM with a system driver, copy it to the cache, patch it, return the path."""
        result = get_system_chromedriver_path()
        expected = os.path.expanduser(
            '~/.local/share/undetected_chromedriver/undetected_chromedriver')
        self.assertEqual(result, expected)
        copy_mock.assert_called_once_with('/usr/bin/chromedriver', expected)
        patcher_mock.assert_called_once_with(executable_path=expected)
        patcher_mock.return_value.patch_exe.assert_called_once()
