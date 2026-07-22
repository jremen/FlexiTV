import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

def play_stream(handle, stream_info):
    url = stream_info.get("url", "")
    headers = stream_info.get("headers", {})
    manifest_type = stream_info.get("manifest_type") or ("hls" if ".m3u8" in url else "mpd")

    max_res = xbmcaddon.Addon().getSetting('max_resolution').strip()
    if max_res and max_res != 'Auto':
        xbmc.log(f"[play.py] Applying resolution cap: {max_res}", xbmc.LOGINFO)

    listitem = xbmcgui.ListItem(path=url)
    listitem.setMimeType("application/x-mpegURL" if manifest_type == "hls" else "application/dash+xml")
    listitem.setContentLookup(False)
    listitem.setProperty("inputstream", "inputstream.adaptive")
    listitem.setProperty("inputstream.adaptive.manifest_type", manifest_type)

    if max_res and max_res != 'Auto':
        listitem.setProperty("inputstream.adaptive.chooser_resolution_max", max_res)

    if headers:
        header_pairs = [f"{k}={v}" for k, v in headers.items()]
        listitem.setProperty(
            "inputstream.adaptive.stream_headers",
            "&".join(header_pairs)
        )

    listitem.setProperty("inputstream.adaptive.license_type", "")
    listitem.setProperty("inputstream.adaptive.license_key", "")

    xbmc.log(f"[play.py] Resolving stream: {url[:120]}...", xbmc.LOGINFO)
    xbmcplugin.setResolvedUrl(handle, True, listitem)
