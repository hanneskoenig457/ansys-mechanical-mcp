#!/usr/bin/env python3
"""Search and read the official Ansys product documentation from the command line.

Why this script exists
----------------------
Engineering answers about Mechanical features (contact formulations, element
technology, boundary-condition semantics, scripting API objects) must come from
the shipped documentation for the release actually installed here, not from a
model's recollection. This gives an agent a way to look it up.

How it works
------------
`ansyshelp.ansys.com` has no published API, but its own frontend posts Solr
queries to an unauthenticated passthrough endpoint, and the search index stores
the full plain text of every page. So both search *and* full-text retrieval are
one HTTP call each, with no HTML scraping:

    search : POST /public/Account/Search/   form field `searchQuery`
             = "<core>/select?<solr params>"
    read   : the stored `body_en` field of the matching document
    source : GET /public/Views/Secured/<doc id>   (the rendered HTML page)

Verified working 2026-08-20 against core `ansysDoc_pub` (~337k documents,
releases 24.2 through 26.1).

Caveat: this endpoint is undocumented and unversioned. Ansys can change or
close it without notice. If it starts failing, fall back to the offline help
installed with Ansys in the Windows VM rather than guessing at answers.

Usage
-----
    ansys-docs.py search "contact formulation augmented lagrange"
    ansys-docs.py search "ExtAPI Named Selection" --manual "Scripting in Mechanical Guide"
    ansys-docs.py read corp/v251/en/wb_sim/ds_Contact_Settings.html
    ansys-docs.py manuals

Defaults to the release named by ANSYS_DOCS_VERSION (else 25.1) and to the
Mechanical Application product, so hits match the installed software. Use
`--product all` / `--all-versions` to widen the search.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://ansyshelp.ansys.com/public"
SEARCH_URL = f"{BASE}/Account/Search/"
CONTENT_URL = f"{BASE}/Views/Secured/"
CORE = "ansysDoc_pub"

# Akamai fronts this host and drops requests without a browser-like agent.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_VERSION = os.environ.get("ANSYS_DOCS_VERSION", "25.1")
DEFAULT_PRODUCT = "Mechanical Application"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        # python.org builds ship no CA bundle; macOS keeps one here.
        if os.path.exists("/etc/ssl/cert.pem"):
            return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
        return ssl.create_default_context()


_CTX = _ssl_context()


def _fetch(url: str, data: bytes | None = None) -> str:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=30, context=_CTX) as response:
        return response.read().decode("utf-8", "replace")


class AnsysHelpError(RuntimeError):
    """The endpoint did not return a Solr response."""


def solr(path_and_params: str, attempts: int = 4) -> dict:
    """Send a raw Solr request, e.g. 'select?q=...' or 'admin/luke?numTerms=0'.

    Roughly one in six calls comes back as a 404 HTML page instead of JSON
    (measured 2026-08-20), so identical requests are simply retried.
    """
    body = urllib.parse.urlencode({"searchQuery": f"{CORE}/{path_and_params}"}).encode()
    for attempt in range(attempts):
        payload = _fetch(SEARCH_URL, body)
        if payload.lstrip().startswith("{"):
            return json.loads(payload)
        if attempt < attempts - 1:
            time.sleep(0.5 * (attempt + 1))
    raise AnsysHelpError(
        "ansyshelp returned a non-Solr response " f"{attempts} times for: {path_and_params}"
    )


def _params(mapping: dict) -> str:
    parts = []
    for key, value in mapping.items():
        for item in value if isinstance(value, list) else [value]:
            parts.append(f"{key}={urllib.parse.quote(str(item))}")
    return "&".join(parts)


def _filters(product: str | None, version: str | None, manual: str | None, lang: str) -> list[str]:
    filters = [f"language:{lang}"]
    if product:
        filters.append(f'prodname_s:"{product}"')
    if version:
        filters.append(f'internal_version:"{version}"')
    if manual:
        filters.append(f'manualtitle:"{manual}"')
    return filters


def search(query, product=None, version=None, manual=None, lang="en", rows=8):
    data = solr(
        "select?"
        + _params(
            {
                "q": query,
                "defType": "edismax",
                "qf": "title_en^4 manualtitle^2 body_en",
                # sow=true restores classic per-term scoring across the mixed
                # field types here and measurably improves ranking. `mm` is
                # deliberately absent: any value above 1 returns zero hits on
                # this core, so it cannot be used to tighten multi-word queries.
                "sow": "true",
                "fq": _filters(product, version, manual, lang),
                "rows": rows,
                "fl": "id,title_en,manualtitle,prodnamefull,internal_version,physicstype",
                "sort": "score desc,internal_version desc",
                "hl": "true",
                "hl.fl": "body_en",
                "hl.fragsize": "240",
                "hl.snippets": "2",
            }
        )
    )
    highlights = data.get("highlighting", {})
    results = []
    for doc in data["response"]["docs"]:
        fragments = dict.fromkeys(highlights.get(doc["id"], {}).get("body_en", []))
        results.append(
            {
                "id": doc["id"],
                "url": CONTENT_URL + doc["id"],
                "title": doc.get("title_en", ""),
                "manual": doc.get("manualtitle", ""),
                "product": (doc.get("prodnamefull") or [""])[0],
                "version": (doc.get("internal_version") or [""])[0],
                "snippet": " … ".join(
                    re.sub(r"</?em>", "", fragment).strip() for fragment in fragments
                ),
            }
        )
    return data["response"]["numFound"], results


def _strip_html(markup: str) -> str:
    text = re.sub(r"(?s)<(script|style).*?</\1>", "", markup)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    import html as html_module

    return re.sub(r"[ \t]+", " ", html_module.unescape(text)).strip()


def read(doc_ids) -> list[dict]:
    """Return {id, title, text} per page, in the order asked for.

    Several pages come back in a single Solr call, because answering one
    question usually means reading a handful of related sections. Page text is
    taken from the index and only falls back to the rendered HTML if a document
    carries no stored body.
    """
    if isinstance(doc_ids, str):
        doc_ids = [doc_ids]
    wanted = [doc.replace(CONTENT_URL, "").split("?")[0].lstrip("/") for doc in doc_ids]

    clause = " OR ".join(f'id:"{doc_id}"' for doc_id in wanted)
    data = solr("select?" + _params({"q": clause, "rows": len(wanted), "fl": "id,title_en,body_en"}))
    indexed = {doc["id"]: doc for doc in data["response"]["docs"]}

    pages = []
    for doc_id in wanted:
        doc = indexed.get(doc_id, {})
        text = doc.get("body_en") or ""
        if isinstance(text, list):
            text = text[0] if text else ""
        if not text:
            try:
                text = _strip_html(_fetch(CONTENT_URL + doc_id))
            except urllib.error.HTTPError as error:
                text = f"[could not be read: HTTP {error.code}. Check the id from a search result.]"
        pages.append(
            {
                "id": doc_id,
                "title": doc.get("title_en", ""),
                "text": re.sub(r"[ \t]+", " ", text).strip(),
            }
        )
    return pages


def facets(field, product=None, version=None, lang="en", limit=60) -> dict:
    data = solr(
        "select?"
        + _params(
            {
                "q": "*:*",
                "rows": 0,
                "fq": _filters(product, version, None, lang),
                "facet": "true",
                "facet.field": field,
                "facet.limit": limit,
                "facet.mincount": 1,
            }
        )
    )
    values = data["facet_counts"]["facet_fields"][field]
    return dict(zip(values[0::2], values[1::2]))


def _resolve_scope(args):
    product = None if args.product == "all" else args.product
    version = None if args.all_versions else args.version
    return product, version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--product", default=DEFAULT_PRODUCT, help='product name, or "all"')
    parser.add_argument("--version", default=DEFAULT_VERSION, help="internal release, e.g. 25.1")
    parser.add_argument("--all-versions", action="store_true", help="do not filter by release")
    parser.add_argument("--lang", default="en")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="full-text search, prints ids to read")
    p_search.add_argument("query")
    p_search.add_argument("--manual", help='restrict to one manual, e.g. "Mechanical User\'s Guide"')
    p_search.add_argument("-n", "--rows", type=int, default=8)

    p_read = sub.add_parser("read", help="print one or more pages as plain text")
    p_read.add_argument("doc_ids", nargs="+", help="Solr ids or full ansyshelp URLs")
    p_read.add_argument("--max-chars", type=int, default=0, help="per page; 0 = whole page")

    sub.add_parser("manuals", help="list manuals available for the scope")
    sub.add_parser("products", help="list products available for the release")

    args = parser.parse_args()
    product, version = _resolve_scope(args)

    try:
        if args.command == "search":
            total, results = search(
                args.query, product, version, args.manual, args.lang, args.rows
            )
            scope = f"{product or 'all products'}, {version or 'all releases'}"
            print(f"{total} hits ({scope}), showing {len(results)}\n")
            for item in results:
                print(f"{item['title']}  [{item['manual']} {item['version']}]")
                print(f"  id:  {item['id']}")
                print(f"  url: {item['url']}")
                if item["snippet"]:
                    print(f"  …{item['snippet']}…")
                print()
            if not results:
                print("No hits. Widen with --product all or --all-versions.")

        elif args.command == "read":
            for index, page in enumerate(read(args.doc_ids)):
                if index:
                    print()
                print(f"=== {page['title'] or page['id']} ===")
                print(f"{CONTENT_URL}{page['id']}\n")
                print(page["text"][: args.max_chars] if args.max_chars else page["text"])

        elif args.command == "manuals":
            for name, count in sorted(
                facets("manualtitle", product, version, args.lang).items(),
                key=lambda kv: -kv[1],
            ):
                print(f"{count:6d}  {name}")

        elif args.command == "products":
            for name, count in sorted(
                facets("prodnamefull", None, version, args.lang, limit=300).items()
            ):
                print(f"{count:6d}  {name}")

    except (urllib.error.URLError, AnsysHelpError) as error:
        print(f"ansyshelp request failed: {error}", file=sys.stderr)
        print(
            "The endpoint is undocumented and may have changed. Use the offline "
            "help installed with Ansys instead of answering from memory.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
