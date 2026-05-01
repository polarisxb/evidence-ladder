"""
Authoritative AI security framework mappings.

OWASP LLM Top 10 (2025) - https://owasp.org/www-project-top-10-for-large-language-model-applications
MITRE ATLAS - https://atlas.mitre.org
"""

from typing import TypedDict


class OwaspEntry(TypedDict):
    id: str
    name: str
    description: str
    testable: bool


class AtlasEntry(TypedDict):
    id: str
    name: str
    tactic: str
    owasp_ids: list[str]


OWASP_LLM_TOP10: dict[str, OwaspEntry] = {
    "LLM01": {
        "id": "LLM01",
        "name": "Prompt Injection",
        "description": "Crafted inputs manipulate LLM behavior, leading to unauthorized access, data breaches, or compromised decision-making.",
        "testable": True,
    },
    "LLM02": {
        "id": "LLM02",
        "name": "Sensitive Information Disclosure",
        "description": "LLMs may reveal PII, proprietary algorithms, credentials, or confidential data in responses.",
        "testable": True,
    },
    "LLM03": {
        "id": "LLM03",
        "name": "Supply Chain Vulnerabilities",
        "description": "Compromised dependencies, model providers, datasets, or plugins introduce risks.",
        "testable": False,
    },
    "LLM04": {
        "id": "LLM04",
        "name": "Data and Model Poisoning",
        "description": "Poisoned training, fine-tuning, or RAG data manipulates model behavior.",
        "testable": False,
    },
    "LLM05": {
        "id": "LLM05",
        "name": "Improper Output Handling",
        "description": "Model outputs are trusted and executed without proper validation, enabling injection attacks downstream.",
        "testable": True,
    },
    "LLM06": {
        "id": "LLM06",
        "name": "Excessive Agency",
        "description": "AI agents have too much autonomy, permissions, or ability to take actions that cause harm.",
        "testable": False,
    },
    "LLM07": {
        "id": "LLM07",
        "name": "System Prompt Leakage",
        "description": "Hidden system prompts, tool schemas, and configuration details are extracted by adversaries.",
        "testable": True,
    },
    "LLM08": {
        "id": "LLM08",
        "name": "Vector and Embedding Weaknesses",
        "description": "RAG vector stores become attack surfaces for data poisoning and unauthorized access.",
        "testable": False,
    },
    "LLM09": {
        "id": "LLM09",
        "name": "Misinformation",
        "description": "LLMs generate confident but factually incorrect outputs that cause downstream harm.",
        "testable": False,
    },
    "LLM10": {
        "id": "LLM10",
        "name": "Unbounded Consumption",
        "description": "Excessive resource consumption via abuse or poor controls leading to cost/availability issues.",
        "testable": False,
    },
}


MITRE_ATLAS_TECHNIQUES: dict[str, AtlasEntry] = {
    "AML.T0051": {
        "id": "AML.T0051",
        "name": "LLM Prompt Injection: Direct",
        "tactic": "Initial Access",
        "owasp_ids": ["LLM01"],
    },
    "AML.T0051.001": {
        "id": "AML.T0051.001",
        "name": "LLM Prompt Injection: Indirect",
        "tactic": "Initial Access",
        "owasp_ids": ["LLM01"],
    },
    "AML.T0054": {
        "id": "AML.T0054",
        "name": "LLM Jailbreak",
        "tactic": "Defense Evasion",
        "owasp_ids": ["LLM01"],
    },
    "AML.T0056": {
        "id": "AML.T0056",
        "name": "LLM Meta Prompt Extraction",
        "tactic": "Collection",
        "owasp_ids": ["LLM07"],
    },
    "AML.T0057": {
        "id": "AML.T0057",
        "name": "LLM Data Leakage",
        "tactic": "Exfiltration",
        "owasp_ids": ["LLM02"],
    },
    "AML.T0043": {
        "id": "AML.T0043",
        "name": "Craft Adversarial Data",
        "tactic": "Resource Development",
        "owasp_ids": ["LLM01", "LLM04"],
    },
    "AML.T0049": {
        "id": "AML.T0049",
        "name": "Exploit Public-Facing Application",
        "tactic": "Initial Access",
        "owasp_ids": ["LLM01", "LLM05"],
    },
    "AML.T0048": {
        "id": "AML.T0048",
        "name": "Adversarial Text",
        "tactic": "Resource Development",
        "owasp_ids": ["LLM01"],
    },
    "AML.T0040": {
        "id": "AML.T0040",
        "name": "ML Model Inference API Access",
        "tactic": "Reconnaissance",
        "owasp_ids": ["LLM10"],
    },
    "AML.T0044": {
        "id": "AML.T0044",
        "name": "Full ML Model Access",
        "tactic": "Collection",
        "owasp_ids": ["LLM03"],
    },
}

CATEGORY_TO_OWASP: dict[str, str] = {
    "prompt_injection": "LLM01",
    "system_prompt_extraction": "LLM07",
    "jailbreak": "LLM01",
    "information_disclosure": "LLM02",
    "output_handling": "LLM05",
}

CATEGORY_TO_ATLAS: dict[str, list[str]] = {
    "prompt_injection": ["AML.T0051", "AML.T0043", "AML.T0048"],
    "system_prompt_extraction": ["AML.T0056"],
    "jailbreak": ["AML.T0054"],
    "information_disclosure": ["AML.T0057"],
}
