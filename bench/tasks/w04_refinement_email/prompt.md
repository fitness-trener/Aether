# Task: contract-wedge — Email refinement type

Declare a refinement type `Email = String where contains?(self, "@")` —
i.e. an Email is a String that contains an `@`.

Write `domainOf(addr: Email) returns String` that returns the substring
after the last `@`. The function must be `pure`.

In `main`, call `domainOf("not-an-email")` — a String with no `@`. The
refinement boundary check **must catch** the call site and trigger a
structured `[E0302]` diagnostic at runtime. A non-refinement implementation
would either crash with an obscure exception or silently return garbage.
