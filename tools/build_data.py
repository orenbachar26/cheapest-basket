#!/usr/bin/env python3
"""Nightly data builder: downloads the legally-mandated Israeli supermarket price
files, keeps stores near the configured centre, and writes compact JSON for the app."""
import gzip, io, json, math, os, re, sys, time, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
import requests

CENTER = (31.8120, 34.7790)   # Gedera
RADIUS_KM = float(os.environ.get("RADIUS_KM", "40"))
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT, exist_ok=True)
GEOCACHE_PATH = os.path.join(OUT, "geocache.json")
UA = {"User-Agent": "Mozilla/5.0 (cheapest-basket price comparison)"}

CERBERUS = "https://url.publishedprices.co.il"
CERBERUS_CHAINS = {  # login user -> display name
    "RamiLevi": "רמי לוי",
    "yohananof": "יוחננוף",
    "osherad": "אושר עד",
    "TivTaam": "טיב טעם",
    "HaziHinam": "חצי חינם",
    "Keshet": "קשת טעמים",
    "Stop_Market": "סטופ מרקט",
    "politzer": "פוליצר",
    "freshmarket": "פרשמרקט",
    "Victory": "ויקטורי",
    "SalachD": "סאלח דבאח",
}
SHUFERSAL = "https://prices.shufersal.co.il"
LIMIT_STORES_PER_CHAIN = int(os.environ.get("LIMIT_STORES_PER_CHAIN", "0"))  # 0 = no limit (testing aid)

log = lambda *a: print(*a, flush=True)


def haversine(a, b):
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def to_text(b):
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    elif b[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(b))
        b = z.read(z.namelist()[0])
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        t = b.decode("utf-16", "replace")
    else:
        try:
            t = b.decode("utf-8-sig")
        except UnicodeDecodeError:
            t = b.decode("windows-1255", "replace")
    return re.sub(r"^\s*<\?xml[^>]*\?>", "", t.lstrip("﻿"))


def parse(b):
    return ET.fromstring(to_text(b))


def tagname(e):
    return e.tag.split("}")[-1].lower()


def child_text(e, name):
    for c in e.iter():
        if tagname(c) == name and c.text:
            return c.text.strip()
    return ""


def parse_stores(b):
    root = parse(b)
    out = []
    for e in root.iter():
        if tagname(e) == "store" and any(tagname(c) == "storeid" for c in e):
            d = {tagname(c): (c.text or "").strip() for c in e if len(c) == 0}
            out.append({
                "sub": d.get("subchainid", ""),
                "id": d.get("storeid", ""),
                "name": d.get("storename", ""),
                "address": d.get("address", ""),
                "city": d.get("city", ""),
            })
    # SubChainID is sometimes only on the parent element
    if out and not any(s["sub"] for s in out):
        pass
    return out


def parse_items(b):
    root = parse(b)
    items = {}
    for e in root.iter():
        if tagname(e) != "item":
            continue
        d = {tagname(c): (c.text or "").strip() for c in e if len(c) == 0}
        code = d.get("itemcode", "")
        if not (code.isdigit() and len(code) >= 8):
            continue
        if d.get("bisweighted", "0") in ("1", "true", "True"):
            continue
        try:
            price = float(d.get("itemprice", "0"))
        except ValueError:
            continue
        if price <= 0:
            continue
        items[code] = {
            "price": price,
            "name": d.get("itemname", ""),
            "brand": d.get("manufacturername", ""),
            "qty": d.get("quantity", ""),
            "unit": d.get("unitofmeasure", ""),
        }
    return items


# ---------------------------------------------------------------- geocoding
geocache = {}
if os.path.exists(GEOCACHE_PATH):
    geocache = json.load(open(GEOCACHE_PATH, encoding="utf-8"))
_last = [0.0]


def geocode(q):
    if q in geocache:
        return geocache[q]
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": q, "format": "json", "limit": 1, "countrycodes": "il"},
                         headers=UA, timeout=30)
        j = r.json()
        res = [float(j[0]["lat"]), float(j[0]["lon"])] if j else None
    except Exception as e:
        log("geocode error", q, type(e).__name__)
        return None  # don't cache transient errors
    geocache[q] = res
    return res


LOCALITIES = {}


