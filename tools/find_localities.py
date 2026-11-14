import requests, json
H={"User-Agent":"Mozilla/5.0"}
for q in ["ישובים","רשימת ישובים","יישובים סמל ישוב","localities"]:
    try:
        r=requests.get("https://data.gov.il/api/3/action/package_search",params={"q":q,"rows":8},headers=H,timeout=40)
        print("Q",q,r.status_code)
        for p in r.json()["result"]["results"]:
            print(" PKG",p["title"][:60],"|",p["name"])
            for res in p["resources"][:4]:
                print("    RES",res["id"],res.get("format"),res.get("datastore_active"),(res.get("name") or "")[:50])
    except Exception as e: print("ERR",q,type(e).__name__,str(e)[:100])
