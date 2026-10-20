"""Generates the sample handbook PDF used in the README and for trying DocMind out.

Run from the backend folder:  uv run python ../samples/make_samples.py
"""

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tests.pdf_factory import make_pdf  # noqa: E402

HANDBOOK = {
    "Welcome to Kestrel Labs": [
        "This handbook explains how we work, what you can expect from Kestrel Labs, and what we expect "
        "from you. It applies to all full-time and part-time employees. If something here conflicts with "
        "your employment contract, the contract wins.",
        "Questions about any policy go to the People team at people@kestrel.example. Policies are reviewed "
        "every January and the current version is always the one on the intranet.",
    ],
    "Working hours and remote work": [
        "Our core hours are 11:00 to 15:00 in your local time zone. Outside core hours you can arrange your "
        "day as you like, as long as your team knows when to reach you.",
        "Employees may work remotely up to three days per week. Remote days must be agreed with your manager "
        "at least one week in advance and recorded in the team calendar.",
        "Employees who live more than 80 kilometres from an office can apply to work fully remotely. "
        "Fully remote employees travel to an office for a team week once every quarter, and Kestrel Labs "
        "pays for the travel.",
    ],
    "Leave": [
        "Full-time employees receive 24 days of paid annual leave per year, plus public holidays. Part-time "
        "employees receive leave in proportion to their contracted hours.",
        "Up to five unused days can be carried over into the next year. Carried-over days must be used by "
        "31 March, after which they expire.",
        "Sick leave is separate from annual leave. Tell your manager before 10:00 on the first day of "
        "illness. A doctor's note is needed for absences longer than five working days.",
        "Parents receive 20 weeks of fully paid parental leave, which can be taken at any time in the first "
        "year after the birth or adoption of a child.",
    ],
    "Equipment and expenses": [
        "Every employee receives a laptop and a home-office budget of 600 dollars, which can be spent on a "
        "desk, chair, monitor or headset in the first three months of employment.",
        "Submit expense claims with a receipt in the finance portal within 30 days of the purchase. Claims "
        "older than 90 days cannot be reimbursed.",
        "Any single purchase above 500 dollars, including travel, needs approval from your department head "
        "before you pay. Book flights in economy class for trips shorter than six hours.",
    ],
    "Learning and development": [
        "Each employee has a yearly learning budget of 1,500 dollars for courses, books and conferences. "
        "Unused budget does not carry over to the next year.",
        "You can spend up to four working days per year at conferences or training without using annual "
        "leave. Agree the dates with your manager at least two weeks before.",
        "After two years at Kestrel Labs you can apply for a paid sabbatical of up to four weeks to work on "
        "a project that develops your skills.",
    ],
}


def build() -> bytes:
    pages = []
    for title, paragraphs in HANDBOOK.items():
        lines = [title, ""]
        for paragraph in paragraphs:
            lines.extend(textwrap.wrap(paragraph, width=88))
            lines.append("")
        pages.append(lines)
    return make_pdf(pages)


if __name__ == "__main__":
    out = Path(__file__).parent / "kestrel-employee-handbook.pdf"
    out.write_bytes(build())
    print(f"Wrote {out}")
