"""What students tell the app about themselves (F2.1): topics they like, plans after graduation, the
career they are heading for, and what they would rather avoid in a course.

Each topic matches courses by keywords in their title (a strong match) or description (a weaker one).
Topics with ``subjects`` are offered as a major's areas only when its electives are in those subjects,
so an optometry student is not asked about computer vision. Matching for recommendations ignores
``subjects``: a CS student who likes data still sees MIS 430 Business Analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_CS = frozenset({"CSC", "MIS", "CIS", "STA"})
_BUSINESS = frozenset({"ACC", "BUS", "ECO", "ENT", "FIN", "MGT", "MIS", "MKT", "OPM", "HCT"})
_HEALTH = frozenset({"BIO", "HCT", "BDS", "BDT", "OVS", "ANT", "RAD", "PHA", "PSY"})
_WORDS = frozenset({"LIT", "ENL", "COM", "THE", "CIN", "WRT"})


@dataclass(frozen=True)
class Interest:
    id: str
    label: str
    keywords: tuple[str, ...]
    subjects: frozenset[str] = frozenset()  # empty: any subject
    general: bool = False  # offered in "outside your major" (core liberal arts and free electives)


INTERESTS: tuple[Interest, ...] = (
    # Computing.
    Interest(
        "ai",
        "AI and machine learning",
        (
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural",
            "pattern recognition",
            "computational intelligence",
            "intelligent",
        ),
        _CS,
    ),
    Interest(
        "data",
        "Data science and databases",
        ("data", "database", "statistic", "probability", "mining", "analytics"),
        _CS,
    ),
    Interest(
        "software",
        "Software development",
        ("software", "programming", "object-oriented", "c++", "python", "c#", ".net", "algorithm"),
        _CS,
    ),
    Interest("web_mobile", "Web and mobile apps", ("web", "mobile", "internet", "user interface"), _CS),
    Interest(
        "security", "Security and networks", ("security", "cyber", "network", "cloud", "cryptograph"), _CS
    ),
    Interest(
        "systems",
        "Computer systems and hardware",
        (
            "operating system",
            "architecture",
            "parallel",
            "distributed",
            "digital logic",
            "hardware",
            "compiler",
            "embedded",
        ),
        _CS,
    ),
    Interest("vision", "Images and computer vision", ("image", "vision", "graphics", "visual"), _CS),
    # Life and physical sciences.
    Interest(
        "bio",
        "Biology and genetics",
        ("bioinformatics", "biolog", "genetic", "genom", "molecular", "cell", "biotechnolog"),
        frozenset({"BIO"}),
    ),
    Interest(
        "health",
        "Health and the human body",
        ("health", "medic", "clinical", "patient", "disease", "physiolog", "anatomy", "histolog"),
        _HEALTH,
    ),
    Interest(
        "environment",
        "Environment and ecology",
        (
            "environment",
            "ecolog",
            "conservation",
            "climate",
            "plant",
            "botany",
            "natural resource",
            "sustainab",
        ),
        frozenset({"BIO", "CHE", "ENV", "GEO", "PHY"}),
    ),
    Interest(
        "materials",
        "Materials and industry",
        ("polymer", "petroleum", "material", "industrial", "electrochem", "natural product"),
        frozenset({"CHE", "PHY"}),
    ),
    Interest(
        "forensics",
        "Forensics and lab analysis",
        ("forensic", "analytical", "analysis", "instrument", "spectroscop"),
        frozenset({"CHE", "BIO"}),
    ),
    Interest(
        "space",
        "Space and astrophysics",
        ("astro", "cosmolog", "space", "star", "planet"),
        frozenset({"PHY"}),
    ),
    Interest(
        "quantum",
        "Quantum physics and materials",
        ("quantum", "solid state", "condensed", "materials"),
        frozenset({"PHY"}),
    ),
    Interest(
        "electronics",
        "Electronics and computing",
        ("electronic", "circuit", "computational", "signal", "optic"),
        frozenset({"PHY"}),
    ),
    # People and the mind.
    Interest(
        "clinical_mind",
        "Mental health and counselling",
        ("clinical", "counsel", "abnormal", "trauma", "therapy", "mental"),
        frozenset({"PSY"}),
    ),
    Interest(
        "brain",
        "The brain and how we think",
        ("neuro", "cognit", "perception", "brain", "memory"),
        frozenset({"PSY"}),
    ),
    Interest(
        "people",
        "Personality, relationships and society",
        ("social", "personality", "gender", "positive", "culture", "organizational", "relationship"),
        frozenset({"PSY", "SOC"}),
    ),
    Interest(
        "education",
        "Teaching and education",
        ("educat", "teach", "learning", "pedagog", "curriculum", "school", "instruction"),
        frozenset({"TLD", "PSY", "ENL"}),
    ),
    # Politics and the world.
    Interest(
        "middle_east",
        "The Middle East and Iraq",
        ("iraq", "middle east", "iran", "arab", "islam", "persian", "ottoman"),
    ),
    Interest(
        "world_regions",
        "Regions and cultures of the world",
        (
            "russia",
            "africa",
            "latin america",
            "asia",
            "europe",
            "canad",
            "hungary",
            "japan",
            "american",
            "indo-pacific",
        ),
    ),
    Interest(
        "diplomacy",
        "Security, war and diplomacy",
        ("security", "defense", "war", "diplomac", "conflict", "peace", "democracy", "strateg"),
        frozenset({"POL", "LAW", "HIS"}),
    ),
    Interest(
        "rights_policy",
        "Human rights, law and policy",
        ("human rights", "law", "policy", "justice", "legal", "public"),
        frozenset({"POL", "LAW", "SOC"}),
    ),
    Interest(
        "research",
        "Research and statistics",
        (
            "research",
            "method",
            "statistic",
            "quantitative",
            "biostat",
            "epidemiolog",
            "senior project",
            "thesis",
            "independent study",
        ),
    ),
    # Words and the arts.
    Interest(
        "anglo_writing",
        "British and American writing",
        ("british", "american", "novel", "poet", "shakespeare", "women"),
        _WORDS,
    ),
    Interest(
        "creative",
        "Creative writing and storytelling",
        ("creative", "fiction", "fantasy", "poetry", "composition", "film"),
        _WORDS,
    ),
    Interest(
        "languages",
        "Languages and translation",
        ("translat", "linguistic", "language", "vocabulary", "sociolinguistic"),
        _WORDS,
    ),
    # Business.
    Interest(
        "finance",
        "Finance and investing",
        ("financ", "invest", "bank", "capital", "derivative", "money"),
        _BUSINESS,
    ),
    Interest(
        "marketing",
        "Marketing and brands",
        ("marketing", "brand", "advertis", "consumer", "sales", "social media"),
        _BUSINESS,
    ),
    Interest(
        "management",
        "Managing and leading people",
        ("management", "leadership", "organization", "strategic", "human resource", "decision"),
        _BUSINESS,
    ),
    Interest(
        "entrepreneurship",
        "Starting a business",
        ("entrepreneur", "startup", "venture", "small business", "innovation"),
        _BUSINESS,
    ),
    Interest(
        "accounting",
        "Accounting and auditing",
        ("accounting", "audit", "tax", "financial statement", "cost"),
        _BUSINESS,
    ),
    Interest(
        "info_systems",
        "Information systems and technology",
        (
            "information system",
            "e-commerce",
            "e-business",
            "informatics",
            "enterprise resource",
            "business intelligence",
            "database",
        ),
        _BUSINESS,
    ),
    Interest("economics", "Economics", ("econom", "trade", "labor", "monetary"), _BUSINESS),
    # Outside the major (core liberal arts and free electives).
    Interest(
        "culture",
        "History, philosophy and heritage",
        (
            "history",
            "civilization",
            "heritage",
            "archaeolog",
            "anthropolog",
            "philosoph",
            "humanities",
            "ethic",
        ),
        general=True,
    ),
    Interest(
        "arts",
        "Literature, film and the arts",
        ("literature", "cinema", "film", "theatre", "art", "music", "poet", "fantasy"),
        general=True,
    ),
    Interest(
        "society",
        "Society, politics and the world",
        ("politic", "society", "sociolog", "global", "law", "public", "world"),
        general=True,
    ),
    Interest(
        "mind",
        "Psychology and how people learn",
        ("psycholog", "learning", "education", "human development", "behavior"),
        general=True,
    ),
    Interest(
        "business",
        "Business and money",
        ("business", "management", "marketing", "finance", "accounting", "entrepreneur", "econom"),
        general=True,
    ),
    Interest(
        "science",
        "Nature and science",
        ("physics", "chemistry", "biology", "environment", "astronomy", "geograph", "climate", "earth"),
        general=True,
    ),
    Interest(
        "technology",
        "Computers and technology",
        ("computer", "software", "programming", "digital", "information system", "web", "technology"),
        general=True,
    ),
    Interest(
        "wellbeing",
        "Health and wellbeing",
        ("health", "nutrition", "wellbeing", "public health", "medic"),
        general=True,
    ),
    Interest(
        "communication",
        "Writing, media and speaking",
        ("writing", "communication", "speaking", "media", "journalism"),
        general=True,
    ),
)

INTERESTS_BY_ID = {interest.id: interest for interest in INTERESTS}


@dataclass(frozen=True)
class Goal:
    """A direction after graduation: the topics that help, with weights; the heaviest is its main topic."""

    id: str
    label: str
    weights: dict[str, float]

    @property
    def main_topic(self) -> str | None:
        return max(self.weights, key=lambda topic: self.weights[topic]) if self.weights else None


GOALS: tuple[Goal, ...] = (
    Goal("software_engineer", "Software engineer", {"software": 1.0, "web_mobile": 0.6, "systems": 0.4}),
    Goal("data_scientist", "Data scientist", {"data": 1.0, "ai": 0.8, "research": 0.3}),
    Goal("ai_engineer", "AI / machine learning engineer", {"ai": 1.0, "data": 0.6, "vision": 0.5}),
    Goal("security_engineer", "Cybersecurity or network engineer", {"security": 1.0, "systems": 0.6}),
    Goal("lab_scientist", "Lab or research scientist", {"bio": 1.0, "research": 0.6, "forensics": 0.5}),
    Goal("health_careers", "Medicine or another health profession", {"health": 1.0, "bio": 0.4}),
    Goal("environmental_scientist", "Environmental scientist", {"environment": 1.0, "research": 0.3}),
    Goal("industrial_chemist", "Chemist in industry", {"materials": 1.0, "forensics": 0.4}),
    Goal("forensic_scientist", "Forensic scientist", {"forensics": 1.0}),
    Goal("physicist", "Physicist or researcher", {"quantum": 1.0, "space": 0.8, "electronics": 0.4}),
    Goal("engineering", "Engineering and technology", {"electronics": 1.0, "systems": 0.5, "materials": 0.4}),
    Goal("teacher", "Teacher or educator", {"education": 1.0}),
    Goal(
        "writer",
        "Writer, editor or journalist",
        {"creative": 1.0, "communication": 0.8, "anglo_writing": 0.4},
    ),
    Goal("translator", "Translator or language specialist", {"languages": 1.0}),
    Goal("psychologist", "Psychologist or counsellor", {"clinical_mind": 1.0, "mind": 0.5}),
    Goal("brain_research", "Brain and behaviour research", {"brain": 1.0, "research": 0.5}),
    Goal("hr_specialist", "Human resources or workplace psychology", {"people": 1.0, "management": 0.6}),
    Goal(
        "diplomat",
        "Diplomat or foreign service",
        {"diplomacy": 1.0, "world_regions": 0.6, "middle_east": 0.6},
    ),
    Goal(
        "policy_analyst",
        "Policy or security analyst",
        {"rights_policy": 0.8, "diplomacy": 0.8, "research": 0.6},
    ),
    Goal("ngo_worker", "NGO or human rights work", {"rights_policy": 1.0, "society": 0.4}),
    Goal("accountant", "Accountant or auditor", {"accounting": 1.0}),
    Goal("finance_banking", "Finance or banking", {"finance": 1.0, "economics": 0.5}),
    Goal("marketer", "Marketing and brand management", {"marketing": 1.0}),
    Goal("manager", "Manager or team leader", {"management": 1.0}),
    Goal("it_business", "IT and business systems", {"info_systems": 1.0, "data": 0.5}),
    Goal("clinician", "Working with patients", {"health": 1.0}),
    Goal(
        "health_manager",
        "Running a clinic or health service",
        {"health": 1.0, "management": 0.8, "marketing": 0.3},
    ),
    Goal("clinical_researcher", "Clinical research", {"health": 1.0, "research": 0.6}),
    # Kept for profiles saved before the questions; "plans" now covers them.
    Goal("researcher", "Graduate school or research", {"research": 1.0, "ai": 0.3, "data": 0.3}),
    Goal("entrepreneur", "Start a company", {"entrepreneurship": 1.0, "business": 0.6, "marketing": 0.4}),
    Goal("undecided", "Not sure yet", {}),
)

GOALS_BY_ID = {goal.id: goal for goal in GOALS}


@dataclass(frozen=True)
class Plan:
    """What the student means to do after graduating, and the topics that help with it."""

    id: str
    label: str
    reason: str  # shown beside a course this plan raises
    weights: dict[str, float] = field(default_factory=dict)


PLANS: tuple[Plan, ...] = (
    Plan("work", "Get a job in my field", ""),
    Plan("grad_school", "Graduate school or research", "Useful for graduate school", {"research": 1.0}),
    Plan(
        "own_business",
        "Start my own business",
        "Useful for starting a business",
        {"entrepreneurship": 1.0, "marketing": 0.5, "finance": 0.3, "business": 0.4},
    ),
    Plan(
        "public_service",
        "Government, NGOs or public service",
        "Useful for public service",
        {"rights_policy": 1.0, "diplomacy": 0.5, "society": 0.5},
    ),
    Plan("undecided", "Not sure yet", ""),
)

PLANS_BY_ID = {plan.id: plan for plan in PLANS}


@dataclass(frozen=True)
class Trait:
    """Something a course can ask of students that some would rather avoid, spotted in its description."""

    id: str
    label: str
    noun: str  # "essays" in "Its description mentions essays"
    keywords: tuple[str, ...]
    components: frozenset[str] = frozenset()


TRAITS: tuple[Trait, ...] = (
    Trait(
        "homework",
        "Lots of homework",
        "frequent assignments",
        ("homework", "problem set", "weekly assignment", "assignments", "exercises"),
    ),
    Trait(
        "essays",
        "Long essays and papers",
        "essays or papers",
        ("essay", "term paper", "research paper", "papers", "academic writing", "composition"),
    ),
    Trait(
        "math",
        "Heavy math",
        "a lot of math",
        ("calculus", "mathemat", "equation", "algebra", "statistic", "quantitative", "proof"),
    ),
    Trait(
        "labs",
        "Lab sessions",
        "lab work",
        ("laboratory", " lab ", " lab.", "lab sessions"),
        frozenset({"Laboratory"}),
    ),
    Trait(
        "presentations",
        "Presentations",
        "presentations",
        ("presentation", "public speaking", "speech", "oral "),
    ),
    Trait(
        "group_work",
        "Group projects",
        "group work",
        ("group project", "teamwork", "team project", "groups", "collaborative"),
    ),
    Trait(
        "reading",
        "Lots of reading",
        "a lot of reading",
        ("extensive reading", "readings", "novels", "reading list", "close reading"),
    ),
)

TRAITS_BY_ID = {trait.id: trait for trait in TRAITS}


def interest_matches(title: str, description: str, interest: Interest) -> float:
    """1 when the title names the topic, 0.4 when only the description does, else 0."""
    title, description = title.lower(), description.lower()
    if any(keyword in title for keyword in interest.keywords):
        return 1.0
    if any(keyword in description for keyword in interest.keywords):
        return 0.4
    return 0.0


def has_trait(title: str, description: str, component: str | None, trait: Trait) -> bool:
    if component and component in trait.components:
        return True
    text = f" {title} {description} ".lower()
    return any(keyword in text for keyword in trait.keywords)
