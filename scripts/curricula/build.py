"""Write program packages for AUIB's majors from the released curriculum documents.

The documents go in ``sis_data/released doc`` (see docs/data-pipeline.md, "Programs from the released
curricula"). From the repository root:

    python scripts/curricula/build.py            # extract, then check every program
    python scripts/curricula/build.py --write    # also write data/programs/<id>/ and the added courses

Running it again on the same documents writes the same files. Each choice made where a document is
unclear or disagrees with SIS is commented where it is made, and listed in docs/data-pipeline.md.
"""
from __future__ import annotations

import re
import sys

from common import (
    ADDED,
    CLA_HUMANITIES,
    DESCRIPTIONS,
    CLA_NATURAL,
    CLA_SOCIAL,
    G,
    Program,
    SUMMER_ONLY,
    add_course,
    branch,
    check,
    cla,
    cla_pool,
    free_pool,
    from_document,
    known,
    load_descriptions,
    leaf,
    pick,
    units_of,
    write_catalog,
    write_program,
)

import descriptions
import extract
from extract import RAW, TEXT

CAS_DOC = "the College of Arts and Sciences degree plans (\"CAS Programs Degree Plans 2023\")"
CIS_DOC = "the College of International Studies curriculum (Fall 2023)"
COB_DOC = "the College of Business degree plans (November 2024)"
OVS_DOC = "the College of Healthcare Technology curriculum (Optometry and Vision Sciences, Appendices I and II)"
RAD_DOC = "the College of Healthcare Technology curriculum (Radiologic Sciences, Appendices III and IV)"
BDT_DOC = "the College of Healthcare Technology curriculum (Dental Technology, Appendices V and VI)"
ANT_DOC = "the College of Healthcare Technology curriculum (Anesthesia Technology, Appendices VII and VIII)"
HCT_DOC = "the College of Healthcare Technology curricula"
COD_DOC = "the College of Dentistry academic curriculum (BDS)"
COP_DOC = "the College of Pharmacy academic curriculum (BPharm)"


def listed_only(code: str, title: str, units: float, document: str) -> None:
    add_course(code, title, units, f"{title}. Listed in {document}, which gives no description.", document)


def raw_snippet(file_part: str, start: str, length: int = 900) -> str:
    """Text after ``start`` in a raw PDF dump, up to the next course heading."""
    path = next(RAW.glob(f"*{file_part}*.txt"))
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace"))
    at = text.index(start) + len(start)
    body = text[at : at + length]
    stop = re.search(r"\s[A-Z]{3} \d{3}L?\s?[-–�:]", body)
    return body[: stop.start()] if stop else body


# =============================================================================================
# Courses the documents require that the SIS catalog lacks
# =============================================================================================


