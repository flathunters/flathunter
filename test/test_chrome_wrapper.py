import pytest
import unittest
from unittest.mock import patch

from flathunter.chrome_wrapper import get_chrome_version, CHROME_BINARY_NAMES
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
