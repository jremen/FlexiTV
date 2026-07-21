import sys
import json
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import parse_qs, quote

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}] {msg}', level)

def get_settings():
    username = ADDON.getSetting('username').strip()
    password = ADDON.getSetting('password').strip()
    base_url = ADDON.getSetting('base_url').strip() or 'https://tv.flexitv.sk'
    return username, password, base_url

def open_settings_and_retry():
    log('Credentials not configured — opening settings')
    ADDON.openSettings()
    username = ADDON.getSetting('username').strip()
    password = ADDON.getSetting('password').strip()
    if not username or not password:
        dialog = xbmcgui.Dialog()
        dialog.ok(ADDON_NAME, 'Flexi TV credentials are required.', 'Please enter your username and password in Settings.')
        return None, None
    return username, password

def router(paramstring, handle):
    params = parse_qs(paramstring)
    action = params.get('action', [None])[0]

    if action == 'quick_settings':
        labels = ['Auto (no cap)', '1080p', '720p', '480p', '360p']
        values = ['Auto', '1080p', '720p', '480p', '360p']
        current = ADDON.getSetting('max_resolution').strip() or 'Auto'
        preselect = values.index(current) if current in values else -1
        sel = xbmcgui.Dialog().select('Maximum resolution', labels, presel=preselect)
        if sel >= 0:
            ADDON.setSetting('max_resolution', values[sel])
        xbmc.executebuiltin('Container.Refresh')
        return

    if action == 'epg':
        _epg_landing(handle)
        return

    if action == 'epg_timeline':
        day = params.get('day', ['dnes'])[0]
        station_filter = params.get('station', [None])[0]
        _epg_timeline(handle, day, station_filter)
        return

    if action == 'epg_stations':
        _epg_stations_picker(handle)
        return

    if action == 'epg_notavail':
        enc = params.get('data', [None])[0]
        if enc:
            detail = json.loads(enc)
            dialog = xbmcgui.Dialog()
            dialog.ok('TV Schedule', f'"{detail["title"]}" is not available on Flexi TV.')
        return

    username, password, base_url = get_settings()
    if not username or not password:
        username, password = open_settings_and_retry()
        if not username:
            return

    from resources.lib.flexitv import FlexiTV

    tv = FlexiTV(
        base_url=base_url,
        username=username,
        password=password,
        log=lambda msg: log(msg)
    )

    if action == 'play':
        enc = params.get('data', [None])[0]
        if not enc:
            log('No channel data provided', xbmc.LOGERROR)
            return
        try:
            channel_data = json.loads(enc)
        except json.JSONDecodeError:
            log('Invalid channel data', xbmc.LOGERROR)
            return
        log(f'Resolving stream for: {channel_data.get("label", "")}')
        stream_info = tv.get_stream_url(channel_data)
        from resources.lib.play import play_stream
        play_stream(handle, stream_info)

    elif action == 'channels':
        category_id = params.get('category', [''])[0]
        log(f'Loading channels for category: {category_id}')
        channels = tv.get_channels(category_id)
        for ch in channels:
            data_json = json.dumps({"uri": ch["uri"], "suffix": ch["suffix"], "id": ch["id"], "label": ch["label"]})
            url = f'{sys.argv[0]}?action=play&data={quote(data_json, safe="")}'
            li = xbmcgui.ListItem(ch['label'])
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': ch['label']})
            if ch.get('logo'):
                li.setArt({'thumb': ch['logo'], 'icon': ch['logo']})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(handle)

    else:
        log('Loading root categories')
        try:
            categories = tv.get_categories()
        except Exception as e:
            log(f'Failed to load categories: {e}', xbmc.LOGERROR)
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_NAME, 'Could not load categories.', str(e)[:200])
            return

        epg_url = f'{sys.argv[0]}?action=epg'
        epg_li = xbmcgui.ListItem('TV Schedule')
        epg_li.setArt({'icon': 'DefaultAddonTvInfo.png'})
        xbmcplugin.addDirectoryItem(handle, epg_url, epg_li, isFolder=True)

        if ADDON.getSetting('quick_settings_visible').strip() == 'true':
            qs_url = f'{sys.argv[0]}?action=quick_settings'
            qs_label = 'Quick settings'
            qs_li = xbmcgui.ListItem(qs_label)
            qs_li.setArt({'icon': 'DefaultAddonSettings.png'})
            xbmcplugin.addDirectoryItem(handle, qs_url, qs_li, isFolder=False)

        for cat in categories:
            url = f'{sys.argv[0]}?action=channels&category={quote(cat["id"], safe="")}'
            li = xbmcgui.ListItem(cat['label'])
            if cat.get('logo'):
                li.setArt({'thumb': cat['logo']})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        xbmcplugin.endOfDirectory(handle)