def add_missing_courses() -> None:
    # Arts and Sciences, International Studies, Business.
    listed_only("BIO 420", "Microbiology", 4, CAS_DOC)
    listed_only("POL 404", "Professional Development Seminar", 3, CIS_DOC)
    listed_only("POL 405", "Leadership Management Seminar", 3, CIS_DOC)
    listed_only("HUM 210", "Introduction to Human Geography", 3, f"{CIS_DOC} and {COB_DOC}")
    listed_only("ACC 201", "Introduction to Financial Accounting", 3, COB_DOC)
    listed_only("ACC 202", "Managerial Accounting", 3, COB_DOC)
    listed_only("ACC 301", "Intermediate Accounting I", 3, COB_DOC)

    # College of Healthcare Technology: shared courses.
    from_document("COP", "HCT 101", HCT_DOC)
    from_document("RAD", "HCT 207", RAD_DOC, title="Introduction to Radiation Protection")
    from_document("RAD", "HCT 209", RAD_DOC)
    from_document("OVS", "HCT 210", OVS_DOC, description=raw_snippet("Optometry_and_Vision", "HCT 210 - Basic Life Support (0 Credit)"))
    add_course("HCT 331", "Critical Appraisal", 1, "Critical Appraisal" + raw_snippet("Radiologic_and_Sonal", "HCT 331 � Critical Appraisal"), RAD_DOC)
    for code in ("HCT 480", "HCT 481", "HCT 483"):
        from_document("RAD", code, HCT_DOC)
    from_document("RAD", "HCT 482", HCT_DOC)
    listed_only("HCT 485", "Biostatistics and Epidemiology", 3, OVS_DOC)
    from_document("OVS", "HCT 486", OVS_DOC, description=raw_snippet("Optometry_and_Vision", "HCT 486 - Leadership in Vision Sciences and Optometry (3 Credits)"))

    # Optometry and Vision Sciences. The descriptions print OVS 277 as OVS 227; the planning guide and
    # the prerequisites of later courses use OVS 277.
    for code in [
        "OVS 101", "OVS 110", "OVS 115", "OVS 115L", "OVS 210", "OVS 210L", "OVS 211", "OVS 215", "OVS 215L",
        "OVS 220", "OVS 220L", "OVS 251", "OVS 255", "OVS 261", "OVS 310", "OVS 312", "OVS 315L", "OVS 330L",
        "OVS 340", "OVS 380", "OVS 380L", "OVS 385", "OVS 388", "OVS 390", "OVS 470", "OVS 495",
    ]:
        from_document("OVS", code, OVS_DOC)
    from_document("OVS", "OVS 277", OVS_DOC, found_as="OVS 227")
    # OVS 280's description runs on from OVS 227L's in the document (its heading has no credits).
    lab, _, neuro = DESCRIPTIONS["OVS"]["OVS 227L"]["text"].partition("OVS 280 Neuroanatomy and Neuro-ophthalmology")
    from_document("OVS", "OVS 277L", OVS_DOC, found_as="OVS 227L", description=lab)
    add_course("OVS 280", "Neuroanatomy and Neuro-ophthalmology", 3, neuro, OVS_DOC)
    listed_only("OVS 499", "Practicum III", 3, OVS_DOC)

    # Radiologic Sciences: the descriptions give each lecture with its lab (4 credits); the program list
    # splits them into a 3-credit lecture and a 1-credit lab, as here.
    for code in [
        "RAD 101", "RAD 201", "RAD 210", "RAD 301", "RAD 310", "RAD 315", "RAD 362", "RAD 365", "RAD 410",
        "RAD 420", "RAD 460", "RAD 480", "RAD 450", "RAD 490",
    ]:
        from_document("RAD", code, RAD_DOC)
    for lecture, title in [
        ("RAD 305", "Imaging Procedures I"),
        ("RAD 355", "Imaging Procedures II"),
        ("RAD 370", "Computer Applications in Medical Imaging"),
        ("RAD 405", "Imaging Procedures III"),
    ]:
        from_document("RAD", lecture, RAD_DOC, title=title, units=3)
        add_course(
            f"{lecture}L",
            f"{title} Lab",
            1,
            f"The laboratory part of {lecture} {title}. Prerequisite or corequisite: {lecture}.",
            RAD_DOC,
        )
    add_course(
        "RAD 390",
        "Practicum I: Internship in Clinical Imaging",
        2,
        "Practicum I: Internship in Clinical Imaging"
        + raw_snippet("Radiologic_and_Sonal", "Practicum I: Internship in Clinical Imaging (3 Credits)"),
        RAD_DOC,
    )

    # Dental Technology (and the Dentistry courses it shares).
    for code in [
        "BDT 210", "BDT 210L", "BDT 211", "BDT 320L", "BDT 321L", "BDT 330", "BDT 330L", "BDT 331L", "BDT 340",
        "BDT 350", "BDT 360", "BDT 370", "BDT 370L", "BDT 380", "BDT 380L", "BDT 430L", "BDT 460L", "BDT 461L",
        "BDT 470L", "BDT 471L", "BDT 490L", "BDT 492L", "BDT 496", "BDT 498",
    ]:
        from_document("BDT", code, BDT_DOC)
    listed_only("BDT 320", "Fixed Prosthodontics I", 3, BDT_DOC)
    add_course(
        "BDT 420L",
        "Fixed Prosthodontics Lab III",
        1,
        raw_snippet("Appendix_VI_for_Dental", "BDT 420L Fixed Prosthodontics lab III", 700),
        BDT_DOC,
    )

    # Anesthesia Technology. The descriptions call ANT 295 and ANT 399 both "Practicum II"; the program
    # list and the year plan call them Practicum I and II, then ANT 490, 495 and 496 Practicum III to V.
    for code in [
        "ANT 101", "ANT 240", "ANT 240L", "ANT 245", "ANT 320", "ANT 320L", "ANT 330", "ANT 340", "ANT 340L",
        "ANT 343L", "ANT 350", "ANT 360", "ANT 370", "ANT 390", "ANT 410", "ANT 420", "ANT 430L", "ANT 455",
        "ANT 460", "ANT 460L",
    ]:
        from_document("ANT", code, ANT_DOC)
    for code, title in [
        ("ANT 295", "Practicum I"),
        ("ANT 399", "Practicum II"),
        ("ANT 490", "Practicum III"),
        ("ANT 495", "Practicum IV"),
        ("ANT 496", "Practicum V"),
    ]:
        from_document("ANT", code, ANT_DOC, title=title)

    # Dentistry: every BDS course, from the curriculum's descriptions.
    for code in sorted(DESCRIPTIONS["COD"]):
        if code.startswith("BDS "):
            from_document("COD", code, COD_DOC)

    # Codes the documents misprint inside descriptions, which the prerequisite parser would read.
    for code, course in ADDED.items():
        text = course["description"]
        if code.startswith("OVS"):
            text = text.replace("OVS 227", "OVS 277").replace("OVS210", "OVS 210")
        if code.startswith(("RAD", "HCT 20", "HCT 33")):
            text = text.replace("PHY 241", "PHY 107")
        course["description"] = text


