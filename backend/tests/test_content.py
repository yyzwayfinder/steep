from steep.content import clean_url, make_excerpt, sanitize


def test_sanitize_strips_scripts_pixels_and_absolutizes():
    html = '<p onclick="x()">Hi <a href="/a">link</a></p><script>alert(1)</script>' \
           '<img src="/i.jpg"><img src="https://t.example/p.gif" width="1" height="1">'
    out = sanitize(html, "https://site.example/post/1")
    assert "script" not in out and "onclick" not in out
    assert 'href="https://site.example/a"' in out
    assert 'src="https://site.example/i.jpg"' in out
    assert "p.gif" not in out
    assert 'rel="noopener noreferrer nofollow"' in out


def test_sanitize_drops_javascript_urls():
    assert "javascript" not in sanitize('<a href="javascript:alert(1)">x</a>')


def test_excerpt_prefers_long_summary():
    summary = "<p>" + "A real summary sentence. " * 8 + "</p>"
    assert make_excerpt(summary, "<p>Body text</p>").startswith("A real summary")


def test_excerpt_falls_back_to_body_when_summary_is_teaser():
    body = "<p>" + "The body has the real words. " * 20 + "</p>"
    out = make_excerpt("<p>Short… Continue reading</p>", body)
    assert out.startswith("The body has")
    assert len(out) <= 225 and out.endswith("…")


def test_excerpt_strips_feed_boilerplate():
    summary = "<p>" + "Words here. " * 15 + "The post Hello appeared first on Example Blog.</p>"
    assert "appeared first" not in make_excerpt(summary, None)


def test_clean_url_strips_tracking_but_keeps_real_params():
    url = "https://ex.example/p?id=7&utm_source=rss&utm_medium=feed&fbclid=abc#xtor=RSS-1"
    assert clean_url(url) == "https://ex.example/p?id=7"
    assert clean_url("https://ex.example/p#section-2") == "https://ex.example/p#section-2"
