import pytest

from jobsmith.ats.workday import date_digits


@pytest.mark.parametrize(
    ("value", "sections", "digits"),
    [
        ("2022", 1, ["2022"]),
        ("3/2022", 2, ["03", "2022"]),
        ("12/2022", 2, ["12", "2022"]),
        ("3/5/2026", 3, ["03", "05", "2026"]),
        ("10/31/2026", 3, ["10", "31", "2026"]),
    ],
)
def test_date_digits_pads_months_and_days(value, sections, digits):
    assert date_digits(value, sections) == digits


@pytest.mark.parametrize(
    ("value", "sections"),
    [
        ("3/2022", 3),  # too few parts
        ("3/5/2026", 2),  # too many parts
        ("2022", 4),  # no date has four sections
        ("13/2022", 2),  # month too big
        ("0/2022", 2),  # month too small
        ("1/32/2026", 3),  # day too big
        ("22", 1),  # year not four digits
        ("20222", 1),
        ("003/2022", 2),  # month wider than its section
        ("Mar/2022", 2),
        ("2022-03", 1),
        ("", 1),
        ("١٢/2022", 2),  # non-ASCII digits
    ],
)
def test_date_digits_refuses_what_does_not_fit(value, sections):
    with pytest.raises(ValueError):
        date_digits(value, sections)