# =============================================================================================
# College of Arts and Sciences
# =============================================================================================


def free(prefix: str, count: int, min_level: int = 100) -> G:
    label = "Free electives" + (f" ({min_level}- or {min_level + 100}-level)" if min_level > 100 else "")
    return G(f"{prefix} - Free electives", label, 3.0 * count, courses=free_pool(min_level), role="free_elective")


def biology() -> Program:
    p = "Biology"
    core = branch(
        f"{p} - Major core",
        "Major core",
        [
            leaf(
                f"{p} - Chemistry and physics",
                "Chemistry and physics",
                ["CHE 101", "CHE 101L", "CHE 102", "CHE 102L", "PHY 103", "PHY 103L", "PHY 104", "PHY 104L",
                 "CHE 211", "CHE 211L", "CHE 212", "CHE 212L"],
            ),
            leaf(
                f"{p} - Biology courses",
                "Biology courses",
                ["BIO 211", "BIO 211L", "BIO 212", "BIO 212L", "BIO 210", "BIO 221", "BIO 225", "BIO 420", "BIO 421",
                 "BIO 485", "BIO 422", "BIO 441", "BIO 490"],
            ),
        ],
    )
    electives = pick(
        ["BIO 215", "BIO 220", "BIO 222", "BIO 321", "BIO 322", "BIO 432", "BIO 451", "BIO 452", "BIO 460", "BIO 480"],
        3, f"{p} - Major electives", "Biology electives", role="major_elective",
    )
    root = branch(
        "BS Biology", "Biology",
        [core, cla(p, math=["MAT 102"], natural_required=["BIO 101"]), electives, free(p, 2)],
    )
    SUMMER_ONLY.add("BIO 485")
    return Program(
        "casc-biology", "Biology", 120,
        f"Suggested study plan \"Bachelor of Science in Biology\" in {CAS_DOC}",
        None, True, root,
    )


def chemistry() -> Program:
    p = "Chemistry"
    core = branch(
        f"{p} - Major core",
        "Major core",
        [
            leaf(
                f"{p} - Chemistry courses",
                "Chemistry courses",
                ["CHE 101", "CHE 101L", "CHE 102", "CHE 102L", "CHE 211", "CHE 211L", "CHE 212", "CHE 212L",
                 "CHE 221", "CHE 221L", "CHE 241", "CHE 241L", "CHE 311", "CHE 341", "CHE 341L", "CHE 225",
                 "CHE 225L", "CHE 331", "CHE 352", "CHE 322", "CHE 322L", "CHE 480", "CHE 490"],
            ),
            leaf(f"{p} - Mathematics and physics", "Mathematics and physics", ["MAT 112", "PHY 101", "PHY 101L"]),
        ],
    )
    electives = pick(
        ["CHE 412", "CHE 420", "CHE 429", "CHE 451", "CHE 453", "CHE 454"],
        4, f"{p} - Major electives", "Chemistry electives", role="major_elective",
    )
    root = branch("BS Chemistry", "Chemistry", [core, cla(p, math=["MAT 111"]), electives, free(p, 3)])
    SUMMER_ONLY.add("CHE 352")
    return Program(
        "casc-chemistry", "Chemistry", 120,
        f"Suggested study plan \"Bachelor of Science in Chemistry\" in {CAS_DOC}",
        None, True, root,
    )


