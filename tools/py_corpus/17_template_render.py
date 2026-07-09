def render(template, context):
    result = template
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result

def render_expr(expr, context):
    return eval(expr, {"__builtins__": {}}, context)
