import json
import os

_addon_id = None
_manifest = None


def _get_addon_id():
    global _addon_id
    if _addon_id is None:
        import xbmcaddon
        _addon_id = xbmcaddon.Addon().getAddonInfo("id")
    return _addon_id


def _load():
    global _manifest
    if _manifest is not None:
        return
    addon_id = _get_addon_id()
    p = os.path.join(
        os.path.expanduser("~"),
        "Library", "Application Support", "Kodi", "addons",
        addon_id, "resources", "media", "channels", "_manifest.json",
    )
    if os.path.isfile(p):
        with open(p) as f:
            _manifest = json.load(f)
    else:
        _manifest = {}


def resolve(suffix):
    _load()
    fn = _manifest.get(suffix)
    if fn:
        return (
            "special://home/addons/"
            f"{_get_addon_id()}/resources/media/channels/{fn}"
        )
    return None