def load_localities():
    """CBS locality code -> Hebrew name (stores files carry only the numeric code)."""
    try:
        recs, offset = [], 0
        while True:
            r = requests.get("https://data.gov.il/api/3/action/datastore_search",
                             params={"resource_id": "5c78e9fa-c2e2-4771-93ff-7f400a12f7ba", "limit": 1000, "offset": offset},
                             headers=UA, timeout=60)
            part = r.json()["result"]["records"]
            if not part:
                break
            recs += part
            offset += len(part)
        sample = recs[0] if recs else {}
        log("localities fields:", list(sample.keys()))
        code_k = next((k for k in sample if "סמל" in k), None)
        name_k = next((k for k in sample if "שם" in k and "אנגל" not in k and "english" not in k.lower()), None)
        for x in recs:
            try:
                LOCALITIES[int(str(x[code_k]).strip())] = re.sub(r"\s+", " ", str(x[name_k])).strip()
            except Exception:
                pass
        log("localities loaded:", len(LOCALITIES), "e.g.", [(k, LOCALITIES[k]) for k in list(LOCALITIES)[:3]])
    except Exception as e:
        log("localities FAILED", type(e).__name__, str(e)[:120])


def locate_stores(stores):
    """Keep stores within radius. City-level pass first, then street-level for survivors."""
    for s in stores:
        if s["city"].isdigit() and int(s["city"]) in LOCALITIES:
            s["city"] = LOCALITIES[int(s["city"])]
    near = []
    log("  sample stores:", [(s["city"], s["address"]) for s in stores[:4]])
    for s in stores:
        city = s["city"] or ""
        c = geocode(f"{city}, ישראל") if city and not city.isdigit() else None
        if c is None and not city and s["address"]:
            c = geocode(f"{s['address']}, ישראל")
        if c is None:
            s["_skip"] = "nogeo"
            continue
        if haversine(CENTER, c) <= RADIUS_KM + 8:
            s["lat"], s["lng"] = c
            near.append(s)
    log("  nogeo:", sum(1 for s in stores if s.get("_skip")), "of", len(stores), "| within margin:", len(near))
    final = []
    for s in near:
        if s["address"] and s["city"] and not s["city"].isdigit():
            c = geocode(f"{s['address']}, {s['city']}, ישראל")
            if c and haversine((s["lat"], s["lng"]), c) <= 15:  # ignore street hits far from the city
                s["lat"], s["lng"] = c
        if haversine(CENTER, (s["lat"], s["lng"])) <= RADIUS_KM:
            final.append(s)
    return final


# ---------------------------------------------------------------- chains
def cerberus_session(user):
    s = requests.Session()
    s.headers.update(UA)
    r = s.get(CERBERUS + "/login", timeout=30)
    tok = re.search(r'name="csrftoken" content="([^"]+)"', r.text).group(1)
    r2 = s.post(CERBERUS + "/login/user",
                data={"username": user, "password": "", "Submit": "Sign in", "csrftoken": tok}, timeout=30)
    if not r2.url.rstrip("/").endswith("/file"):
        return None, None
    m = re.search(r'name="csrftoken" content="([^"]+)"', r2.text)
    return s, (m.group(1) if m else tok)


def cerberus_list(s, tok):
    r = s.post(CERBERUS + "/file/json/dir", data={
        "sEcho": 1, "iColumns": 5, "sColumns": ",,,,", "iDisplayStart": 0, "iDisplayLength": 100000,
        "mDataProp_0": "fname", "mDataProp_1": "typeLabel", "mDataProp_2": "size", "mDataProp_3": "ftime",
        "mDataProp_4": "", "sSearch": "", "bRegex": "false", "iSortingCols": 0, "cd": "/", "csrftoken": tok},
        timeout=90)
    return [x["fname"] for x in r.json().get("aaData", [])]


def run_cerberus(user, display):
    s, tok = cerberus_session(user)
    if not s:
        log(f"[{display}] login failed")
        return None
    names = cerberus_list(s, tok)
    store_files = sorted(n for n in names if n.startswith("Stores"))
    if not store_files:
        log(f"[{display}] no stores file")
        return None
    stores = parse_stores(s.get(CERBERUS + "/file/d/" + store_files[-1], timeout=120).content)
    # latest PriceFull per (sub, store)
    latest = {}
    for n in names:
        m = re.match(r"PriceFull(\d+)-(\d+)-(\d+)-(\d{8})-(\d{6})", n)
        if m:
            key = (int(m.group(2)), int(m.group(3)))
            if key not in latest or n > latest[key]:
                latest[key] = n
    for st in stores:
        if not st["sub"]:
            st["sub"] = "0"
    stores = [st for st in stores if (int(st["sub"] or 0), int(st["id"] or 0)) in latest
              or any(k[1] == int(st["id"] or 0) for k in latest)]
    near = locate_stores(stores)
    if LIMIT_STORES_PER_CHAIN:
        near = near[:LIMIT_STORES_PER_CHAIN]
    log(f"[{display}] stores={len(stores)} near={len(near)}")
    result = []
    for st in near:
        sid = int(st["id"] or 0)
        cand = [n for k, n in latest.items() if k[1] == sid and (k[0] == int(st["sub"] or 0))] or \
               [n for k, n in latest.items() if k[1] == sid]
        if not cand:
            continue
        try:
            b = s.get(CERBERUS + "/file/d/" + max(cand), timeout=180).content
            items = parse_items(b)
        except Exception as e:
            log(f"[{display}] store {sid} error {type(e).__name__}")
            continue
        if items:
            result.append((st, items))
    return result


