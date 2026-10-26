"""HTML sanitizing, plain-text excerpts, share-URL cleaning and content hashing."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import lxml.html
import nh3

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "dd", "del", "details",
    "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "ins", "kbd", "li", "mark", "ol", "p", "picture", "pre", "q", "s", "small",
    "source", "span", "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th",
    "thead", "time", "tr", "u", "ul", "video", "audio",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "srcset", "alt", "title", "width", "height", "loading"},
    "source": {"src", "srcset", "type", "media"},
    "video": {"src", "poster", "controls", "width", "height"},
    "audio": {"src", "controls"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "time": {"datetime"},
    "abbr": {"title"},
    "ol": {"start"},
}

TRACKING_PARAMS = re.compile(
    r"^(utm_[a-z_]+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|_hsenc|_hsmi|igshid|"
    r"ref_src|ref_url|cmpid|ncid|sr_share|wt\.mc_id|yclid|oly_enc_id|oly_anon_id|vero_id|"
    r"__twitter_impression|guccounter|guce_referrer|guce_referrer_sig|soc_src|soc_trk)$",
    re.IGNORECASE,
)

BOILERPLATE = re.compile(
    r"(continue reading|read more|the post .{0,200} appeared first on .{0,120}|"
    r"\[(…|\.\.\.)\]|this article originally appeared.*$)",
    re.IGNORECASE | re.DOTALL,
)

EXCERPT_CHARS = 220
SUMMARY_MIN_CHARS = 120


def _absolutize(html: str, base_url: str | None) -> str:
    """Make relative links absolute and drop 1x1 tracking pixels before cleaning."""
    if not html.strip():
        return html
    try:
        frag = lxml.html.fragment_fromstring(html, create_parent="div")
    except (lxml.etree.ParserError, ValueError):
        return html
    for img in frag.iter("img"):
        w, h = img.get("width", ""), img.get("height", "")
        if w in {"0", "1"} or h in {"0", "1"}:
            img.drop_tree()
    if base_url:
        try:
            frag.make_links_absolute(base_url, resolve_base_href=False)
        except ValueError:
            pass
    for img in frag.iter("img"):
        # Many feeds lazy-load: copy data-src into src.
        if not img.get("src") and img.get("data-src"):
            img.set("src", img.get("data-src"))
        img.set("loading", "lazy")
    out = lxml.html.tostring(frag, encoding="unicode")
    # Strip the wrapper div we added.
    return out[len("<div>"):-len("</div>")] if out.startswith("<div>") else out


def sanitize(html: str | None, base_url: str | None = None) -> str:
    if not html:
        return ""
    return nh3.clean(
        _absolutize(html, base_url),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )


def text_of(html: str | None) -> str:
    if not html or not html.strip():
        return ""
    try:
        doc = lxml.html.fragment_fromstring(html, create_parent="div")
        for bad in doc.xpath("//script|//style|//figcaption"):
            bad.drop_tree()
        text = doc.text_content()
    except (lxml.etree.ParserError, ValueError):
        text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _clip(text: str, limit: int = EXCERPT_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-– ")
    return cut + "…"


def make_excerpt(summary_html: str | None, content_html: str | None, title: str | None = None) -> str:
    """Prefer the feed summary when it has real text; otherwise use the article body (F-17)."""
    def clean(t: str) -> str:
        t = BOILERPLATE.sub(" ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if title and t.lower().startswith(title.lower()):
            t = t[len(title):].lstrip(" :—-–")
        return t

    summary = clean(text_of(summary_html))
    if len(summary) >= SUMMARY_MIN_CHARS:
        return _clip(summary)
    body = clean(text_of(content_html))
    if body:
        return _clip(body)
    return _clip(summary)


def first_image(html: str | None) -> str | None:
    if not html:
        return None
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    if m and m.group(1).startswith(("http://", "https://")):
        return m.group(1)
    return None


def clean_url(url: str | None) -> str | None:
    """The link we hand out when sharing: tracking parameters stripped (F-25)."""
    if not url:
        return url
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url
    if parts.scheme not in {"http", "https"}:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    fragment = "" if parts.fragment.startswith(("xtor=", "utm_", "ref=")) else parts.fragment
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), fragment))


def resolve(base: str | None, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base or "", href)


def content_hash(title: str | None, html: str | None) -> str:
    text = (title or "") + "\n" + text_of(html)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
