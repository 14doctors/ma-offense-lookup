"""Generate demo House/Senate document pairs for each comparison mode.

Run from the pasteup-suite directory:  python samples/make_samples.py
Writes six .docx files into samples/.
"""

import os

from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))

STANDARD_HOUSE = """An Act relative to municipal road safety.

SECTION 1. Section 1 of chapter 90 of the General Laws, as appearing in the 2022 Official Edition, is hereby amended by inserting after the definition of "Low-speed vehicle" the following definition:- "Municipal road safety plan", a plan adopted by a city or town under section 35 of chapter 90I.

SECTION 2. Chapter 90 of the General Laws is hereby amended by inserting after section 17C the following section:- Section 17D. A city or town that has adopted a municipal road safety plan may establish a speed limit of 20 miles per hour on any way within a designated safety zone.

SECTION 3. Section 18B of said chapter 90 is hereby amended by striking out the second paragraph and inserting in place thereof the following paragraph:- The department shall promulgate regulations to implement this section not later than 180 days after the effective date of this act.

SECTION 4. This act shall take effect on January 1, 2027."""

STANDARD_SENATE = """An Act relative to municipal road safety.

SECTION 1. Section 1 of chapter 90 of the General Laws, as appearing in the 2022 Official Edition, is hereby amended by inserting after the definition of "Low-speed vehicle" the following definition:- "Municipal road safety plan", a plan adopted by a city or town under section 35 of chapter 90I and approved by the department.

SECTION 2. Chapter 90 of the General Laws is hereby amended by inserting after section 17C the following section:- Section 17D. A city or town that has adopted a municipal road safety plan may establish a speed limit of 25 miles per hour on any way within a designated safety zone.

SECTION 3. Notwithstanding any general or special law to the contrary, the registrar of motor vehicles shall conduct a public awareness campaign concerning safety zones established under section 17D of chapter 90 of the General Laws.

SECTION 4. Section 18B of said chapter 90 is hereby amended by striking out the second paragraph and inserting in place thereof the following paragraph:- The department shall promulgate regulations to implement this section not later than 180 days after the effective date of this act.

SECTION 5. This act shall take effect on July 1, 2027."""

BOND_HOUSE = """An Act financing improvements to municipal roads and bridges.

SECTION 1. To provide for a program of improvements to municipal roads and bridges, the sums set forth in sections 2 and 2A are hereby made available, subject to the laws regulating the disbursement of public funds.

SECTION 2. EXECUTIVE OFFICE FOR ADMINISTRATION AND FINANCE

1599-2026 For a program of grants to cities and towns for the construction and reconstruction of municipal ways; provided, that grants shall be distributed in accordance with section 34 of chapter 90 of the General Laws ................ $200,000,000

1599-2027 For the municipal small bridge program; provided, that funds may be expended for design, construction and repair of bridges on municipal ways ................ $70,000,000

SECTION 2A. MASSACHUSETTS DEPARTMENT OF TRANSPORTATION

6121-2610 For the design, construction and repair of pavement and surface conditions on state and municipal roadways ................ $25,000,000

SECTION 3. The secretary of transportation shall file an annual report with the house and senate committees on ways and means detailing all expenditures made pursuant to this act.

SECTION 4. This act shall take effect upon its passage."""

BOND_SENATE = """An Act financing improvements to municipal roads and bridges.

SECTION 1. To provide for a program of improvements to municipal roads and bridges, the sums set forth in sections 2 and 2A are hereby made available, subject to the laws regulating the disbursement of public funds.

SECTION 2. EXECUTIVE OFFICE FOR ADMINISTRATION AND FINANCE

1599-2026 For a program of grants to cities and towns for the construction and reconstruction of municipal ways; provided, that grants shall be distributed in accordance with section 34 of chapter 90 of the General Laws; provided further, that not less than $10,000,000 shall be expended for rural roadway apportionment ................ $250,000,000

1599-2027 For the municipal small bridge program; provided, that funds may be expended for design, construction and repair of bridges on municipal ways ................ $70,000,000

SECTION 2A. MASSACHUSETTS DEPARTMENT OF TRANSPORTATION

6121-2610 For the design, construction and repair of pavement and surface conditions on state and municipal roadways ................ $25,000,000

6121-2620 For a program of electric vehicle charging infrastructure on municipal ways ................ $15,000,000

SECTION 3. The secretary of transportation shall file a quarterly report with the house and senate committees on ways and means and the joint committee on transportation detailing all expenditures made pursuant to this act.

SECTION 4. This act shall take effect upon its passage."""

CHARTER_HOUSE = """An Act establishing a charter for the town of Exampleton.

ARTICLE I - INCORPORATION AND POWERS

SECTION 1. The inhabitants of the town of Exampleton shall continue to be a body corporate and politic under the name "Town of Exampleton".

SECTION 2. The town shall have all powers possible for a town to have under the constitution and laws of the commonwealth.

ARTICLE II - LEGISLATIVE BRANCH

SECTION 1. The legislative powers of the town shall be exercised by a town council consisting of 9 members.

SECTION 2. Town councillors shall serve terms of 2 years, beginning on the first Monday of January following their election.

ARTICLE III - EXECUTIVE BRANCH

SECTION 1. The chief executive officer of the town shall be a town manager appointed by the town council."""

CHARTER_SENATE = """An Act establishing a charter for the town of Exampleton.

ARTICLE I - INCORPORATION AND POWERS

SECTION 1. The inhabitants of the town of Exampleton shall continue to be a body corporate and politic under the name "Town of Exampleton".

SECTION 2. The town shall have all powers possible for a town to have under the constitution and laws of the commonwealth.

ARTICLE II - LEGISLATIVE BRANCH

SECTION 1. The legislative powers of the town shall be exercised by a town council consisting of 11 members, 2 of whom shall be elected at large.

SECTION 2. Town councillors shall serve terms of 4 years, beginning on the first Monday of January following their election.

SECTION 3. The town council shall annually elect a president from among its members.

ARTICLE III - EXECUTIVE BRANCH

SECTION 1. The chief executive officer of the town shall be a town manager appointed by the town council."""


def write_docx(name: str, text: str) -> None:
    doc = Document()
    for para in text.split("\n\n"):
        doc.add_paragraph(para)
    path = os.path.join(HERE, name)
    doc.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    write_docx("standard-house.docx", STANDARD_HOUSE)
    write_docx("standard-senate.docx", STANDARD_SENATE)
    write_docx("bond-house.docx", BOND_HOUSE)
    write_docx("bond-senate.docx", BOND_SENATE)
    write_docx("charter-house.docx", CHARTER_HOUSE)
    write_docx("charter-senate.docx", CHARTER_SENATE)
