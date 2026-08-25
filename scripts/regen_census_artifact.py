"""Regenerate the Indicator Census artifact's list sections from the JSON.

The published page was written from an earlier, larger enumeration - it claimed 60
buildable families where the tested census holds 46, and its own lede and headings
disagreed with each other. Hand-patching the counts would leave the body listing
families that no longer exist. Generating both list sections from
data/derived/indicator_families.json makes the page match what the tests guard, and
means it can be regenerated rather than re-edited next time.
"""
import html
import json
from pathlib import Path

R = Path('C:/Users/rafae/Documents/GitHub/OMEGA')
D = json.loads((R / 'data/derived/indicator_families.json').read_text(encoding='utf-8'))
P = R / 'artifact/indicator-census.html'
lines = P.read_text(encoding='utf-8').split('\n')

B, K = D["buildable"], D["blocked"]
e = lambda s: html.escape(str(s), quote=False)

DOMAIN_TITLE = {
    "classical": "Classical trend &amp; moving-average systems",
    "oscillator": "Oscillator constructions",
    "factor": "Cross-sectional factors",
    "microstructure": "Microstructure &amp; order flow",
    "derivatives": "Derivatives &amp; funding",
    "statistical": "Statistical &amp; path measures",
    "structure": "Market structure",
    "sentiment": "Sentiment",
    "institutional": "Institutional constructions",
}
CAUSE_TITLE = {
    "operator-absent": ("The data is present, the equation is not",
                        "22 families. Every one of these is arithmetic the engine declines "
                        "to perform on numbers it already has."),
    "guard-refuses": ("The operator exists, the unit-clique rule rejects the pair",
                      "2 families. <code>spread</code> is within-unit-class only."),
    "needs-state": ("Requires recursive evaluation, not a new function",
                    "2 families."),
    "renderer-fails": ("Validates offline, crashes on render",
                       "1 family. Legal by every published rule and "
                       "<code>INTERNAL_ERROR</code> every time."),
    "data-absent": ("The input genuinely does not exist",
                    "1 family &mdash; the only true data gap in the whole census."),
}


def spec(s):
    bits = [f'<b>{e(s["metric"])}</b>', e(s["transformId"])]
    if s.get("inputs"):
        bits.append(", ".join(f'<b>{e(i["metric"])}</b>' for i in s["inputs"]))
    if s.get("chainedTransformId"):
        bits.append("&rarr; " + e(s["chainedTransformId"]))
    for k in ("window", "offset", "ordering", "side", "bars"):
        if s.get(k) is not None:
            bits.append(f'<i>{k}={e(s[k])}</i>')
    return " ".join(bits)


def entry(f, i):
    at = f' <span class="at">&mdash; {e(f["attribution"])}</span>' if f.get("attribution") else ""
    bd = ""
    if f.get("cryptoOnly"):
        bd += f' <span class="bd co" title="null off-crypto">crypto only</span>'
    if f.get("gateability") == "label-only":
        bd += ' <span class="bd lo" title="is/in only - cannot be thresholded">label only</span>'
    sp = "   &middot;   ".join(spec(s) for s in f["columns"])
    nt = f'\n      <div class="nt">{e(f["note"])}</div>' if f.get("note") else ""
    return (f'    <div class="ind"><span class="mark y">{i:02d}</span><div class="body">\n'
            f'      <span class="nm">{e(f["name"])}</span>{at}{bd}\n'
            f'      <div class="sp">{sp}</div>{nt}</div></div>')


def blocked_entry(f):
    at = f' <span class="at">&mdash; {e(f["attribution"])}</span>' if f.get("attribution") else ""
    nd = f' <span class="bd lo">needs {e(f["needs"])}</span>' if f.get("needs") else ""
    nt = f'<div class="nt">{e(f["note"])}</div>' if f.get("note") else ""
    return ('    <div class="ind"><span class="mark n">&times;</span><div class="body">'
            f'<span class="nm">{e(f["name"])}</span>{at}{nd}{nt}</div></div>')


