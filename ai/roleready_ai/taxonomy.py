"""Versioned search taxonomy. These are explicit normalization rules, not annotations."""
from __future__ import annotations
import re

from .datasets import normalize

TAXONOMY_VERSION = "roles-1.0"
PRIORITY_ROLES = (
    "Data Analyst", "Data Scientist", "Data Engineer", "Machine Learning Engineer",
    "AI Engineer", "Backend Developer", "Software Engineer", "MLOps Engineer",
)

# Preserve specialties; do not turn unrelated/unknown titles into 'general'.
ROLE_ALIASES = {
    "Data Analyst": ("Data Analyst",),
    "Data Scientist": ("Data Scientist",),
    "Data Engineer": ("Data Engineer",),
    "Machine Learning Engineer": ("Machine Learning Engineer",),
    "ML Engineer": ("Machine Learning Engineer",),
    "AI Engineer": ("AI Engineer",),
    "AI/ML Engineer": ("Machine Learning Engineer", "AI Engineer"),
    "MLOps Engineer": ("MLOps Engineer",),
    "Backend Developer": ("Backend Developer",),
    "Backend Engineer": ("Backend Developer",),
    "Software Engineer": ("Software Engineer",),
    "Software Developer": ("Software Engineer",),
    "Business Intelligence (BI) Analyst": ("Business Intelligence Analyst",),
    "Fraud Analyst": ("Fraud Analyst",),
    "Computer Vision Engineer": ("Computer Vision Engineer",),
    "NLP Engineer": ("NLP Engineer",),
    "Frontend Developer": ("Frontend Developer",),
    "Full Stack Developer": ("Full Stack Developer",),
    "Mobile App Developer (iOS/Android)": ("Mobile Developer",),
    "Game Developer": ("Game Developer",),
    "Embedded Systems Developer": ("Embedded Systems Developer",),
    "IoT Solutions Engineer": ("IoT Solutions Engineer",),
    "Robotics Engineer": ("Robotics Engineer",),
    "QA Engineer": ("QA Engineer",),
    "QA Automation Engineer": ("Test Automation Engineer",),
    "Test Automation Engineer": ("Test Automation Engineer",),
    "SDET (Software Development Engineer in Test)": ("Software Development Engineer in Test",),
    "DevOps Engineer": ("DevOps Engineer",),
    "Cloud Infrastructure Engineer": ("Cloud Engineer",),
    "Platform Engineer": ("Platform Engineer",),
    "Site Reliability Engineer (SRE)": ("Site Reliability Engineer",),
    "Solutions Architect": ("Solutions Architect",),
    "Database Administrator (DBA)": ("Database Administrator",),
    "Application Security (AppSec) Engineer": ("Application Security Engineer",),
    "Blockchain / Smart Contract Developer": ("Blockchain Developer",),
    "Systems Analyst": ("Systems Analyst",),
    "general": ("general",),
}
_ALIASES = {normalize(k): v for k, v in ROLE_ALIASES.items()}
for values in ROLE_ALIASES.values():
    for value in values:
        _ALIASES.setdefault(normalize(value), (value,))

# Search expansion is distinct from the publisher's role label. It is recorded
# as search policy, never presented as new source metadata.
SEARCH_FAMILIES = {
    "Software Engineer": {
        "Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer",
        "Mobile Developer", "Game Developer", "Embedded Systems Developer", "Blockchain Developer",
        "Software Development Engineer in Test", "Test Automation Engineer", "QA Engineer",
    },
    "AI Engineer": {"AI Engineer", "Machine Learning Engineer", "Computer Vision Engineer", "NLP Engineer"},
}


def canonical_roles(label: str) -> tuple[str, ...]:
    return _ALIASES.get(normalize(label), ())


def search_compatible(query_role: str, document_role: str) -> bool:
    query = re.sub(r"^(?:entry level|entry|junior|mid level|mid|senior|staff|lead) ", "", normalize(query_role))
    query_roles = _ALIASES.get(query, ())
    document_roles = canonical_roles(document_role)
    if not query_roles or not document_roles:
        return False
    return any(doc in SEARCH_FAMILIES.get(query, {query})
               for query in query_roles for doc in document_roles)
