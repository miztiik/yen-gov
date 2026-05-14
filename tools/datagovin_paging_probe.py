"""Probe OGD pagination behaviour."""
import io, sys
import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UUID = "1f2e77f0-6742-4671-ae29-8836d2110a5c"
KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
UA = {"User-Agent": "Mozilla/5.0 yen-gov-recon"}

with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as c:
    for limit in (10, 50, 100, 200):
        url = f"https://api.data.gov.in/resource/{UUID}?api-key={KEY}&format=json&limit={limit}&offset=0"
        try:
            r = c.get(url)
            d = r.json()
            print(f"limit={limit}  status={r.status_code}  count={d.get('count')}  total={d.get('total')}")
        except Exception as exc:
            print(f"limit={limit}  ERROR {type(exc).__name__}: {exc}")