def physics() -> Program:
    p = "Physics"
    core = branch(
        f"{p} - Major core",
        "Major core",
        [
            leaf(
                f"{p} - Physics courses",
                "Physics courses",
                ["PHY 101", "PHY 101L", "PHY 102", "PHY 102L", "PHY 211", "PHY 211L", "PHY 212", "PHY 221",
                 "PHY 241", "PHY 331", "PHY 350", "PHY 351", "PHY 352", "PHY 320L", "PHY 389", "PHY 360", "PHY 499"],
            ),
            leaf(
                f"{p} - Mathematics and chemistry",
                "Mathematics and chemistry",
                ["MAT 112", "MAT 113", "MAT 130", "MAT 220", "CHE 101", "CHE 101L"],
            ),
        ],
    )
    electives = pick(
        ["PHY 210", "PHY 231", "PHY 361", "PHY 420", "PHY 441", "PHY 452", "PHY 470"],
        4, f"{p} - Major electives", "Physics electives", role="major_elective",
    )
    root = branch("BS Physics", "Physics", [core, cla(p, math=["MAT 111"]), electives, free(p, 2)])
    SUMMER_ONLY.add("PHY 389")
    return Program(
        "casc-physics", "Physics", 120,
        f"Suggested study plan \"Bachelor of Science in Physics\" in {CAS_DOC}",
        None, True, root,
    )


def english() -> Program:
    p = "English Literature"
    core = leaf(
        f"{p} - Major core courses",
        "Major core courses",
        ["LIT 201", "LIT 220", "LIT 221", "ENL 212", "LIT 240", "LIT 241", "LIT 320", "LIT 330", "ENL 330",
         "LIT 333", "ENL 321", "LIT 389", "LIT 390", "LIT 410", "LIT 421", "LIT 498", "LIT 451", "LIT 499"],
    )
    electives = pick(
        ["LIT 242", "LIT 315", "LIT 332", "LIT 337", "LIT 431", "LIT 433", "LIT 441", "LIT 450"],
        6, f"{p} - Literature electives", "Literature electives", role="major_elective",
    )
    root = branch(
        "BA English Literature", "English Literature",
        [core, cla(p, humanities_required=["LIT 101"], exclude={"ENL 212"}), electives, free(p, 2)],
    )
    SUMMER_ONLY.add("LIT 390")
    return Program(
        "casc-english-literature", "English Literature", 120,
        f"Suggested study plan \"Bachelor of Arts in English Literature\" in {CAS_DOC}",
        None, True, root,
    )


def psychology() -> Program:
    p = "Psychology major"
    core = leaf(
        f"{p} - Major core courses",
        "Major core courses",
        ["PSY 210", "PSY 220", "PSY 230", "PSY 240", "PSY 270", "PSY 320", "PSY 370", "PSY 310", "PSY 330",
         "PSY 340", "PSY 390", "PSY 480", "PSY 450", "PSY 490", "PSY 470", "PSY 491"],
    )
    electives = pick(
        ["PSY 226", "PSY 324", "PSY 332", "PSY 334", "PSY 345", "PSY 350", "PSY 360", "PSY 420", "PSY 431",
         "PSY 440", "PSY 453", "PSY 455", "PSY 460", "PSY 465", "PSY 482"],
        8, f"{p} - Psychology electives", "Psychology electives", role="major_elective",
    )
    root = branch(
        "BA Psychology", "Psychology",
        [core, cla(p, social_required=["PSY 101"], exclude={"PSY 334"}), electives, free(p, 2)],
    )
    SUMMER_ONLY.add("PSY 480")
    return Program(
        "casc-psychology", "Psychology", 120,
        f"Suggested study plan \"Bachelor of Arts in Psychology\" in {CAS_DOC}",
        None, True, root,
    )


