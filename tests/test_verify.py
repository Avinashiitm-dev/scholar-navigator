from app.verify import quote_in_page

PAGE = """## Eligibility
Students must have **secured at least 50% marks** in the previous exam.
Family income should not exceed [Rs 2.5 lakh](https://x.gov.in) per annum."""


def test_exact_quote_passes():
    assert quote_in_page("Students must have secured at least 50% marks in the previous exam.", PAGE)


def test_markdown_noise_ignored():
    assert quote_in_page("Family income should not exceed Rs 2.5 lakh per annum.", PAGE)


def test_hallucinated_quote_fails():
    assert not quote_in_page("Family income should not exceed Rs 8 lakh per annum.", PAGE)


def test_too_short_quote_fails():
    assert not quote_in_page("50% marks", PAGE)
