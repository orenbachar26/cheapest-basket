import re, requests
H={"User-Agent":"Mozilla/5.0"}
print("== Bina portals")
for host in ["zolvebegadol","kingstore","maayan2000","shefabirkathashem","hazihinam","victory"]:
    for path in ["/", "/MainIO_Hok.aspx"]:
        u=f"https://{host}.binaprojects.com{path}"
        try:
            r=requests.get(u,headers=H,timeout=30)
            print("BINA",u,r.status_code,len(r.text),re.sub(r"\s+"," ",r.text[:160]))
        except Exception as e: print("BINA",u,"ERR",type(e).__name__)
print("== Cerberus usernames")
B="https://url.publishedprices.co.il"
for user in ["ZolVebegadol","zolvebegadol","ZolVeBegadol","Zol_Vebegadol","zol","ZolBegadol","Zol","zolbegadol","zolvbegadol","ZOL_VEBEGADOL","Hazi_Hinam","hazihinam","Victory","victory","VictoryRetail"]:
    try:
        s=requests.Session();s.headers.update(H)
        r=s.get(B+"/login",timeout=30);tok=re.search(r'name="csrftoken" content="([^"]+)"',r.text).group(1)
        r2=s.post(B+"/login/user",data={"username":user,"password":"","Submit":"Sign in","csrftoken":tok},timeout=30)
        print("CERB",user,"OK" if r2.url.rstrip("/").endswith("/file") else "no")
    except Exception as e: print("CERB",user,"ERR",type(e).__name__)
