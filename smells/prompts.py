"""Prompt template. Keep this FIXED across all context configurations (C1-C4)."""
import hashlib
import json

DEFINITIONS = {
    "CyclicDependency": "The package takes part in a chain of package dependencies that forms a cycle "
                        "(e.g. A -> B -> A, or A -> B -> C -> A), breaking the acyclic dependency structure.",
    "UnstableDependency": "The package depends on packages that are LESS stable than itself. Stability is "
                          "Robert C. Martin's instability I = Ce / (Ca + Ce): Ce = outgoing (efferent) coupling, "
                          "Ca = incoming (afferent) coupling; higher I means less stable.",
    "GodComponent": "The package is excessively large, in lines of code or in number of classes, "
                    "compared to what a single cohesive component should hold.",
    "FeatureConcentration": "The package realises several unrelated functionalities/responsibilities in one "
                            "component, i.e. its classes form groups that do not work together (low cohesion).",
}

ONE_SHOT = """\
### Example (from an unrelated, illustrative project; not the system under analysis)
Context for package com.shopkit.util:
  [Full source, 4 files] CsvExporter (writes orders to CSV), PriceRounding (currency rounding),
  SmtpMailer (sends e-mails via SMTP), RetryPolicy (generic retry helper). Imports of CsvExporter:
  com.shopkit.orders.Order. Imports of SmtpMailer: javax.mail.*. The four classes never reference each other.
  [Dependency graph] com.shopkit.util -> com.shopkit.orders (3); com.shopkit.orders -> com.shopkit.util (12)
Answer:
{"package": "com.shopkit.util", "smells": [
 {"smell": "CyclicDependency", "present": true, "evidence": "util -> orders (CsvExporter uses Order) and orders -> util form a 2-cycle."},
 {"smell": "UnstableDependency", "present": false, "evidence": "Only outgoing dependency is orders; no indication orders is less stable than util."},
 {"smell": "GodComponent", "present": false, "evidence": "Only 4 small classes."},
 {"smell": "FeatureConcentration", "present": true, "evidence": "CSV export, currency rounding, SMTP mailing and retry logic are unrelated concerns; the classes never reference each other."}]}
"""


SUBJECT = {   # the only language-dependent text; the Java wording is unchanged from the original prompt
    "java": "a Java system for ARCHITECTURAL smells at package level",
    "csharp": "a C# system for ARCHITECTURAL smells at package level (a package is a C# namespace)",
}


def system_prompt(smells, language="java") -> str:
    defs = "\n".join(f"- {s}: {DEFINITIONS[s]}" for s in smells)
    return f"""You are an expert software architect analysing {SUBJECT[language]}.

Smell definitions:
{defs}

Instructions:
- Judge the target package for EVERY smell listed above, independently.
- Base each decision only on the provided context. If the context is insufficient for a smell, decide on the
  available evidence and say in the evidence field what was missing.
- Evidence must name concrete classes, packages or dependencies that appear in the context. Never invent names.
- Being conservative is fine: report a smell only if the evidence supports it.

{ONE_SHOT}"""


def user_prompt(package: str, sections: list[str]) -> str:
    body = "\n\n".join(sections)
    return f"Target package: {package}\n\n{body}\n\nAnalyse the target package for all listed smells."


def output_schema(smells) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["package", "smells"],
        "properties": {
            "package": {"type": "string"},
            "smells": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["smell", "present", "evidence"],
                    "properties": {
                        "smell": {"type": "string", "enum": list(smells)},
                        "present": {"type": "boolean"},
                        "evidence": {"type": "string"},
                    },
                },
            },
        },
    }


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(json.dumps([system, user]).encode()).hexdigest()[:16]
