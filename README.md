# Flexi TV — Kodi Addon

Watch live TV channels from the **Flexi TV** streaming service (`tv.flexitv.sk`) directly in Kodi.

## Features

- Browse TV channels grouped by category (Slovak, Czech, …)
- Play live HLS streams via Kodi's **InputStream Adaptive**
- 87 bundled channel logos
- DWR/Playwright-assisted login to handle the site's JavaScript-protected authentication

## Repository layout

```
.
├── build.sh                                          # Build script — creates the .zip addon package
├── logo_flexi.png                                    # Project / addon logo
├── plugin.video.flexitv/                             # Kodi addon directory
│   ├── addon.xml                                     # Addon metadata (id, version, dependencies)
│   ├── main.py                                       # Kodi plugin entry point
│   ├── README.md                                     # End-user install / usage instructions
│   └── resources/
│       ├── lib/
│       │   ├── flexitv.py                            # Core addon logic (login, scrape, stream resolve)
│       │   ├── logo_resolver.py                      # Channel logo fetching / caching
│       │   ├── play.py                               # Stream playback helper
│       │   ├── playwright_dwr.py                     # Headless Chromium DWR helper (subprocess)
│       │   ├── streams.py                            # HLS URL extraction
│       │   └── python-deps/                          # Bundled libraries (see "Building from source")
│       ├── media/
│       │   └── channels/                             # 87 PNG channel logos
│       └── settings.xml                              # Kodi addon settings (username, password, base_url)
├── plugin.video.flexitv-1.0.5.zip                    # Pre-built addon package (older)
├── plugin.video.flexitv-1.0.7.zip                    # Pre-built addon package (current)
└── scripts/
    ├── bump_version.sh                               # Bump addon version in addon.xml
    └── fetch_logos.py                                # Download channel logos from the Flexi TV site
```

## Quick start (end user)

1. Download `plugin.video.flexitv-1.0.7.zip` (or a newer release).
2. In Kodi: **Add-ons → Install from zip file**.
3. Install **InputStream Adaptive** if prompted.
4. Open **Flexi TV** from your Add-ons menu, enter your **Username** and **Password** in Settings, and browse channels.

See `plugin.video.flexitv/README.md` for detailed usage and troubleshooting.

## Building from source

```bash
./build.sh                                # Produces plugin.video.flexitv-<version>.zip
```

To also fetch the latest channel logos from the site, set `FLEXI_USER` and `FLEXI_PASS` environment variables before building:

```bash
export FLEXI_USER="your@email.com"
export FLEXI_PASS="your-password"
./build.sh
```

### Rebuilding bundled Python dependencies

The addon bundles its own copies of `playwright`, `requests`, `urllib3`, and other libs at `plugin.video.flexitv/resources/lib/python-deps/`. These are **not committed to git** by default. To rebuild them for your Python version:

```bash
/usr/bin/python3 -m pip install \
  --target /tmp/py39-deps \
  playwright requests

rm -rf plugin.video.flexitv/resources/lib/python-deps
mkdir -p plugin.video.flexitv/resources/lib/python-deps
cp -R /tmp/py39-deps/* plugin.video.flexitv/resources/lib/python-deps/
rm -rf plugin.video.flexitv/resources/lib/python-deps/{bin,include}
```

Then run `./build.sh` as normal.

## Development

- **Entry point** — `plugin.video.flexitv/main.py`
- **Login / DWR helper** — `plugin.video.flexitv/resources/lib/playwright_dwr.py` (run as a subprocess from the addon)
- **Bump version** — `./scripts/bump_version.sh` updates the version in `addon.xml`
- **Fetch logos** — `./scripts/fetch_logos.py` re-downloads channel artwork from the Flexi TV site
- **Bundled deps** — the `python-deps/` directory is gitignored; see the rebuild instructions above

## Requirements

- **Kodi v19 Matrix** or newer (Python 3)
- **InputStream Adaptive** addon
- **Active Flexi TV subscription** with login credentials (entered at runtime via Kodi settings — never stored in this repo)

## Security

Credentials are configured inside Kodi's secure settings dialog and are not stored in this repository. The login flow uses a headless Chromium instance (launched by Playwright) to execute the site's DWR/JavaScript authentication before session tokens are handed back to the addon.

## License

MIT

## Disclaimer

This is an **unofficial** addon. It is not affiliated with, endorsed by, or supported by Flexi TV. Users must have a valid Flexi TV subscription and agree to the site's terms of service.