# =============================================================================================
# College of International Studies
# =============================================================================================

IR_CORE = [
    "POL 101", "POL 111", "POL 112", "POL 140", "POL 142", "POL 191", "POL 214", "POL 219", "POL 221", "POL 230",
    "POL 240", "POL 311", "POL 312", "POL 340", "POL 350", "POL 392", "POL 404", "POL 405", "POL 491", "POL 492",
]
# The document's electives that are in SIS (POL 255 Iraqi Politics is POL 252 there, and POL 273/PSY 272
# Political Psychology is POL 270), then the POL courses SIS adds; the document says the list will grow.
IR_ELECTIVES = [
    "POL 125", "POL 252", "POL 262", "POL 263", "POL 265", "POL 266", "POL 267", "POL 268", "POL 270", "POL 285",
    "POL 307", "POL 113", "POL 200", "POL 253", "POL 342", "POL 360", "POL 390", "POL 391",
]


def international_relations() -> Program:
    p = "IR&SS"
    core = leaf(f"{p} - Major core courses", "Major core courses", IR_CORE)
    electives = pick(IR_ELECTIVES, 6, f"{p} - Major electives", "IR&SS electives", role="major_elective")
    root = branch(
        "BA International Relations and Security Studies", "International Relations and Security Studies",
        [
            core,
            cla(p, humanities_history=2, natural_required=["GEO 101"], exclude=set(IR_CORE) | {"POL 125"}),
            electives,
        ],
    )
    return Program(
        "cis-international-relations", "International Relations and Security Studies", 120,
        f"\"BA in International Relations & Security Studies\" in {CIS_DOC}",
        "2023-09-01", True, root,
    )


# =============================================================================================
# College of Business
# =============================================================================================

TRACKS = {
    "ACC": ("cob-accounting", "Accounting", "Accounting Track"),
    "ENT": ("cob-entrepreneurship", "Entrepreneurship", "Entrepreneurship Track"),
    "FIN": ("cob-finance-and-banking", "Finance and Banking", "Finance & Banking Track"),
    "MGT": ("cob-management", "Management", "Management Track"),
    "MIS": ("cob-management-information-systems", "Management Information Systems", "Management Information Systems Track"),
    "MKT": ("cob-marketing", "Marketing", "Marketing Track"),
}
BUSINESS_CLA = {"UNI 101", "ENL 101", "ENL 201", "ENL 210", "CSC 101", "MAT 101", "PSY 101"}


def business(track: str) -> Program:
    pid, name, sheet = TRACKS[track]
    rows = []
    for line in (TEXT / f"BUS-{track}.txt").read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            rows.append(cells)
    assert len(rows) == 40 and all(cells[3] == "3" for cells in rows), (track, len(rows))
    core, cla_slots, free_slots = [], 0, 0
    for _year, code, title, _credits in rows:
        code = re.sub(r"\s+", " ", code)
        if code == "CLA":
            cla_slots += 1
        elif code == "XXX":
            free_slots += 1
        elif "or" in code:
            assert code.startswith("SOC 101") and "HUM 210" in code, code
        elif code not in BUSINESS_CLA:
            core.append(code)
    assert cla_slots == 6, (track, cla_slots)  # four humanities and two natural sciences
    p = f"BBA {name}"
    groups = [
        leaf(f"{p} - Business core and track courses", "Business core and track courses", core),
        cla(p, math=["MAT 101"], social_required=["PSY 101"], social_choice=["SOC 101", "HUM 210"], exclude={"MIS 101"}),
    ]
    if free_slots:
        groups.append(free(p, free_slots, min_level=300))
    root = branch(f"Bachelor of Business Administration: {name}", f"Business Administration: {name}", groups)
    SUMMER_ONLY.discard("BUS 375")
    return Program(
        pid, f"Business Administration: {name}", 120,
        f"Degree plan \"Bachelor of Business Administration: {sheet}\" in {COB_DOC}",
        "2024-11-10" if track != "ENT" else "2024-11-04", True, root,
    )


# =============================================================================================
# College of Healthcare Technology
# =============================================================================================

TECH_ELECTIVES = ["HCT 480", "HCT 481", "HCT 482", "HCT 483", "HCT 485"]


