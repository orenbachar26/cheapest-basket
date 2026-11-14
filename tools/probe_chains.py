import re, requests, json
BASE = "https://url.publishedprices.co.il"
USERS = ["RamiLevi","yohananof","osherad","TivTaam","HaziHinam","Victory","doralon","Keshet","Stop_Market","NetivHesed","ZolVebegadol","SuperYuda","politzer","freshmarket","SalachD","Maayan2000","Bareket","superdosh","CoopIsrael"]
def probe(u):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    try:
        r = s.get(BASE + "/login", timeout=30)
        m = re.search(r'name="csrftoken"[^>]*content="([^"]+)"|name="csrftoken" value="([^"]+)"|<meta name="csrftoken" content="([^"]+)"', r.text)
        tok = next((g for g in (m.groups() if m else []) if g), "")
        r2 = s.post(BASE + "/login/user", data={"username": u, "password": "", "Submit": "Sign in", "csrftoken": tok}, timeout=30, allow_redirects=True)
        r3 = s.post(BASE + "/file/json/dir", data={"sEcho":1,"iColumns":5,"sColumns":",,,,","iDisplayStart":0,"iDisplayLength":100000,"mDataProp_0":"fname","sSearch":"","bRegex":"false","iSortingCols":0,"cd":"/","csrftoken":tok}, timeout=60)
        n = None
        try: n = len(r3.json().get("aaData", []))
        except Exception: pass
        return f"{u}: login={r2.status_code} dir={r3.status_code} files={n}"
    except Exception as e:
        return f"{u}: ERROR {type(e).__name__} {str(e)[:80]}"
print("== publishedprices (Cerberus)")
for u in USERS: print(probe(u))
print("== Carrefour direct")
try:
    r = requests.get("https://prices.carrefour.co.il/", timeout=30, headers={"User-Agent":"Mozilla/5.0"}); print("carrefour", r.status_code, len(r.text))
except Exception as e: print("carrefour ERROR", type(e).__name__, str(e)[:80])
