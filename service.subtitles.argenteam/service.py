# See GPLv3 license.txt for full license
"""Searches for subtitles at argenteam.net based on movie or tv show name
with optional year.

Usage: Enable via Kodi player subtitle options.  When playing media, use
subtitles dialog in full screen video to start search and select subtitle
from results.
"""

import json
import os
import re
import shutil
import sys
import unicodedata
import urllib
import urllib.parse
import urllib.request as urllib2

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.argenteamutilities import geturl, log

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString

__cwd__ = xbmcvfs.translatePath(
    __addon__.getAddonInfo('path'))
__profile__ = xbmcvfs.translatePath(
    __addon__.getAddonInfo('profile'))
__resource__ = xbmcvfs.translatePath(
    os.path.join(__cwd__, 'resources', 'lib'))
__temp__ = xbmcvfs.translatePath(
    os.path.join(__profile__, 'temp'))
__temp__ = __temp__ + os.path.sep

sys.path.append(__resource__)
API_SEARCH_URL = "http://argenteam.net/api/v1/search"
API_TVSHOW_API = "http://argenteam.net/api/v1/tvshow"
API_EPISODE_URL = "http://argenteam.net/api/v1/episode"
API_MOVIE_API = "http://argenteam.net/api/v1/movie"
MAIN_URL = "http://www.argenteam.net/"
EXTS = [".srt", ".sub", ".txt", ".smi", ".ssa", ".ass"]


def append_subtitle(items:list):
    """Creates Kodi listitems from sub urls

    Args:
        items (list): list of subtitle dicts
    """

    items.sort(key=lambda x: x['rating'], reverse=True)
    index = 0
    for item in items:
        index += 1
        sublistitem = xbmcgui.ListItem(
            label=item['lang'],
            label2=item['filename'])

        #listitem.setProperty("sync",  'true' if item["sync"] else 'false')
        sublistitem.setArt({'thumb': item['image'], 'icon': item['rating']})
        sublistitem.setProperty(
            "hearing_imp",
            'true' if item["hearing_imp"] else 'false')

        ## below arguments are optional, it can be used to pass any info needed
        ## in download function
        ## anything after "action=download&" will be sent to addon
        ## once user clicks listed subtitle to downlaod
        url = (f"plugin://{__scriptid__}/?action=download"
               f"&actionsortorder={str(index).zfill(2)}"
               f"&link={item['link']}"
               f"&filename={item['filename']}"
               f"&id={item['id']}")
        #log('service.append_subtitle', f"listitem url: {url}")

        ## add it to list, this can be done as many times as needed
        ## for all subtitles found
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]),
            url=url,
            listitem=sublistitem,
            isFolder=False
        )


def search_movie(movie_id:int) -> list:
    url = API_MOVIE_API + "?id=" + str(movie_id)
    content, response_url = geturl(url)
    return search_common(content)


def search_tvshow(result):
    #log(__name__, "Search tvshow = %s" % tvshow)

    subs = []

    if result['type'] == "tvshow":
        url = API_TVSHOW_API + "?id=" + str(result['id'])
        content, response_url = geturl(url)
        content = content.replace("null", '""')
        result_json = json.loads(content)

        for season in result_json['seasons']:
            for episode in season['episodes']:
                subs.extend(search_episode(episode['id']))

    elif result['type'] == "episode":
        subs.extend(search_episode(result['id']))

    return subs


def search_episode(episode_id) -> list:
    url = API_EPISODE_URL + "?id=" + str(episode_id)
    content, response_url = geturl(url)

    return search_common(content)


def search_common(content) -> list:
    if content is not None:
        log(__name__, "Resultados encontrados...")
        #object_subtitles = find_subtitles(content)
        items = []
        result = json.loads(content)

        if "releases" in result:
            for release in result['releases']:
                for subtitle in release['subtitles']:
                    item = {}
                    item['lang'] = "Spanish"
                    item['filename'] = urllib.parse.unquote_plus(
                        subtitle['uri'].split("/")[-1]
                    )
                    item['rating'] = str(subtitle['count'])
                    item['image'] = 'es'
                    item['id'] = subtitle['uri'].split("/")[-2]
                    item['link'] = subtitle['uri']

                    #Check for Closed Caption
                    if "-CC" in item['filename']:
                        item['hearing_imp'] = True
                    else:
                        item['hearing_imp'] = False

                    items.append(item)

        return items


