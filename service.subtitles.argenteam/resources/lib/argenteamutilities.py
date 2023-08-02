"""Provides utility functions
log (module, msg)
geturl(url)
"""
from __future__ import annotations

import urllib.error
import urllib.request as urllib2

import xbmc

#import re

def log(module:str, msg:str):
    """utility writes to Kodi debug log

    Args:
        module (str): module logging
        msg (str): what to log
    """
    xbmc.log((f"### [{module}] - {msg}"), level=xbmc.LOGDEBUG)


def geturl(url:str) -> tuple[str, str]:
    """argenteam query

    Args:
        url (str): url/query string

    Returns:
        tuple[str, str]: response from argenteam
    """
    log(__name__, f"Getting url: {url}")
    try:
        req = urllib2.Request(url, headers={"User-Agent": "Kodi-Addon"})
        response = urllib2.urlopen(req)
        content = response.read()
        #Fix non-unicode characters in movie titles
        #strip_unicode = re.compile("([^-_a-zA-Z0-9!@#%&=,/'\";:~`\$\^\*\(\)\+\[\]\.\{\}\|\?<>\\]+|[^\s]+)")
        #content = strip_unicode.sub('', content)
        return_url = response.geturl()
    except urllib.error.URLError:
        log(__name__, f"Failed to get url: {url}")
        content = None
        return_url = None
    return content, return_url
