#!/usr/bin/env python3
"""Build-time: log in via Playwright, download all channel logos, write manifest.
Each logo is saved as {internalNameSuffix}.png and keyed by suffix in the manifest."""

import argparse
import json
import os
import re
import sys
import traceback
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import requests as req_lib

BASE = "https://tv.flexitv.sk"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MEDIA_DIR = os.path.join(
    REPO_ROOT, "plugin.video.flexitv", "resources", "media", "channels"
)
MANIFEST_PATH = os.path.join(MEDIA_DIR, "_manifest.json")


def _normalize(s):
    """Normalize a channel suffix or logo filename stem for matching."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r'\(\d+\)?', "", s)  # strip (1) or (1 (dedup suffix)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _normalize_variants(s):
    """Return a list of normalized variants for matching (with/without _hd)."""
    base = _normalize(s)
    variants = [base]
    no_hd = re.sub(r"_hd$", "", base)
    if no_hd and no_hd != base:
        variants.append(no_hd)
    with_hd = base + "_hd"
    if with_hd not in variants:
        variants.append(with_hd)
    return variants


def _alnum(s):
    """Return all alphanumeric characters in order (no underscores)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _words(s):
    """Split into words by underscore and camelCase."""
    t = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
    parts = re.sub(r'[^a-z0-9]+', '_', t.lower()).split('_')
    return {p for p in parts if len(p) > 1 and p not in ('hd', 'tv')}


def _word_overlap(stem, suffix):
    """Fraction of words in common (0..1)."""
    sw = _words(stem)
    ss = _words(suffix)
    if not sw or not ss:
        return 0.0
    common = sw & ss
    smaller = min(len(sw), len(ss))
    return len(common) / smaller


class _LogoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.logos = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        attr_dict = dict(attrs)
        if "channellogo" not in (attr_dict.get("class") or "").split():
            return
        style = attr_dict.get("style", "")
        m = re.search(
            r'background-image\s*:\s*url\(\s*(["\']?)([^)"\']+)\1\s*\)',
            style, re.IGNORECASE
        )
        if m:
            self.logos.append(m.group(2).strip())


def _abs_url(url):
    if url.startswith("//"):
        return "https:" + url
    return urljoin(BASE, url)


def _filename_from_url(url):
    stem = url.rsplit("/", 1)[-1] if url else ""
    return stem.split("?")[0]


def _stem_from_url(url):
    fn = _filename_from_url(url)
    return re.sub(r"\.[a-z0-9]+$", "", fn, flags=re.IGNORECASE)


def _download(url, dest):
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        },
    )
    with urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)


def _get_suffixes_from_server():
    """Fetch the initial page HTML and extract allTVChannels JSON → list of suffixes."""
    session = req_lib.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    })
    resp = session.get(f"{BASE}/pctv/")
    html = resp.text

    idx = html.find("allTVChannels = [")
    second = html.find("allTVChannels = [", idx + 10)
    if second >= 0:
        idx = second
    start = html.find("[", idx)
    end_marker = "categories = ["
    end = html.find(end_marker, start)
    last = html.rfind("]", start, end)
    raw = html[start:last + 1]
    data = json.loads(raw)

    suffixes = []
    for item in data:
        ch = item.get("channel", item) if isinstance(item, dict) else {}
        suffix = ch.get("internalNameSuffix", "") or ""
        name = ch.get("name", "") or ""
        if suffix:
            suffixes.append((suffix, name))
    return suffixes


