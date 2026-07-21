import re
import requests


BASE = "https://telkac.zoznam.sk"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class Telkac:
    def __init__(self, log=None):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self.log_fn = log or (lambda msg: None)

    def log(self, msg):
        self.log_fn(f"[Telkac] {msg}")

    def _get(self, path):
        url = f"{BASE}{path}" if path.startswith("/") else f"{BASE}/{path}"
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def stations(self):
        html = self._get("/nastav-tv-program")
        results = []
        for m in re.finditer(
            r'<input[^>]*class="chid"[^>]*'
            r'chid="(\d+)"[^>]*'
            r'name="([^"]*)"[^>]*'
            r'(?:checked="[^"]*")?[^>]*'
            r'(?:img="([^"]*)")?',
            html,
        ):
            chid = int(m.group(1))
            name = self._unescape(m.group(2))
            logo = m.group(3) or ""
            results.append({"chid": chid, "name": name, "logo": logo})
        return results

    def day_options(self):
        html = self._get("/")
        options = []
        for m in re.finditer(
            r'<option\s+value="(/tv-program/[^"]+)"\s*'
            r'(?:selected="[^"]*")?\s*>([^<]+)</option>',
            html,
        ):
            slug = m.group(1).replace("/tv-program/", "")
            label = m.group(2).strip()
            options.append({"slug": slug, "label": label})
        return options

    def schedule(self, day_slug, chids=None):
        path = f"/tv-program/{day_slug}"
        html = self._get(path)
        stations = self._parse_station_list(html)
        if chids:
            chid_set = set(chids)
            stations = [s for s in stations if s["chid"] in chid_set]
        rows = self._parse_timeline_rows(html)
        result = []
        for idx, station in enumerate(stations):
            programs = rows[idx] if idx < len(rows) else []
            result.append({"station": station, "programs": programs})
        return result

    def _parse_station_list(self, html):
        block = re.search(
            r'<aside[^>]*id="timeline-channels"[^>]*>(.*?)</aside>',
            html, re.DOTALL,
        )
        if not block:
            return []
        stations = []
        for m in re.finditer(
            r'<a\s+href="/tv-program-stanice/(\d+)/([^"]+)"[^>]*>'
            r'\s*<img[^>]*src="([^"]*)"[^>]*>'
            r'\s*<span\s+class="station-name">([^<]+)</span>',
            block.group(1), re.DOTALL,
        ):
            stations.append({
                "chid": int(m.group(1)),
                "slug": m.group(2),
                "logo": m.group(3),
                "name": self._unescape(m.group(4).strip()),
            })
        return stations

    def _parse_timeline_rows(self, html):
        rows = []
        for row_match in re.finditer(
            r'<ul\s+class="timeline-row">(.*?)</ul>',
            html, re.DOTALL,
        ):
            row_html = row_match.group(1)
            capsules = {}
            for cap in re.finditer(
                r'<div\s+class="broadcast-capsule"[^>]*\s+bid="(\d+)"[^>]*>(.*?)</div>',
                row_html, re.DOTALL,
            ):
                bid = int(cap.group(1))
                cap_html = cap.group(2)
                desc = ""
                dm = re.search(
                    r'<div\s+class="tooltip-program-desc">(.*?)</div>',
                    cap_html, re.DOTALL,
                )
                if dm:
                    desc = dm.group(1).strip()
                img = ""
                im = re.search(r'<img\s+src="([^"]*)"', cap_html)
                if im:
                    img = im.group(1)
                title = ""
                tm = re.search(
                    r'<div\s+class="tooltip-program-title">.*?<a[^>]*>([^<]+)</a>',
                    cap_html, re.DOTALL,
                )
                if tm:
                    title = tm.group(1).strip()
                capsules[bid] = {"desc": desc, "image": img, "title": title}

            programs = []
            for cell in re.finditer(
                r'<li[^>]*>\s*'
                r'<span\s+class="time"[^>]*>([^<]+)</span>\s*'
                r'<div\s+class="program">\s*'
                r'<a\s+href="(https?://telkac\.zoznam\.sk/[^"]+)"[^>]*\s+bid="(\d+)"[^>]*>'
                r'([^<]+)</a>',
                row_html, re.DOTALL,
            ):
                time_str = cell.group(1).strip()
                href = cell.group(2)
                bid = int(cell.group(3))
                title = cell.group(4).strip()
                cap = capsules.get(bid, {})
                programs.append({
                    "time": time_str,
                    "title": title,
                    "href": href,
                    "bid": bid,
                    "desc": cap.get("desc", ""),
                    "image": cap.get("image", ""),
                })

            programs = self._derive_durations(programs)
            rows.append(programs)
        return rows

    def _derive_durations(self, programs):
        for i in range(len(programs) - 1):
            dur = self._time_diff_minutes(programs[i]["time"], programs[i + 1]["time"])
            programs[i]["duration"] = dur
        if programs:
            programs[-1]["duration"] = 0
        return programs

    def _time_diff_minutes(self, t1, t2):
        def to_mins(t):
            parts = t.strip().split(":")
            return int(parts[0]) * 60 + int(parts[1])
        m1 = to_mins(t1)
        m2 = to_mins(t2)
        if m2 < m1:
            m2 += 24 * 60
        return m2 - m1

    def program_detail(self, url):
        html = self._get(url if url.startswith("/") else f"/{url}")
        poster = ""
        pm = re.search(
            r'<div\s+class="box-rating-top">.*?<img\s+src="([^"]*)"',
            html, re.DOTALL,
        )
        if pm:
            poster = pm.group(1)
        rating = ""
        rm = re.search(
            r'<div\s+class="box-rating-top">.*?<span>(\d+%)</span>',
            html, re.DOTALL,
        )
        if rm:
            rating = rm.group(1)
        plot = ""
        pm2 = re.search(r'<dt>Obsah:</dt>\s*<dd>([^<]+)</dd>', html)
        if pm2:
            plot = pm2.group(1).strip()
        metadata = {}
        for dt_dd in re.finditer(r'<dt>([^<]+):</dt>\s*<dd>([^<]+)</dd>', html):
            key = dt_dd.group(1).strip().rstrip(":")
            val = dt_dd.group(2).strip()
            if key not in metadata:
                metadata[key] = val
        return {"poster": poster, "rating": rating, "plot": plot, "metadata": metadata}

    def _unescape(self, text):
        return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
