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
        for cat in categories:
            url = f'{sys.argv[0]}?action=channels&category={quote(cat["id"], safe="")}'
            li = xbmcgui.ListItem(cat['label'])
            if cat.get('logo'):
                li.setArt({'thumb': cat['logo']})
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        xbmcplugin.endOfDirectory(handle)

if __name__ == '__main__':
    handle = int(sys.argv[1])
    paramstring = sys.argv[2][1:] if sys.argv[2].startswith('?') else sys.argv[2]
    log(f'Route: {sys.argv[0]} | params: {paramstring}')
    router(paramstring, handle)
