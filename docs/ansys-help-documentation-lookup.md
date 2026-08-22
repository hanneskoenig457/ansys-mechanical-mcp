# Documentation lookup against Ansys Help

`scripts/ansys-docs.py` lets an agent search and read the official Ansys
product documentation from the command line, so answers about Mechanical
behavior come from the shipped documentation for the installed release instead
of from a model's recollection. `skills/ansys-mechanical/SKILL.md` makes that
lookup mandatory for feature and API questions.

## What it talks to

Ansys publishes no documentation API. The Ansys Help frontend, however, posts
Solr queries to an unauthenticated passthrough endpoint, and the search index
stores the full plain text of every page. Both facts were verified live on
2026-08-20.

| Purpose | Request |
| --- | --- |
| Search | `POST https://ansyshelp.ansys.com/public/Account/Search/`, form field `searchQuery` = `ansysDoc_pub/select?<solr params>` |
| Page text | the stored `body_en` field of the matching document |
| Rendered page | `GET https://ansyshelp.ansys.com/public/Views/Secured/<doc id>` |

The endpoint passes arbitrary Solr syntax through, including `fq`, `facet`,
`hl` and `admin/luke`. The core name (`ansysDoc_pub` for the public site) comes
from `getCoreName()` in `/public/Views/Secured/css/ansys_doc_global.js`; the
request shape is in `css/ansys_search.js`.

No login or token is involved. The pages themselves are public; the login
wrapper and the iframe are client-side only, so `iframe_check()` never runs for
a non-browser client.

## Index shape

- ~337,000 documents, releases 24.2 through 26.1, 82 products at 25.1.
- Mechanical Application 25.1 holds 2,609 pages, including the Mechanical
  User's Guide (1,186), Mechanical Technology Showcase (388), Scripting in
  Mechanical Guide (235) and Mechanical Object Reference (226).
- Mechanical APDL is indexed as a **separate product**.
- Fields: `id, filename, title_en, body_en, manualtitle, book_id, prodnamefull,
  prodname_s, internal_version, language, physicstype, pub_desc_en,
  help_format, item_order, date`.
- Facet on `prodnamefull`. `prodname_s` is tokenized, so it filters correctly
  in `fq` but returns word fragments when faceted.
- `id` doubles as the path of the rendered page, e.g.
  `corp/v251/en/wb_sim/ds_contact_theory.html`.

## Endpoint behavior worth knowing

- **It is flaky.** Roughly one call in six returns a 404 HTML page instead of
  JSON. `solr()` retries identical requests up to four times with a short
  backoff; anything that talks to this endpoint must do the same.
- **`mm` is unusable.** Any minimum-match value above 1 returns zero hits, even
  for a single-field query whose terms all occur in known documents. Multi-word
  queries therefore cannot be tightened that way.
- **`sow=true` improves ranking** across the mixed field types in `qf`, and is
  set by default. A `pf` phrase boost was tested and rejected: it helped no
  query and demoted the correct hit for others.
- Akamai fronts the host and drops requests without a browser-like
  `User-Agent`.
- **Relevance is mediocre and field weighting does not fix it.** With the
  default `qf` (`title_en^4 manualtitle^2 body_en`), `contact formulation`
  ranks an Explicit Dynamics page above `9.6.2. Contact Formulation Theory`;
  a body-weighted `qf` corrects that query but breaks meshing queries, so the
  title-weighted default stands. Restricting to one manual is by far the
  stronger lever and is what the skill instructs agents to do.

## If it breaks

The endpoint is undocumented and unversioned, so Ansys can change or close it
without notice. The script then exits non-zero with a message pointing at the
fallback: the offline help installed with Ansys in the Windows VM. The rule in
the skill is that an unavailable lookup must be reported as unavailable — it is
never grounds for answering from memory.

Ansys' own "API Docs" navigation link (`developer.ansys.com/docs`) now
redirects to `developer.synopsys.com` and does not offer a documentation API.
