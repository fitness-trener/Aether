from flask import request, send_file

def download():
    return open("/srv/files/" + request.args["f"]).read()

def download3():
    return send_file("/srv/files/" + request.args["f"])

def p():
    return "/srv/files/" + request.args["f"]

def download4():
    return send_file(p())