def search_filename(filename:str, language:list):
    """gets title and year from filename

    Args:
        filename (str): A filename to parse
        languages (list): unused
    """
    title, year = xbmc.getCleanMovieTitle(filename)
    log(__name__, f'clean title: \"{title}\" ({year})')
    try:
        yearval = int(year)
    except ValueError:
        yearval = 0
    if title and yearval > 1900:
        search_string = title + "+" + year
        search_argenteam_api(search_string)
    else:
        match = re.search(
            r'\WS(?P<season>\d\d)E(?P<episode>\d\d)',
            title,
            flags=re.IGNORECASE
        )
        if match is not None:
            tvshow = str.strip(title[:match.start('season')-1])
            season = str.lstrip(match.group('season'), '0')
            episode = str.lstrip(match.group('episode'), '0')
            search_string = "%s S%#02dE%#02d" % (
                tvshow,
                int(season),
                int(episode)
            )
            search_argenteam_api(search_string)
        else:
            search_argenteam_api(filename)


def search_argenteam_api(search_string:str):
    """query argenteam for subs urls and create listitems for subs

    Args:
        search_string (str): argenteam query string
    
    """
    url = f"{API_SEARCH_URL}?q={urllib.parse.quote_plus(search_string)}"
    content, response_url = geturl(url)
    response:dict = json.loads(content)
    arg_subs = []

    if response['total'] > 0:
        for result in response['results']:
            if result['type'] == "tvshow" or result['type'] == "episode":
                arg_subs.extend(search_tvshow(result))
            elif result['type'] == "movie":
                arg_subs.extend(search_movie(result['id']))

    append_subtitle(arg_subs)


def search(sitem:dict):
    """constructs and runs argenteam query to create Kodi listitems of subs

    Args:
        sitem (dict): the tv show or movie to search for
    """
    filename = os.path.splitext(os.path.basename(sitem['file_original_path']))[0]
    log(__name__, f"Search_argenteam='{sitem}', "
        f"filename='{filename}', "
        f"addon_version={__version__}"
    )
    if sitem['mansearch']:
        search_string = urllib.parse.unquote(sitem['mansearchstr'])
        search_argenteam_api(search_string)
    elif sitem['tvshow']:
        search_string = "%s S%#02dE%#02d" % (
            sitem['tvshow'].replace("(US)", ""),
            int(sitem['season']),
            int(sitem['episode'])
        )
        search_argenteam_api(search_string)
    elif sitem['title'] and sitem['year']:
        search_string = sitem['title'] + " " + sitem['year']
        search_argenteam_api(search_string)
    else:
        search_filename(filename, sitem['3let_language'])


def download(id:str, url:str, filename:str, search_string="") -> list:
    """download subs and write to files

    Args:
        id (str): argenteam subid
        url (str): argenteam sub url
        filename (str): local media filename
        search_string (str, optional): _description_. Defaults to "".

    Returns:
        list: sub files
    """
    subtitle_list = []

    ## Cleanup temp dir, we recomend you download/unzip your subs
    ## in temp folder and pass that to XBMC to copy and activate
    if xbmcvfs.exists(__temp__):
        shutil.rmtree(__temp__)
    xbmcvfs.mkdirs(__temp__)
    #log('service.download', f'created temp {__temp__}')
    filename = os.path.join(__temp__, filename + ".zip")
    #log('sevice.download', f'sub filename {filename}')
    req = urllib2.Request(url, headers={"User-Agent": "Kodi-Addon"})
    with urllib2.urlopen(req) as response:
        raw_sub = response.read()
    with open(filename, "wb") as subfile:
        subfile.write(raw_sub)
    log('service.download', f'wrote file {filename}')

    xbmc.sleep(500)
    #xbmc.executebuiltin(
    #   ('XBMC.Extract("%s","%s")' % (filename, __temp__,)),
    #    True)
    zip_files = xbmcvfs.listdir(f'zip://{urllib.parse.quote_plus(filename)}')[1]
    #log('service.download', f'zip files {zip_files} zip dirs {zip_dirs}')
    for file in zip_files:
        xbmcvfs.copy(f'zip://{urllib.parse.quote_plus(filename)}/{file}', f'{__temp__}/{file}')
        file = os.path.join(__temp__, file)
        #log('service.download', f'file is {file}')
        if os.path.splitext(file)[1] in EXTS:
            if search_string and str.find(
                str.lower(file),
                str.lower(search_string)
            ) == -1:
                continue
            log(__name__, f"=== returning subtitle file {file}")
            subtitle_list.append(file)

    return subtitle_list