def run_shufersal():
    display = "שופרסל"
    sess = requests.Session()
    sess.headers.update(UA)

    def list_cat(cat, maxpages=60):
        found, seen = [], set()
        for page in range(1, maxpages + 1):
            r = sess.get(f"{SHUFERSAL}/FileObject/UpdateCategory",
                         params={"catID": cat, "storeId": 0, "sort": "Time", "order": "Desc", "page": page}, timeout=60)
            links = re.findall(r'href="(https://pricesprodpublic[^"]+)"', r.text)
            links = [l.replace("&amp;", "&") for l in links]
            new = [l for l in links if l not in seen]
            if not new:
                break
            seen.update(new)
            found += new
        return found

    store_links = list_cat(5, 3)
    if not store_links:
        log("[שופרסל] no store links")
        return None
    stores = parse_stores(sess.get(store_links[0], timeout=120).content)
    near = locate_stores(stores)
    if LIMIT_STORES_PER_CHAIN:
        near = near[:LIMIT_STORES_PER_CHAIN]
    log(f"[{display}] stores={len(stores)} near={len(near)}")
    want = {int(s["id"]) for s in near if s["id"].isdigit()}
    links = list_cat(2, 60)
    latest = {}
    for l in links:
        m = re.search(r"PriceFull\d+-\d+-(\d+)-(\d{8})-(\d{6})", l)
        if m and int(m.group(1)) in want:
            sid = int(m.group(1))
            stamp = m.group(2) + m.group(3)
            if sid not in latest or stamp > latest[sid][0]:
                latest[sid] = (stamp, l)
    log(f"[{display}] pricefull links={len(links)} matched={len(latest)}")
    result = []
    for st in near:
        if not st["id"].isdigit() or int(st["id"]) not in latest:
            continue
        try:
            items = parse_items(sess.get(latest[int(st["id"])][1], timeout=180).content)
        except Exception as e:
            log(f"[{display}] store {st['id']} error {type(e).__name__}")
            continue
        if items:
            result.append((st, items))
    return result


# ---------------------------------------------------------------- main
def main():
    load_localities()
    chains = {}
    try:
        r = run_shufersal()
        if r:
            chains["שופרסל"] = r
    except Exception as e:
        log("[שופרסל] FAILED", type(e).__name__, str(e)[:200])
    for user, display in CERBERUS_CHAINS.items():
        try:
            r = run_cerberus(user, display)
            if r:
                chains[display] = r
        except Exception as e:
            log(f"[{display}] FAILED", type(e).__name__, str(e)[:200])
        json.dump(geocache, open(GEOCACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(geocache, open(GEOCACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)

    stores_out, price_rows = [], defaultdict(list)
    info = {}
    seen_stores = set()
    for chain, lst in chains.items():
        for st, items in lst:
            key = f"{chain}:{st['sub']}-{st['id']}"
            if key in seen_stores:
                continue
            seen_stores.add(key)
            idx = len(stores_out)
            stores_out.append({"chain": chain, "name": st["name"], "address": st["address"], "city": st["city"],
                               "lat": round(st["lat"], 5), "lng": round(st["lng"], 5)})
            for code, it in items.items():
                price_rows[code].append((idx, it["price"]))
                cur = info.get(code)
                if cur is None or len(it["name"]) > len(cur[0]):
                    info[code] = [it["name"], it["brand"], it["qty"], it["unit"]]
    # keep only barcodes sold in >=2 stores, so every item is comparable
    keep = {c for c, rows in price_rows.items() if len(rows) >= 2}
    prices = {c: [x for idx, p in price_rows[c] for x in (idx, p)] for c in keep}
    items_out = {c: info[c] for c in keep}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta = {"updated": now, "center": CENTER, "radiusKm": RADIUS_KM,
            "chains": {c: len(l) for c, l in chains.items()}, "stores": len(stores_out), "items": len(keep)}
    dump = lambda name, obj: json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"),
                                       ensure_ascii=False, separators=(",", ":"))
    dump("stores.json", stores_out)
    dump("items.json", items_out)
    dump("prices.json", prices)
    dump("meta.json", meta)
    log("DONE", json.dumps(meta, ensure_ascii=False))
    for n in ("stores", "items", "prices"):
        log(n, os.path.getsize(os.path.join(OUT, n + ".json")), "bytes")


if __name__ == "__main__":
    main()
