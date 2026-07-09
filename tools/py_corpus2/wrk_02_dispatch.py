HANDLERS = {}

def handler(name):
    def deco(fn):
        HANDLERS[name] = fn
        return fn
    return deco

def dispatch(event):
    fn = HANDLERS.get(event["type"])
    if fn is None:
        raise KeyError(event["type"])
    return fn(event["payload"])

@handler("ping")
def on_ping(payload):
    return {"pong": payload}
