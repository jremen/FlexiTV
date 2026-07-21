import os
import sys
import re
import json
import tempfile
import subprocess
import shutil

import requests
from urllib.parse import urljoin



class FlexiTV:
    BASE_URL = "https://tv.flexitv.sk"
    AUTH_BASE = "https://ucet.flexi.sk"

    def __init__(self, base_url=None, username=None, password=None, log=None):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.username = username
        self.password = password
        self.log_fn = log or (lambda msg: None)
        self._logged_in = False
        self._bundled_deps = self._find_bundled_deps()

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _find_bundled_deps(self):
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        deps = os.path.join(addon_dir, "resources", "lib", "python-deps")
        if os.path.isdir(deps):
            return deps
        return None

    def _find_python(self):
        candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            shutil.which("python3"),
        ]
        for cand in candidates:
            if cand and os.path.exists(cand):
                return cand
        for p in (sys.executable, "python3"):
            if p and os.path.exists(p):
                return p
        return "python3"

    def _stage_node_binary(self):
        node_src = os.path.join(
            self._bundled_deps, "playwright", "driver", "node"
        ) if self._bundled_deps else None
        if not node_src or not os.path.isfile(node_src):
            return None

        staging_dir = os.path.join(
            tempfile.gettempdir(), f"flexitv_node_{os.getuid()}"
        )
        os.makedirs(staging_dir, exist_ok=True)
        node_dst = os.path.join(staging_dir, "node")

        if not os.path.isfile(node_dst) or os.path.getsize(node_dst) != os.path.getsize(node_src):
            shutil.copy2(node_src, node_dst)
        os.chmod(node_dst, 0o755)
        try:
            subprocess.run(
                ["xattr", "-d", "com.apple.quarantine", node_dst],
                check=False, capture_output=True,
            )
        except Exception:
            pass
        return node_dst

    def _call_dwr(self, channel_id):
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        helper = os.path.join(addon_dir, "resources", "lib", "playwright_dwr.py")
        python_bin = self._find_python()
        self.log(f"DWR: python={python_bin}, deps={self._bundled_deps}")

        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("VIRTUAL_ENV", None)
        env.pop("PIP_REQUIRE_VIRTUALENV", None)
        env.pop("PYTHONPATH", None)
        for k in list(env):
            if k.startswith("DYLD_"):
                env.pop(k, None)
        if self._bundled_deps:
            env["PYTHONPATH"] = self._bundled_deps
        env["PYTHONUNBUFFERED"] = "1"

        staged_node = self._stage_node_binary()
        if staged_node:
            env["PLAYWRIGHT_NODEJS_PATH"] = staged_node

        debug_log = os.path.join(
            os.path.expanduser("~"), "Library", "Logs", "flexitv_dwr_debug.log"
        )

        try:
            proc = subprocess.run(
                [python_bin, helper,
                 "--user", self.username or "",
                 "--pass", self.password or "",
                 "--channel-id", str(channel_id)],
                capture_output=True, text=True, timeout=120,
                env=env,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip() or ""
                with open(debug_log, "w") as f:
                    f.write(f"RC: {proc.returncode}\n")
                    f.write(f"STDOUT:\n{proc.stdout}\n")
                    f.write(f"STDERR:\n{proc.stderr}\n")
                if "No module named 'encodings'" in err:
                    self.log("DWR: encodings failure — PYTHONHOME inherited from Kodi interferes")
                self.log(f"DWR helper error (rc={proc.returncode}): {err[:2000]}")
                self.log(f"DWR: full debug log written to {debug_log}")
                return None
            result = json.loads(proc.stdout.strip())
            return result
        except FileNotFoundError:
            self.log(f"DWR: python not found: {python_bin}")
            return None
        except subprocess.TimeoutExpired:
            self.log(f"DWR helper timed out after 120s")
            return None
        except Exception as e:
            self.log(f"DWR helper exception: {e}")
            return None

    def log(self, msg):
        self.log_fn(f"[FlexiTV] {msg}")

    def _make_abs(self, url, base=None):
        if not url:
            return url
        if url.startswith("http"):
            return url
        base = base or self.AUTH_BASE
        return base + url if url.startswith("/") else base + "/" + url

    def login(self):
        self.log("Starting OIDC login flow")

        resp = self._session.get(f"{self.BASE_URL}/pctv/")
        html = resp.text
        self.log(f"GET /pctv/: {resp.status_code} {len(html)} bytes")

        state = self._extract_hauth_field(html, "state")
        client_id = self._extract_hauth_field(html, "client_id")
        redirect_uri = self._extract_hauth_field(html, "redirect_uri")
        scope = self._extract_hauth_field(html, "scope")
        response_type = self._extract_hauth_field(html, "response_type")

        if not all([state, client_id, redirect_uri, scope, response_type]):
            self.log("No hauth form fields — already logged in?")
            if "Odhlásiť" in html:
                self._logged_in = True
                return True
            return False

        resp = self._session.post(
            f"{self.BASE_URL}/hauth/auth/realms/hibox-realm/protocol/openid-connect/auth",
            data={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": response_type,
                "scope": scope,
                "state": state,
            },
            allow_redirects=False,
        )
        url = resp.headers.get("Location", "")
        if not url:
            return False

        resp = self._session.get(url, allow_redirects=False)
        url = resp.headers.get("Location", "")
        if not url:
            return False

        resp = self._session.get(self._make_abs(url), allow_redirects=False)
        url = resp.headers.get("Location", "")
        if not url:
            return False

        resp = self._session.get(self._make_abs(url), allow_redirects=True)

        resp = self._session.post(
            f"{self.AUTH_BASE}/oauth2/account/login",
            data={"username": self.username, "current_password": self.password},
            allow_redirects=False,
        )
        url = resp.headers.get("Location", "")
        if not url:
            return False

        step = 0
        while url and step < 10:
            base = self.BASE_URL if "tv.flexitv.sk" in url else self.AUTH_BASE
            resp = self._session.get(self._make_abs(url, base), allow_redirects=False)
            url = resp.headers.get("Location", "") or ""
            step += 1
            if resp.status_code == 200 and not url:
                break
            if "/pctv/Login" in resp.url.rstrip("/") and resp.status_code == 200:
                break

        if "Odhlásiť" in resp.text:
            self._logged_in = True
            self.log("Login successful")
            return True

        if "Prihlásiť" not in resp.text:
            self._logged_in = True
            self.log("Login successful")
            return True

        self.log("Login failed")
        return False

    def _extract_hauth_field(self, html, field_name):
        m = re.search(rf'name="{re.escape(field_name)}"\s+value="([^"]*)"', html)
        return m.group(1) if m else None

    def _fetch_page(self):
        return self._session.get(f"{self.BASE_URL}/pctv/").text

    def _extract_json_array(self, html, varname):
        idx = html.find(f"{varname} = [")
        if idx < 0:
            return None

        second = html.find(f"{varname} = [", idx + 10)
        if second >= 0:
            idx = second

        start_bracket = html.find("[", idx)
        if start_bracket < 0:
            return None

        if varname == "allTVChannels":
            end_marker = "categories = ["
        else:
            end_marker = "try {"

        end_search = html.find(end_marker, start_bracket)
        if end_search < 0:
            return None

        last_bracket = html.rfind("]", start_bracket, end_search)
        if last_bracket < 0:
            return None

        raw = html[start_bracket:last_bracket + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def get_categories(self):
        self.log("Reading categories from page data")
        try:
            html = self._fetch_page()
            data = self._extract_json_array(html, "categories")
            if data:
                cats = [{"label": c.get("name", ""), "id": str(c.get("id", ""))} for c in data]
                self.log(f"Found {len(cats)} categories")
                return cats

            data = self._extract_json_array(html, "allTVChannels")
            if data:
                seen = {}
                for item in data:
                    ch = item.get("channel", item)
                    for cat in ch.get("categories", []):
                        cid = str(cat.get("id", ""))
                        name = cat.get("name", "") or cat.get("label", "")
                        if cid and cid not in seen:
                            seen[cid] = {"label": name, "id": cid}
                cats = list(seen.values())
                self.log(f"Found {len(cats)} categories from channels")
                return cats

            self.log("No categories found")
            return []
        except Exception as e:
            self.log(f"Error getting categories: {e}")
            return []

    def get_channels(self, category_id=None):
        self.log(f"Reading channels for category: {category_id or 'all'}")
        try:
            html = self._fetch_page()
            data = self._extract_json_array(html, "allTVChannels")
            if not data:
                self.log("No channel data found")
                return []

            channels = []
            for item in data:
                ch = item.get("channel", item) if isinstance(item, dict) else {}
                name = ch.get("name", "")
                sid = str(ch.get("id", ""))
                logo = ch.get("logo", "") or ch.get("logoLarge", "")
                suffix = ch.get("internalNameSuffix", "")
                if suffix:
                    from .logo_resolver import resolve as resolve_logo
                    local_logo = resolve_logo(suffix)
                    if local_logo:
                        logo = local_logo
                if logo and not logo.startswith(("http", "special://", "/")):
                    logo = urljoin(self.BASE_URL, "/" + logo.lstrip("/"))

                ch_cats = [str(c.get("id", "")) for c in ch.get("categories", [])]
                if category_id and category_id not in ch_cats:
                    continue

                streams = item.get("streams", [])
                uri = ""
                for s in streams:
                    u = s.get("uri", "")
                    if u.startswith("/") and ("index.mpd" in u or "rewind" in u):
                        uri = u
                        break
                if not uri:
                    for s in streams:
                        u = s.get("uri", "")
                        if u.startswith("/"):
                            uri = u
                            break
                if not uri:
                    uri = item.get("uri", "")

                channels.append({
                    "label": name,
                    "id": sid,
                    "number": ch.get("number", 0),
                    "suffix": suffix,
                    "uri": uri,
                    "logo": logo or None,
                    "categories": ch_cats,
                })

            self.log(f"Found {len(channels)} channels")
            return channels
        except Exception as e:
            self.log(f"Error getting channels: {e}")
            return []

    def get_stream_url(self, channel_data):
        if isinstance(channel_data, str):
            channel_data = {"uri": channel_data, "suffix": "", "id": ""}

        channel_id = channel_data.get("id", "")
        label = channel_data.get("label", "")

        if channel_id and channel_id.isdigit():
            self.log(f"Resolving via DWR for channel {channel_id} ({label})")
            result = self._call_dwr(int(channel_id))
            if result and "playbackUrl" in result and result["playbackUrl"]:
                stream_url = result["playbackUrl"]
                container = result.get("container", "HLS")
                self.log(f"DWR resolved: {stream_url[:80]}... ({container})")
                return {
                    "url": stream_url,
                    "license_url": None,
                    "headers": {},
                    "manifest_type": "hls" if container == "HLS" else "mpd",
                }

        uri = channel_data.get("uri", "")
        suffix = channel_data.get("suffix", "")

        if not uri or uri.startswith("igmp://") or uri.startswith("flussonic://"):
            if suffix:
                stream_url = f"{self.BASE_URL}/{suffix}/index.m3u8"
            elif channel_id:
                stream_url = f"{self.BASE_URL}/channel/{channel_id}/index.m3u8"
            else:
                stream_url = f"{self.BASE_URL}/live/index.m3u8"
        elif uri.startswith("/"):
            stream_url = f"{self.BASE_URL}{uri}"
        else:
            stream_url = uri

        self.log(f"Fallback stream URL: {stream_url}")
        return {
            "url": stream_url,
            "license_url": None,
            "headers": {},
        }
