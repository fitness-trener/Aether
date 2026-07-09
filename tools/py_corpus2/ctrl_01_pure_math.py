def compound_interest(principal, rate, periods):
    return principal * (1 + rate) ** periods

def amortization(principal, rate, months):
    monthly = rate / 12
    factor = (1 + monthly) ** months
    return principal * monthly * factor / (factor - 1)