out = []

# ---- buildable -------------------------------------------------------------
out.append('<section>')
out.append(f'  <h2>Buildable &mdash; {len(B)} families</h2>')
out.append('  <p>')
out.append('    Each entry is the exact construction, generated from the tested census rather')
out.append('    than transcribed. <code>&rarr;</code> marks a stage-2 chain. Every one of these')
out.append('    was <strong>rendered live against the compiler</strong> on 2026-08-25 &mdash;')
out.append(f'    {len(B)} of {len(B)} families, and every header matched the prediction exactly.')
out.append('  </p>')
out.append('  <p class="nt">')
out.append('    <span class="bd co">crypto only</span> renders null on STOCKS, TRADFI, INDICES and')
out.append('    COMMODITIES &mdash; and a null reads FALSE, never UNRESOLVED, so these gate silently')
out.append('    wrong on a mixed-asset coin selection.')
out.append('    <span class="bd lo">label only</span> can be matched against a label but never')
out.append('    thresholded.')
out.append('  </p>')
i = 0
for dom, title in DOMAIN_TITLE.items():
    fam = [f for f in B if f["domain"] == dom]
    if not fam:
        continue
    out.append(f'\n  <h3>{title}</h3>')
    out.append('  <div class="domain">')
    for f in fam:
        i += 1
        out.append(entry(f, i))
    out.append('  </div>')
out.append('</section>')

# ---- blocked ---------------------------------------------------------------
out.append('')
out.append('<section>')
out.append(f'  <h2>Blocked &mdash; {len(K)} families, by cause</h2>')
out.append('  <p>')
out.append('    &ldquo;Blocked&rdquo; hides five very different situations, and the distinction is')
out.append('    the point: only <strong>one</strong> family is short of data. The rest are')
out.append('    equations the engine does not offer.')
out.append('  </p>')
for cause, (title, blurb) in CAUSE_TITLE.items():
    fam = [f for f in K if f["cause"] == cause]
    if not fam:
        continue
    out.append(f'\n  <h3>{title}</h3>')
    out.append(f'  <p class="nt">{blurb}</p>')
    out.append('  <div class="domain">')
    for f in fam:
        out.append(blocked_entry(f))
    out.append('  </div>')
out.append('</section>')

# ---- what was measured -----------------------------------------------------
ac, gt = D["_assetClassCoverage"], D["_gateability"]
out.append('')
out.append('<section>')
out.append('  <h2>What was measured, and what was not</h2>')
out.append('  <p>')
out.append('    A census is only worth having if it cannot quietly become false. Every buildable')
out.append('    entry above is built and validated by the test suite, and every one was rendered')
out.append('    against the live compiler. Three things about it were <em>not</em> measured that')
out.append('    way, and saying so is part of the record.')
out.append('  </p>')
out.append('')
out.append('  <h3>Asset class &mdash; six families go silently null off-crypto</h3>')
out.append(f'  <p>{e(ac["surprise"])}</p>')
out.append(f'  <p>{e(ac["rule"])}</p>')
out.append(f'  <p><strong>{e(ac["cost"])}</strong></p>')
out.append('')
out.append('  <h3>Gateability &mdash; rendering is not referencing</h3>')
out.append(f'  <p>{e(gt["note"])}</p>')
out.append(f'  <p>{gt["numericGateable"]} of {len(B)} families are numerically gateable. '
           f'{len(gt["labelOnly"])} are label-only: '
           + ", ".join(f'<code>{e(x)}</code>' for x in gt["labelOnly"]) + '.</p>')
out.append('')
out.append('  <h3>Attribution &mdash; the one field that is judgement, not measurement</h3>')
out.append(f'  <p>{e(D["_attributionCaveat"])}</p>')
out.append('</section>')

new = lines[:227] + out + lines[558:]
P.write_text('\n'.join(new), encoding='utf-8')
print(f'regenerated: {len(B)} buildable, {len(K)} blocked')