def _epg_landing(handle):
    from resources.lib.telkac import Telkac
    from resources.lib import epg
    tk = Telkac(log=lambda msg: log(msg))
    all_stations = tk.stations()
    selected = set(epg.get_selected_chids())
    arg = sys.argv[0]

    day_url = f'{arg}?action=epg_timeline&day=dnes'
    li = xbmcgui.ListItem('Show today\'s schedule')
    xbmcplugin.addDirectoryItem(handle, day_url, li, isFolder=True)

    stations_url = f'{arg}?action=epg_stations'
    li = xbmcgui.ListItem('Choose stations')
    li.setArt({'icon': 'DefaultAddonSettings.png'})
    xbmcplugin.addDirectoryItem(handle, stations_url, li, isFolder=False)

    for st in all_stations:
        if st["chid"] not in selected:
            continue
        station_url = f'{arg}?action=epg_timeline&day=dnes&station={st["chid"]}'
        st_li = xbmcgui.ListItem(st["name"])
        st_li.setArt({'thumb': st["logo"]})
        xbmcplugin.addDirectoryItem(handle, station_url, st_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def _epg_timeline(handle, day, station_filter=None):
    from resources.lib.telkac import Telkac
    from resources.lib import epg
    tk = Telkac(log=lambda msg: log(msg))
    chids = epg.get_selected_chids()
    schedule = tk.schedule(day, chids)
    if station_filter:
        schedule = [e for e in schedule if e["station"]["chid"] == station_filter]
    arg = sys.argv[0]

    for entry in schedule:
        st = entry["station"]
        for prog in entry["programs"]:
            label = f'[{prog["time"]}] {prog["title"]}  ({st["name"]})'
            chid = st["chid"]
            if epg.can_play(chid):
                data = json.dumps({
                    "uri": "",
                    "suffix": epg.flexi_suffix(chid),
                    "id": "",
                    "label": st["name"],
                })
                url = f'{arg}?action=play&data={quote(data, safe="")}'
                li = xbmcgui.ListItem(label)
                li.setProperty('IsPlayable', 'true')
            else:
                detail = json.dumps({"chid": chid, "href": prog["href"], "title": prog["title"]})
                url = f'{arg}?action=epg_notavail&data={quote(detail, safe="")}'
                li = xbmcgui.ListItem(f'[COLOR=grey]{label}[/COLOR]')
            li.setInfo('video', {
                'title': prog["title"],
                'plot': prog.get("desc", ""),
                'duration': prog.get("duration", 0),
            })
            art = {}
            if prog.get("image"):
                art['thumb'] = prog["image"]
            elif st.get("logo"):
                art['thumb'] = st["logo"]
            if art:
                li.setArt(art)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(handle)


def _epg_stations_picker(handle):
    from resources.lib.telkac import Telkac
    from resources.lib import epg
    tk = Telkac(log=lambda msg: log(msg))
    all_stations = tk.stations()
    current = set(epg.get_selected_chids())
    names = [s["name"] for s in all_stations]
    preselect = [i for i, s in enumerate(all_stations) if s["chid"] in current]
    sel = xbmcgui.Dialog().multiselect('Choose TV stations', names, preselect=preselect)
    if sel is None:
        xbmcplugin.endOfDirectory(handle)
        return
    chosen = [all_stations[i]["chid"] for i in sel]
    epg.set_selected_chids(chosen)
    xbmc.executebuiltin('Container.Refresh')


if __name__ == '__main__':
    handle = int(sys.argv[1])
    paramstring = sys.argv[2][1:] if sys.argv[2].startswith('?') else sys.argv[2]
    log(f'Route: {sys.argv[0]} | params: {paramstring}')
    router(paramstring, handle)
