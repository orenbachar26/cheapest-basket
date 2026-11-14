import re, requests, gzip, io, zipfile
BASE = "https://url.publishedprices.co.il"
def head(b, n=700):
    try:
        if b[:2] == b'\x1f\x8b': b = gzip.decompress(b)
        elif b[:2] == b'PK': z = zipfile.ZipFile(io.BytesIO(b)); b = z.read(z.namelist()[0])
        return b.decode('utf-8-sig', 'replace')[:n]
    except Exception as e: return "ERR "+str(e)
for user in ["RamiLevi","yohananof","osherad","Victory"]:
    print("#####", user)
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
    r = s.get(BASE+"/login", timeout=30)
    tok = re.search(r'name="csrftoken" content="([^"]+)"', r.text).group(1)
    r2 = s.post(BASE+"/login/user", data={"username":user,"password":"","Submit":"Sign in","csrftoken":tok}, timeout=30)
    tok = re.search(r'name="csrftoken" content="([^"]+)"', r2.text)
    tok = tok.group(1) if tok else ""
    print("landed", r2.url)
    r3 = s.post(BASE+"/file/json/dir", data={"sEcho":1,"iColumns":5,"sColumns":",,,,","iDisplayStart":0,"iDisplayLength":100000,"mDataProp_0":"fname","mDataProp_1":"typeLabel","mDataProp_2":"size","mDataProp_3":"ftime","mDataProp_4":"","sSearch":"","bRegex":"false","iSortingCols":0,"cd":"/","csrftoken":tok}, timeout=60)
    print("dir", r3.status_code, r3.text[:200].replace("\n"," "))
    try: rows = r3.json().get("aaData", [])
    except Exception: rows = []
    names = [x.get("fname") if isinstance(x, dict) else x[0] for x in rows]
    print("files", len(names), names[:6])
    for pref in ["Stores", "PriceFull"]:
        cand = [n for n in names if n and n.startswith(pref)]
        print(pref, len(cand), cand[:2])
        if cand:
            d = s.get(BASE+"/file/d/"+cand[0], timeout=120)
            print("  dl", d.status_code, len(d.content)); print(head(d.content))
