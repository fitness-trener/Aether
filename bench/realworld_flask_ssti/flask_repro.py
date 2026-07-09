# Real-world shape — Flask / Jinja2 server-side template injection
# (CWE-94). Flask is one of the most-used Python web frameworks (tens of
# millions of downloads/month). The classic SSTI bug: user input is
# concatenated INTO the template string and rendered, so `{{7*7}}` (and
# from there `{{config}}`, `{{().__class__...}}`) is evaluated → RCE.
#
# Documented class; a staple of every SSTI writeup and CTF. The vulnerable
# shape (still copy-pasted into real apps):

from flask import render_template_string, request

def greeting():
    name = request.args.get("name", "")
    # User input becomes part of the TEMPLATE, not the data — SSTI.
    template = "<h1>Hello " + name + "</h1>"       # <-- CWE-94
    return render_template_string(template)

# The fix: a fixed template; user input is passed as escaped DATA.

def greeting_safe():
    name = request.args.get("name", "")
    return render_template_string("<h1>Hello {{ name }}</h1>", name=name)

# In Aether this maps 1:1 onto E0719:
#   render_template_string("..." + name)   <-> renderTemplate("..." + name, "")  -> E0719
#   render_template_string("...{{name}}", name=name)
#                                          <-> renderTemplate("...{}", name)      -> clean
# See vulnerable.aeth / fixed.aeth in this directory.
