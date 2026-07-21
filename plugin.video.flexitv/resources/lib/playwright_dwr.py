import os, sys, json

BASE = "https://tv.flexitv.sk"


def get_stream_url(user, password, channel_id):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    except ImportError:
        return {"error": "playwright not installed"}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36",
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

        # Submit hauth form if present (triggers OIDC redirect)
        if page.evaluate("document.getElementById('hauth-login-form') !== null"):
            page.evaluate("document.getElementById('hauth-login-form').submit()")

        page.wait_for_timeout(3000)

        # On OIDC realm — fill login form
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
            except Exception:
                pass

        # Wait for redirect back to tv.flexitv.sk
        try:
            page.wait_for_url(f"{BASE}/**", timeout=25000)
        except PwTimeout:
            pass

        # Fallback: navigate directly
        if "tv.flexitv.sk" not in page.url:
            try:
                page.goto(f"{BASE}/pctv/", wait_until="load", timeout=20000)
            except Exception:
                pass
        page.wait_for_timeout(3000)

        # Wait for CentreServer
        ok = False
        for retry in range(8):
            ok = page.evaluate(
                "typeof CentreServer !== 'undefined' "
                "&& typeof CentreServer.createTVSession === 'function'"
            )
            if ok:
                break
            page.wait_for_timeout(2000)
        if not ok:
            browser.close()
            return {"error": "DWR not initialized", "url": page.url[:80]}

        with page.expect_response(
            lambda r: "dwr/call/plaincall/CentreServer.createTVSession.dwr" in r.url
                      and r.status == 200,
            timeout=30000,
        ) as resp_info:
            page.evaluate("""(cid) => {
                try {
                    CentreServer.createTVSession(cid, null, function(data) {
                        window._dwrResult = data;
                    });
                } catch(e) {
                    window._dwrResult = {error: e.message};
                }
            }""", channel_id)
            resp = resp_info.value

        try:
            page.wait_for_function(
                "() => typeof window._dwrResult !== 'undefined'", timeout=10000
            )
        except PwTimeout:
            pass

        data = page.evaluate("() => window._dwrResult")
        browser.close()

        if isinstance(data, dict) and "error" in data:
            return {"error": str(data.get("error", ""))}
        if not data or not isinstance(data, dict):
            return {"error": "No DWR result data"}

        playback_url = data.get("playbackUrl", "")
        if not playback_url:
            return {"error": "No playbackUrl in response"}

        return {
            "playbackUrl": playback_url,
            "sessionId": data.get("id", ""),
            "channelId": data.get("channelId", ""),
            "serverType": data.get("serverType", ""),
            "container": data.get("mediaInfo", {}).get("container", "HLS"),
        }


if __name__ == "__main__":
    import argparse
    import traceback
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--pass", required=True, dest="password")
    parser.add_argument("--channel-id", required=True, type=int)
    args = parser.parse_args()

    debug_log = os.path.join(
        os.path.expanduser("~"), "Library", "Logs", "flexitv_dwr_debug.log"
    )

    try:
        result = get_stream_url(args.user, args.password, args.channel_id)
        print(json.dumps(result))
        if "error" in result:
            sys.exit(1)
    except Exception:
        with open(debug_log, "w") as f:
            traceback.print_exc(file=f)
            f.write("\n---\n")
            f.write(f"sys.path: {sys.path}\n")
            f.write(f"os.environ keys: {list(os.environ.keys())}\n")
        raise
