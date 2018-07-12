"""
Some useful networking related utility functions.
"""

import urllib.request


def lookupip():
    """
    Poll a third party service to see what our public facing IP is.
    """

    ourip = urllib.request.urlopen('https://icanhazip.com').read()
    ourip = ourip.decode("utf-8")
    ourip = ourip.strip("\n")

    return ourip
