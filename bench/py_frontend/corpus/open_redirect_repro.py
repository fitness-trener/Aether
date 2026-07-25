# Real-world shape — open redirect (CWE-601).
#
# A login flow takes `?next=` so it can send the user back where they
# came from. If the target is not constrained to the application's own
# host, `?next=https://evil.example/login` produces a phishing page the
# victim reached by clicking a link on the real, trusted domain. This is
# also the OAuth `redirect_uri` abuse primitive.
#
# CWE-601. Directly analogous, already ported in this repo:
#   - CVE-2018-14574 (Django CommonMiddleware open redirect) — see
#     bench/realworld_cve/cve_2018_14574_django_redirect_vulnerable.aeth
#
# The vulnerable shape:

from flask import redirect, request


def login_done():
    # `next` comes straight off the query string.
    return redirect(request.args.get("next"))


# The fix: never redirect to a caller-supplied absolute URL. Send the
# user to a fixed in-app location, or look the target up in an allowlist.

def login_done_safe():
    return redirect("/dashboard")


# In Aether this maps 1:1 onto E0718:
#   redirect(request.args.get("next"))  <-> redirect(nextUrl)                  -> E0718
#   redirect("/dashboard")              <-> redirect("/dashboard")             -> clean
#   (Aether's other sanctioned exit is safeRedirect(host, path), which pins
#    the authority and keeps the caller-supplied path.)
