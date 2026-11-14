import re, requests
BASE = "https://url.publishedprices.co.il"
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
r = s.get(BASE + "/login", timeout=30)
print("LOGIN_PAGE", r.status_code, len(r.text))
for m in re.finditer(r'<(?:meta|input)[^>]*csrf[^>]*>', r.text, re.I): print("CSRF_TAG", m.group(0)[:200])
m = re.search(r'csrftoken[^>]*?(?:content|value)="([^"]+)"', r.text, re.I) or re.search(r'(?:content|value)="([^"]+)"[^>]*csrftoken', r.text, re.I)
tok = m.group(1) if m else ""
print("TOKEN_LEN", len(tok))
r2 = s.post(BASE + "/login/user", data={"username":"RamiLevi","password":"","Submit":"Sign in","csrftoken":tok}, timeout=30)
print("POST", r2.status_code, r2.url)
print("POST_BODY", re.sub(r'\s+',' ', re.sub(r'<script.*?</script>','',r2.text, flags=re.S))[:400])
r3 = s.get(BASE + "/file", timeout=30)
print("FILE_PAGE", r3.status_code, r3.url)
print("FILE_BODY", re.sub(r'\s+',' ', re.sub(r'<script.*?</script>','',r3.text, flags=re.S))[:400])
for host in ["https://prices.carrefour.co.il/", "https://prices.mega.co.il/"]:
    try:
        x = requests.get(host, timeout=40, headers={"User-Agent":"Mozilla/5.0"}); print("HOST", host, x.status_code, len(x.text))
    except Exception as e: print("HOST", host, "ERROR", type(e).__name__)
