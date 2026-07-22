import xbmcaddon

ADDON = xbmcaddon.Addon()

TELEKAC_TO_FLEXI = {
    8:   ("Markíza",        "Markiza_HD"),
    22:  ("JOJ",            "JOJ_HD"),
    10:  ("Jednotka",       None),
    90:  ("Doma",           "Doma_HD"),
    11:  ("Dvojka",         None),
    86:  ("JOJ Plus",       "JOJPlus_HD"),
    126: ("TV Dajto",       "DajTo_HD"),
    6:   ("HBO",            None),
    24:  ("TA3",            "TA3_HD"),
    251: ("STVR 24",        None),
    2:   ("ČT1",            "CT1_HD"),
    3:   ("ČT2",            "CT2_HD"),
    4:   ("Prima",          "Prima_SK_HD"),
    1:   ("Nova",           "Nova_International_HD"),
    9:   ("Eurosport 1",    "Eurosport_HD"),
    33:  ("Eurosport 2",    "Eurosport2_HD"),
    94:  ("National Geographic HD", None),
    217: ("JOJ 24",         "JOJ24_HD"),
    249: ("STVR Šport",     "RTVS_Sport_HD"),
    233: ("Nova Sport 6",   None),
    231: ("Nova Sport 5",   None),
    227: ("Markíza KLASIK", "Markiza_Klasik_HD"),
    209: ("Premier Sport 1", None),
    207: ("Markíza KRIMI",  "MarkizaKrimi_HD"),
    204: ("JOJ Šport",      "JOJSport_HD"),
    203: ("Premier Sport 2", None),
    202: ("Nova Sport 4",   None),
    201: ("Nova Sport 3",   None),
    163: ("Nova Sport 2",   None),
    157: ("Nova Sport 1",   None),
    137: ("JOJ Krimi",      None),
    147: ("ČT art",         "CTArt_HD"),
    148: ("ČT :D",          "CTD_HD"),
    91:  ("Disney Channel", None),
    62:  ("Cartoon Network + TCM", None),
    43:  ("Filmbox",        None),
    30:  ("AXN",            None),
    69:  ("AXN White",      None),
    68:  ("AXN Black",      None),
    38:  ("Cinemax",        None),
    49:  ("Cinemax 2",      None),
    40:  ("Film+",          None),
    71:  ("Nova Cinema",    None),
    120: ("Film Europe",    None),
    29:  ("HBO2",           None),
    63:  ("HBO3",           None),
    152: ("AMC",            None),
    161: ("ČS Film",        "CSFilm_HD"),
    156: ("Filmbox Extra HD", None),
    164: ("Filmbox Family", None),
    158: ("JOJ Cinema",     "JOJ_Cinema_HD"),
    165: ("Prima MAX",      None),
    45:  ("Sport1",         None),
    110: ("Sport2",         None),
    243: ("ČT4 Sport",      None),
    215: ("Canal+ Sport",   None),
    27:  ("Extreme Sports", None),
    127: ("Golf Channel",   None),
    72:  ("Nickelodeon",    None),
    225: ("Prima COOL SK",  "PrimaCoolSk_HD"),
    235: ("Prima LOVE SK",  "Prima_Love_SK_HD"),
    129: ("Nova Action",    None),
    111: ("Barrandov",      "TVBarrandovHD"),
    138: ("Nova Fun",       None),
    166: ("Nova International", None),
    167: ("Prima SK",       "Prima_SK_HD"),
    245: ("Prima KRIMI SK", "Prima_Krimi_SK_HD"),
    247: ("Nova Krimi",     None),
    253: ("Kanal 1",        None),
}


def default_chids():
    return [c for c, v in TELEKAC_TO_FLEXI.items() if v[1] is not None]


def get_selected_chids():
    raw = ADDON.getSetting("epg_stations").strip()
    if not raw:
        return default_chids()
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def set_selected_chids(chids):
    ADDON.setSetting("epg_stations", ",".join(str(c) for c in chids))


def flexi_name(chid):
    entry = TELEKAC_TO_FLEXI.get(chid)
    return entry[0] if entry else None


def flexi_suffix(chid):
    entry = TELEKAC_TO_FLEXI.get(chid)
    return entry[1] if entry else None


def can_play(chid):
    return flexi_suffix(chid) is not None


_SUFFIX_TO_CHID = {v[1]: c for c, v in TELEKAC_TO_FLEXI.items() if v[1]}

def chid_for_suffix(suffix):
    return _SUFFIX_TO_CHID.get(suffix)


def build_current_program_map(tk):
    chids = default_chids()
    schedule = tk.schedule("dnes", chids=chids, full_day=False)
    result = {}
    for entry in schedule:
        chid = entry["station"]["chid"]
        suffix = flexi_suffix(chid)
        if suffix and entry["programs"]:
            result[suffix] = entry["programs"][0]
    return result
