import os

LI_AT = os.environ.get("LI_AT", "")
JSESSIONID = os.environ.get("JSESSIONID", "")

if not LI_AT or not JSESSIONID:
    raise EnvironmentError(
        "Set LI_AT and JSESSIONID environment variables before running.\n"
        "Get them from Chrome DevTools > Application > Cookies > linkedin.com"
    )