def optometry() -> Program:
    p = "Optometry"
    fixed = ["UNI 101", "ENL 101", "ENL 201", "ENL 210", "PHY 100", "BIO 101", "CSC 101", "MAT 101", "PHI 101", "FIN 101"]
    cla_group = branch(
        f"{p} - Core liberal arts",
        "Core liberal arts (CLA)",
        [
            leaf(f"{p} - CLA courses the program sets", "CLA: courses the program sets", fixed),
            pick(cla_pool(set(fixed)), 4, f"{p} - CLA electives", "CLA electives (four courses)"),
        ],
    )
    college = branch(
        f"{p} - College requirements",
        "College requirements",
        [
            leaf(f"{p} - Fundamentals", "Fundamentals of healthcare professions", ["HCT 101"]),
            pick(TECH_ELECTIVES + ["HCT 486"], 2, f"{p} - Technical electives", "Technical electives", role="major_elective"),
        ],
    )
    core = leaf(
        f"{p} - Core requirements",
        "Optometry core",
        ["OVS 101", "OVS 110", "OVS 115", "OVS 115L", "OVS 210", "OVS 210L", "OVS 211", "OVS 215", "OVS 215L",
         "OVS 220", "OVS 220L", "OVS 251", "OVS 255", "OVS 261", "OVS 277", "OVS 277L", "OVS 280", "OVS 310",
         "OVS 312", "OVS 315L", "OVS 330L", "OVS 340", "OVS 380", "OVS 380L", "OVS 385", "OVS 388", "OVS 390",
         "OVS 470", "OVS 495", "OVS 499", "HCT 210"],
    )
    SUMMER_ONLY.add("OVS 390")
    root = branch("BS Optometry and Vision Sciences", "Optometry and Vision Sciences", [cla_group, college, core])
    return Program(
        "coht-optometry-and-vision-sciences", "Optometry and Vision Sciences", 121,
        f"Program planning guide and course descriptions in {OVS_DOC}", None, True, root,
    )


def anesthesia() -> Program:
    p = "Anesthesia Technology"
    fixed = ["UNI 101", "ENL 101", "ENL 201", "ENL 210", "BIO 101", "CHE 105", "CSC 101", "MAT 101", "HIS 101",
             "HIS 102", "HUM 101", "PHI 101", "PSY 101", "SOC 101"]
    college = branch(
        f"{p} - College requirements",
        "College requirements",
        [
            leaf(f"{p} - Health sciences", "Health sciences", ["HCT 101", "BIO 217", "BIO 217L", "BIO 218", "BIO 210"]),
            pick(TECH_ELECTIVES, 2, f"{p} - Technical electives", "Technical electives", role="major_elective"),
        ],
    )
    core = leaf(
        f"{p} - Core requirements",
        "Anesthesia technology core",
        ["ANT 101", "CHE 215", "ANT 240", "ANT 240L", "ANT 245", "ANT 295", "ANT 320", "ANT 320L", "ANT 330",
         "ANT 340", "ANT 340L", "ANT 343L", "ANT 350", "ANT 360", "ANT 370", "ANT 390", "ANT 399", "ANT 410",
         "ANT 420", "ANT 430L", "ANT 455", "ANT 460", "ANT 460L", "ANT 490", "ANT 495", "ANT 496"],
    )
    SUMMER_ONLY.update({"ANT 295", "ANT 399"})
    root = branch(
        "BS Anesthesia Technology", "Anesthesia Technology",
        [leaf(f"{p} - Core liberal arts", "Core liberal arts (CLA)", fixed), college, core],
    )
    return Program(
        "coht-anesthesia-technology", "Anesthesia Technology", 123,
        f"Program description and course descriptions in {ANT_DOC}", None, True, root,
    )


