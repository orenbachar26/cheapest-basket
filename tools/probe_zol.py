import re, json, requests, gzip, collections
H={"User-Agent":"Mozilla/5.0"}
host="https://zolvebegadol.binaprojects.com"
r=requests.get(host+"/MainIO_Hok.aspx",headers=H,timeout=60)
rows=r.json()
print("ROWS",len(rows)); print("KEYS",list(rows[0].keys()))
print("TYPES",collections.Counter(x["TypeFile"] for x in rows))
pref=collections.Counter(re.match(r"[A-Za-z]+",x["FileNm"]).group(0) for x in rows); print("PREFIX",pref)
for x in rows[:3]: print("SAMPLE",x)
st=[x for x in rows if x["FileNm"].lower().startswith("stores")]
pf=[x for x in rows if x["FileNm"].lower().startswith("pricefull")]
print("stores files",len(st),"pricefull files",len(pf))
for kind,lst in (("STORES",st),("PRICEFULL",pf)):
    if not lst: continue
    n=lst[0]["FileNm"]
    for u in [f"{host}/Download.aspx?FileNm={n}", f"{host}/Download/{n}", f"{host}/{n}"]:
        try:
            d=requests.get(u,headers=H,timeout=90)
            print("DL",kind,u,d.status_code,len(d.content),d.headers.get("content-type"))
            if d.status_code==200 and len(d.content)>100:
                b=d.content
                try:
                    if b[:2]==b"\x1f\x8b": b=gzip.decompress(b)
                except Exception as e: print("gunzip err",e)
                print(b.decode("utf-8-sig","replace")[:600]); break
        except Exception as e: print("DL ERR",u,type(e).__name__)