def normalize_string(unistr:str) -> str:
    """performs NFKD on unicode strings

    Args:
        unistr (str): a string to normalize

    Returns:
        str: ormalized string
    """
    return unicodedata.normalize(
        'NFKD', unistr)


def get_params() -> dict:
    """gets a dict of argv parameters passed to addon

    Returns:
        dict: the parameters split with & character
    """
    param = {}
    paramstring = sys.argv[2]
    #log('service.get_params', f'type {type(paramstring)} len {len(paramstring)} {paramstring}')
    if len(paramstring) >= 2:
        cleanedparams = paramstring.replace('?', '')
        if paramstring[len(paramstring) - 1] == '/':
            paramstring = paramstring[0:len(paramstring) - 2]
        pairsofparams = cleanedparams.split('&')
        #log('service.get_params', f'pairsofparams {pairsofparams}')
        param = {}
        for pitem in pairsofparams:
            splitparams = pitem.split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    log('service.get_params', f'param dict {param}')
    return param


params = get_params()

#search argenteam for subs and provide list of subs for Kodi select dialog
if params['action'] == 'search' or params['action'] == 'manualsearch':
    item = {}
    item['temp'] = False
    item['rar'] = False
    item['mansearch'] = False
    item['year'] = xbmc.getInfoLabel("VideoPlayer.Year")
    item['season'] = str(xbmc.getInfoLabel("VideoPlayer.Season"))
    item['episode'] = str(xbmc.getInfoLabel("VideoPlayer.Episode"))
    item['tvshow'] = normalize_string(
        xbmc.getInfoLabel("VideoPlayer.TVshowtitle")
    )
    item['title'] = normalize_string(
        xbmc.getInfoLabel("VideoPlayer.OriginalTitle")
    )
    item['file_original_path'] = urllib.parse.unquote(
        xbmc.Player().getPlayingFile()
    )
    #log('service', f'file_original_path {item["file_original_path"]}')
    item['3let_language'] = []

    if 'searchstring' in params:
        item['mansearch'] = True
        item['mansearchstr'] = params['searchstring']
        #log('service', f"searchstring {params['searchstring']}")

    for lang in urllib.parse.unquote(params['languages']).split(","):
        item['3let_language'].append(
            xbmc.convertLanguage(lang, xbmc.ISO_639_2)
        )

    if item['title'] == "":
        # no original title, get just Title
        item['title'] = normalize_string(xbmc.getInfoLabel("VideoPlayer.Title"))

    # Check if season is "Special"
    if item['episode'].lower().find("s") > -1:
        item['season'] = "0"
        item['episode'] = item['episode'][-1:]

    if item['file_original_path'].find("http") > -1:
        item['temp'] = True

    elif item['file_original_path'].find("rar://") > -1:
        item['rar'] = True
        item['file_original_path'] = os.path.dirname(
            item['file_original_path'][6:]
        )

    elif item['file_original_path'].find("stack://") > -1:
        stackPath = item['file_original_path'].split(" , ")
        item['file_original_path'] = stackPath[0][8:]

    search(item)

#download sub file from user select dialog action
elif params['action'] == 'download':
    log('service', 'download subs')
    ## we pickup all our arguments sent from def Search()
    if 'find' in params:
        subs = download(params["link"], params["find"], "")
    else:
        subs = download(params["id"],params["link"], params["filename"])
    ## we can return more than one subtitle for multi CD versions,
    ## for now we are still working out how to handle that
    ## in XBMC core
    for sub in subs:
        listitem = xbmcgui.ListItem(label=sub)
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]),
            url=sub,
            listitem=listitem,
            isFolder=False
        )

xbmcplugin.endOfDirectory(int(sys.argv[1]))  # send end of directory to XBMC