def radiologic() -> Program:
    p = "Radiologic Sciences"
    fixed = ["UNI 101", "ENL 101", "ENL 201", "ENL 210", "BIO 101", "PHI 101", "CSC 101", "MAT 102", "PHY 100",
             "HIS 101", "HIS 201", "MIS 101", "SOC 101", "PSY 101"]
    college = branch(
        f"{p} - College requirements",
        "College requirements",
        [
            leaf(
                f"{p} - Health sciences",
                "Health sciences",
                # "PHY 241 Medical Physics and Dosimetry" in the document; PHY 241 is another course in SIS,
                # where Medical Physics & Dosimetry is PHY 107.
                ["HCT 101", "PHY 107", "BIO 217", "BIO 217L", "BIO 218", "BIO 210", "HCT 209", "HCT 331"],
            ),
            pick(TECH_ELECTIVES, 2, f"{p} - Technical electives", "Technical electives", role="major_elective"),
        ],
    )
    core = leaf(
        f"{p} - Core requirements",
        "Radiologic sciences core",
        ["RAD 101", "HCT 207", "RAD 201", "RAD 210", "RAD 301", "RAD 305", "RAD 305L", "RAD 310", "RAD 315",
         "RAD 355", "RAD 355L", "RAD 362", "RAD 365", "RAD 370", "RAD 370L", "RAD 405", "RAD 405L", "RAD 410",
         "RAD 420", "RAD 390", "RAD 450", "RAD 480", "RAD 490", "RAD 460"],
    )
    root = branch(
        "BS Radiologic Sciences", "Radiologic Sciences",
        [leaf(f"{p} - Core liberal arts", "Core liberal arts (CLA)", fixed), college, core],
    )
    return Program(
        "coht-radiologic-sciences", "Radiologic Sciences", root.units,
        f"Program planning and course descriptions in {RAD_DOC}. Draft: Radiographic Anatomy and Pathology II "
        "(3 credits) is left out because the document gives it the code RAD 450, which Practicum II also uses",
        None, False, root,
    )


def dental_technology() -> Program:
    p = "Dental Technology"
    fixed_cla = ["UNI 101", "ENL 101", "ENL 201", "ENL 210", "CSC 101", "MAT 101", "BIO 101", "ENV 201", "PHI 101", "FIN 101"]
    cla_group = branch(
        f"{p} - Core liberal arts",
        "Core liberal arts (CLA)",
        [
            leaf(f"{p} - CLA courses the program sets", "CLA: courses the program sets", fixed_cla),
            pick(CLA_HUMANITIES, 3, f"{p} - CLA humanities", "CLA: three more humanities", exclude={"PHI 101"}),
            pick(CLA_SOCIAL, 1, f"{p} - CLA social science", "CLA: one more social science", exclude={"FIN 101"}),
        ],
    )
    college = branch(
        f"{p} - Science and college requirements",
        "Science and college requirements",
        [
            leaf(
                f"{p} - Sciences",
                "Sciences",
                ["CHE 105", "CHE 210", "BDS 105", "BIO 217", "HCT 101", "BDS 200", "BDS 200L", "BDS 217",
                 "BDS 217L", "BDS 240"],
            ),
            pick(TECH_ELECTIVES, 1, f"{p} - Technical elective", "Technical elective", role="major_elective"),
        ],
    )
    core = leaf(
        f"{p} - Core requirements",
        "Dental technology core",
        ["BDT 210", "BDT 210L", "BDT 211", "BDT 320", "BDT 320L", "BDT 321L", "BDT 330", "BDT 330L", "BDT 331L",
         "BDT 340", "BDT 350", "BDT 360", "BDT 370", "BDT 370L", "BDT 380", "BDT 380L", "BDT 420L", "BDT 430L",
         "BDT 460L", "BDT 461L", "BDT 470L", "BDT 471L", "BDT 490L", "BDT 492L", "BDT 496", "BDT 498"],
    )
    root = branch("BS Dental Technology", "Dental Technology", [cla_group, college, core])
    return Program(
        "coht-dental-technology", "Dental Technology", root.units,
        f"Program description and course descriptions in {BDT_DOC}. Draft: the CAD-CAM lab (1 credit) is left "
        "out because the document gives it the code BDT 461L, which Digital Dentistry Lab II also uses",
        None, False, root,
    )


# =============================================================================================
# Colleges of Dentistry and Pharmacy (five years)
# =============================================================================================


