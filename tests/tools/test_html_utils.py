from tools.html_utils import extract_text

def test_extract_text_removes_tags():
    html = "<html><body><p>Hello</p><script>bad</script></body></html>"
    result = extract_text(html)
    assert "Hello" in result
    assert "bad" not in result

def test_extract_text_truncates():
    html = "<p>" + "x" * 10000 + "</p>"
    result = extract_text(html, max_chars=100)
    assert len(result) <= 100

def test_extract_text_empty_input():
    assert extract_text("") == ""
