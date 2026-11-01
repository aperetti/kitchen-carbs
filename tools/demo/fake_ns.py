"""Stand-in Nightscout for the demo reels: a made-up CGM trace with bumps after the demo meals (seed.py)."""
import json, math, time
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

def meals():   # the same times seed.py logs, for the last three days
    out = []
    for back in (2, 1, 0):
        d = date.today() - timedelta(days=back)
        for hhmm, grams in (("07:30", 55), ("12:15", 60), ("18:00", 70)):
            out.append((datetime.fromisoformat(f"{d}T{hhmm}").timestamp(), grams))
    return out

def sgv(t, ms):
    v = 112 + 14 * math.sin(t / 5400) + 6 * math.sin(t / 1300)
    for m, g in ms:
        d = (t - m) / 60
        if 0 < d < 240:
            v += g * 1.6 * (d / 55) * math.exp(1 - d / 55)
    h = datetime.fromtimestamp(t)
    if h.hour in (3, 4):
        v -= 28 * math.sin(math.pi * (t - h.replace(hour=3, minute=0, second=0).timestamp()) / 7200)
    return int(max(55, min(320, v)))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); now = time.time()
        if u.path == "/api/v1/entries/sgv.json":
            start = datetime.combine(date.today() - timedelta(days=3), datetime.min.time()).timestamp()
            gt = int(q.get("find[date][$gt]", [0])[0]) / 1000; lte = int(q.get("find[date][$lte]", [now * 1000])[0]) / 1000
            if "find[date][$gt]" not in q:
                gt, lte = now - 300, now
            ms, t, body = meals(), max(gt, start), []
            t = t - t % 300 + 300
            while t <= min(lte, now):
                body.append({"date": int(t * 1000), "sgv": sgv(t, ms), "direction": "Flat"}); t += 300
            body.reverse()
        elif u.path == "/api/v2/properties/iob":
            body = {"iob": {"iob": 0.35, "mills": int(now * 1000) - 120000, "source": "Loop"}}
        elif u.path == "/api/v1/status.json":
            body = {"settings": {"thresholds": {"bgTargetBottom": 70, "bgTargetTop": 180}}}
        else:
            body = []
        b = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

ThreadingHTTPServer(("127.0.0.1", 8766), H).serve_forever()