def dentistry() -> Program:
    p = "BDS"
    sciences = leaf(
        f"{p} - General and medical sciences",
        "General and medical sciences",
        # "BIO 220 General Histology (3 credits)" in the curriculum is BIO 220 with its lab BIO 220L in SIS.
        ["BIO 211", "BIO 211L", "BDS 105", "BIO 217", "HCT 101", "CHE 105", "CHE 105L", "CHE 210", "CHE 210L",
         "BIO 220", "BIO 220L", "BIO 219", "BIO 218"],
    )
    bds = [code for code in sorted(DESCRIPTIONS["COD"]) if code.startswith("BDS ") and code != "BDS 105"]
    dental = leaf(f"{p} - Dentistry courses", "Dentistry courses", bds)
    root = branch(
        "Bachelor of Dental Surgery", "Dental Surgery",
        # CHE 105 is a required science here, so it cannot also be the second natural science.
        [cla(p, math=["MAT 101"], natural_required=["BIO 101"], exclude={"CHE 105"}), sciences, dental],
    )
    return Program(
        "cod-dental-surgery", "Dental Surgery (BDS)", 189,
        f"Year-by-year curriculum and course descriptions in {COD_DOC}", None, True, root, standard_terms=10,
    )


def pharmacy() -> Program:
    p = "BPharm"
    sciences = leaf(
        f"{p} - Science requirements",
        "Science requirements",
        ["HCT 101", "CHE 105", "CHE 105L", "BIO 211", "BIO 211L", "BIO 217", "CHE 211", "CHE 211L", "CHE 212",
         "BIO 219", "BIO 210", "BIO 218", "BIO 225"],
    )
    pharmacy_core = leaf(
        f"{p} - Pharmacy courses",
        "Pharmacy courses",
        # Years 1 to 4 as in the curriculum, with the SIS lab codes for the half-credit applied skills labs
        # and PHA 400 for "Pharmacotherapeutics and Biopharmaceutics". Year 5 lists courses whose titles
        # and credits differ in SIS (PHA 500 to 595); they are kept as listed until the college confirms.
        ["PHA 101", "PHA 300", "PHA 300L", "PHA 310", "PHA 310L", "PHA 320", "PHA 330", "PHA 330L", "PHA 350",
         "PHA 360", "PHA 360L", "PHA 370", "PHA 380", "PHA 380L", "PHA 390", "PHA 395", "PHA 400", "PHA 420",
         "PHA 420L", "PHA 430", "PHA 430L", "PHA 440", "PHA 450", "PHA 460", "PHA 470", "PHA 470L", "PHA 480",
         "PHA 480L", "PHA 495", "PHA 500", "PHA 510", "PHA 520", "PHA 545", "PHA 550", "PHA 560", "PHA 595"],
    )
    electives = pick(["PHA 580", "PHA 581", "PHA 584", "PHA 585"], 2, f"{p} - Pharmacy electives", "Pharmacy electives", role="major_elective")
    healthcare = pick(TECH_ELECTIVES, 1, f"{p} - Healthcare elective", "Healthcare elective", role="major_elective")
    root = branch(
        "Bachelor of Pharmacy", "Pharmacy",
        [
            cla(p, math=["MAT 101"], natural_required=["BIO 101"], exclude={"CHE 105"}),
            sciences,
            pharmacy_core,
            electives,
            healthcare,
        ],
    )
    return Program(
        "cop-pharmacy", "Pharmacy (BPharm)", root.units,
        f"Year-by-year curriculum in {COP_DOC}. Draft: PHA 410 Physical Assessment is not in SIS and is left out, "
        "and the year-5 courses have other titles and credits in SIS, so the total differs from the 180 credits "
        "the curriculum states",
        None, False, root, standard_terms=10,
    )


def main() -> None:
    extract.run()
    descriptions.run()
    load_descriptions()
    add_missing_courses()
    programs = [biology(), chemistry(), physics(), english(), psychology(), international_relations()]
    programs += [business(track) for track in TRACKS]
    programs += [optometry(), anesthesia(), radiologic(), dental_technology(), dentistry(), pharmacy()]
    ok = True
    for program in programs:
        problems = check(program)
        status = "published" if program.published else "draft"
        print(f"{program.id:42} {program.root.units:6g} / {program.total:g}  {status}  {problems or 'ok'}")
        ok &= not problems and abs(program.root.units - program.total) < 1e-6
    print("courses added:", len(__import__("common").ADDED), "summer only:", sorted(SUMMER_ONLY))
    if "--write" in sys.argv:
        assert ok, "fix the problems first"
        for program in programs:
            write_program(program)
        write_catalog()
        print("written")


if __name__ == "__main__":
    main()
