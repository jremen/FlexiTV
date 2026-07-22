import datetime
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

    def schedule(self, day_slug, chids=None, full_day=False):
        path = f"/tv-program/{day_slug}"
        html = self._get(path)
        stations = self._parse_station_list(html)
        rows = self._parse_timeline_rows(html)
        chid_to_programs = {}
        for i, st in enumerate(stations):
            chid_to_programs[st["chid"]] = rows[i] if i < len(rows) else []
        if chids:
            chid_set = set(chids)
            stations = [s for s in stations if s["chid"] in chid_set]
        now_mins = self._now_minutes()
        base_date = self._cet_now().date()
        result = []
        for station in stations:
            all_programs = chid_to_programs.get(station["chid"], [])
            parsed = []
            day_offset = 0
            prev_start = None
            for prog in all_programs:
                start = self._to_minutes(prog["time"])
                if start is None:
                    continue
                if prev_start is not None and start < prev_start:
                    day_offset += 1
                abs_start = start + day_offset * 1440
                dur = prog.get("duration", 0)
                if dur == 0:
                    dur = 180
                prog_date = base_date + datetime.timedelta(days=day_offset)
                prog["start_dt"] = datetime.datetime(
                    prog_date.year, prog_date.month, prog_date.day,
                    start // 60, start % 60
                )
                parsed.append((abs_start, abs_start + dur, prog))
                prev_start = start
            selected = []
            if full_day:
                for s, e, prog in parsed:
                    if s <= now_mins < e or s > now_mins:
                        selected.append(prog)
            else:
                current = None
                next_prog = None
                for i, (s, e, prog) in enumerate(parsed):
                    if s <= now_mins < e:
                        current = prog
                        if i + 1 < len(parsed):
                            next_prog = parsed[i + 1][2]
                        break
                    elif s > now_mins:
                        next_prog = prog
                        break
                if current:
                    selected.append(current)
                if next_prog:
                    selected.append(next_prog)
            if selected:
                result.append({"station": station, "programs": selected})
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
            dur = self._program_duration(programs[i]["time"], programs[i + 1]["time"])
            programs[i]["duration"] = dur
        if programs:
            programs[-1]["duration"] = 0
        return programs

    def _cet_now(self):
        now = datetime.datetime.utcnow()
        offset = datetime.timedelta(hours=2 if self._is_cest(now) else 1)
        return now + offset

    def _now_minutes(self):
        cet = self._cet_now()
        return cet.hour * 60 + cet.minute

    def _is_cest(self, dt):
        year = dt.year
        mar = datetime.date(year, 3, 31)
        while mar.weekday() != 6:
            mar -= datetime.timedelta(days=1)
        start = datetime.datetime(year, mar.month, mar.day, 1, 0, 0)
        oct = datetime.date(year, 10, 31)
        while oct.weekday() != 6:
            oct -= datetime.timedelta(days=1)
        end = datetime.datetime(year, oct.month, oct.day, 1, 0, 0)
        return start <= dt < end

    def _to_minutes(self, t):
        parts = t.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return None

    def _program_duration(self, t1, t2):
        m1 = self._to_minutes(t1)
        m2 = self._to_minutes(t2)
        if m1 is None or m2 is None:
            return 0
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