def fetch_rendered_html_and_logos(user, password):
    """Login via Playwright, return (html, logo_urls)."""
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="sk-SK",
            timezone_id="Europe/Bratislava",
        )
        page = context.new_page()

        page.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        }""")

        page.goto(f"{BASE}/pctv/", wait_until="load", timeout=30000)
        page.wait_for_timeout(2000)

        with page.expect_navigation(timeout=20000) as nav_info:
            page.evaluate("document.getElementById('hauth-login-form').submit()")
            nav_info.value

        if "ucet.flexi.sk" in page.url:
            page.wait_for_timeout(2000)
            user_js = json.dumps(user)
            pass_js = json.dumps(password)
            page.evaluate(f"""
                document.querySelector('input[name="username"]').value = {user_js};
                document.querySelector('input[name="current_password"]').value = {pass_js};
            """)
            page.wait_for_timeout(300)
            try:
                with page.expect_navigation(timeout=30000) as nav_info:
                    page.evaluate("document.querySelector('form').submit()")
                    nav_info.value
            except PwTimeout:
                pass
            page.wait_for_timeout(5000)

        if "/pctv/programs/" not in page.url:
            try:
                page.goto(f"{BASE}/pctv/", wait_until="load", timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(5000)

        for retry in range(15):
            count = page.evaluate(
                "document.querySelectorAll('.channelitem').length"
            )
            if count > 0:
                break
            page.wait_for_timeout(2000)

        logos = page.evaluate("""
            Array.from(document.querySelectorAll('.channellogo')).map(el => {
                const style = el.getAttribute('style') || '';
                const m = style.match(/background-image\\s*:\\s*url\\(\\s*['"]?([^)'"]+)['"]?\\s*\\)/i);
                return m ? m[1] : null;
            }).filter(Boolean)
        """)

        browser.close()
        return logos


def main():
    parser = argparse.ArgumentParser(description="Download channel logos")
    parser.add_argument("--user", default="")
    parser.add_argument("--pass", dest="password", default="")
    args = parser.parse_args()

    os.makedirs(MEDIA_DIR, exist_ok=True)

    if not args.user or not args.password:
        print("No credentials provided — writing empty manifest")
        with open(MANIFEST_PATH, "w") as f:
            json.dump({}, f)
        print(f"Wrote empty {MANIFEST_PATH}")
        return

    # Step 1: get suffixes from server HTML (no auth needed)
    print("Fetching channel list from server...")
    suffixes = _get_suffixes_from_server()
    print(f"Found {len(suffixes)} channels with suffixes")

    # Step 2: log in via Playwright and get channellogo URLs from rendered DOM
    print("Logging in via Playwright...")
    logo_urls = fetch_rendered_html_and_logos(args.user, args.password)
    print(f"Found {len(logo_urls)} channellogo divs")

    # Build logo stems with normalized variants for matching
    logo_entries = []
    for url in logo_urls:
        stem = _stem_from_url(url)
        variants = _normalize_variants(stem)
        if variants:
            logo_entries.append((url, stem, variants))

    # Build suffix lookup by normalized variants
    suffix_map = {}  # normalized_form → (original_suffix, name)
    for suffix, name in suffixes:
        variants = _normalize_variants(suffix)
        for norm in variants:
            if norm and norm not in suffix_map:
                suffix_map[norm] = (suffix, name)

    # Match: for each logo entry, find a matching suffix
    manifest = {}
    seen_suffixes = set()
    downloaded = 0
    used_logos = set()

    for url, stem, logo_variants in logo_entries:
        if stem in used_logos:
            continue

        # Phase 1: find the suffix that matches this logo (try all variants)
        match = None
        for norm in logo_variants:
            match = suffix_map.get(norm)
            if match:
                break

        # Phase 2: fallback to alphanumeric matching (for underscore differences)
        if not match:
            logo_alnum = _alnum(stem)
            logo_alnum_no_hd = re.sub(r"hd$", "", logo_alnum)
            cand = []
            for suff, name in suffixes:
                suff_alnum = _alnum(suff)
                suff_alnum_no_hd = re.sub(r"hd$", "", suff_alnum)
                if logo_alnum == suff_alnum or logo_alnum_no_hd == suff_alnum_no_hd:
                    cand.append((suff, name))
            if cand:
                match = min(cand, key=lambda x: len(x[0]))

        # Phase 3: word-overlap matching (handles word reversal, camelCase)
        if not match:
            cand = []
            for suff, name in suffixes:
                score = _word_overlap(stem, suff)
                if score >= 0.5:
                    cand.append((score, suff, name))
            if cand:
                cand.sort(key=lambda x: -x[0])
                match = (cand[0][1], cand[0][2])

        if not match:
            print(f"  SKIP '{stem}' → no matching suffix")
            continue

        suffix, name = match
        if suffix in seen_suffixes:
            continue

        used_logos.add(stem)
        seen_suffixes.add(suffix)
        filename = f"{suffix}.png"
        dest = os.path.join(MEDIA_DIR, filename)
        abs_url = _abs_url(url)

        if os.path.isfile(dest):
            manifest[suffix] = filename
            continue

        try:
            print(f"  {filename}  ({name})")
            _download(abs_url, dest)
            manifest[suffix] = filename
            downloaded += 1
        except Exception as e:
            print(f"  FAILED {filename}: {e}", file=sys.stderr)

    # Report unmatched suffixes
    matched_suffixes = set(manifest.keys())
    unmatched = set(s for s, n in suffixes if s) - matched_suffixes
    if unmatched:
        print(f"\nUnmatched suffixes (no logo found): {len(unmatched)}")
        for s in sorted(unmatched)[:20]:
            n = next((n for suff, n in suffixes if suff == s), "")
            print(f"  suffix='{s}' name='{n}'")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print(f"\nDownloaded {downloaded} new logos, wrote {MANIFEST_PATH}")
    print(f"Manifest has {len(manifest)} entries")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
