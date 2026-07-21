# Flexi TV Kodi Addon

Watch live TV channels from the Flexi TV streaming service directly in Kodi.

## Requirements

- Kodi v19 Matrix or newer (Python 3)
- InputStream Adaptive addon (installed automatically)
- Active Flexi TV subscription with login credentials

## Installation

1. **Download** the addon zip from the [releases page](https://github.com/...) or build it from source.
2. **Open Kodi** → Add-ons → Install from zip file.
3. **Enable** `Settings → System → Add-ons → Unknown Sources` if prompted.
4. **Navigate** to the downloaded zip and select it.
5. After installation, go to **Add-ons → Flexi TV → Settings**.
6. Enter your Flexi TV **Username** and **Password**.
7. Open Flexi TV from your Add-ons menu.

## Usage

- **Root menu**: Shows TV station categories (e.g. Slovak, Czech, ...).
- **Category**: Opens a list of channels in that category.
- **Channel**: Starts live playback of the selected channel via HLS.

## How it works

1. The addon logs into tv.flexitv.sk using your stored credentials.
2. It scrapes the category tabs and channel listings from the main page.
3. When you select a channel, it fetches the channel page and searches the HTML/JS for the HLS stream URL (`.m3u8`).
4. Playback is handled by Kodi's InputStream Adaptive addon.

## Troubleshooting

- **"Could not load categories"**: Check your credentials in Settings. Verify the Flexi TV website is accessible from your network.
- **"Could not find HLS stream"**: The site may have changed its player. Enable debug logging in Kodi (`Settings → System → Logging → Enable debug logging`), then check `kodi.log` for `[plugin.video.flexitv]` entries. The log will show what was found on the page.

## Stream resolution

This addon tries multiple patterns to find the stream URL:

1. Direct `.m3u8` URLs in the HTML
2. JavaScript variables/objects containing `.m3u8`
3. Video.js / hls.js configuration objects
4. `data-*` HTML attributes
5. JSON embedded in scripts

If none match, check your `kodi.log` for details on what the channel page contains.

## Dependencies

All Python dependencies (Playwright, requests, etc.) are bundled inside the
addon at `resources/lib/python-deps/`. No `pip install` is required.

The addon's DWR helper script (`playwright_dwr.py`) is launched as a subprocess
using the system Python 3 (`/usr/bin/python3` on macOS). Chromium is downloaded
by Playwright on first run (`~/.cache/ms-playwright/`).

## Building from source

```bash
# 1. (Optional) Rebuild bundled deps for the current Python version
/usr/bin/python3 -m pip install --target /tmp/py39-deps playwright requests

# 2. Copy deps into the addon
rm -rf plugin.video.flexitv/resources/lib/python-deps
mkdir -p plugin.video.flexitv/resources/lib/python-deps
cp -R /tmp/py39-deps/* plugin.video.flexitv/resources/lib/python-deps/
rm -rf plugin.video.flexitv/resources/lib/python-deps/{bin,include}

# 3. Build the ZIP
cd plugin.video.flexitv/
zip -r ../plugin.video.flexitv-0.3.3.zip . \
  -x "*/__pycache__/*" -x "*/.DS_Store"
```

## License

MIT
