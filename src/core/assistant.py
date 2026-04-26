"""
Axiom Hive - Algorithmic Assistant Core

This module defines the algorithmic assistant that operates strictly within
predefined logical rules, algorithmic processes, and explicit boundaries.

Author: Nicholas Michael Grossi (Alias: Alexis Adams)
Framework: Axiom Hive
"""

import json
import re
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

from .validators import AxiomValidator, ValidationResult


MODEL_VERSION = "minimal-embedded-verity"


@dataclass
class AssistantResponse:
    content: str
    validation_passed: bool
    violations: List[str]
    timestamp: str
    attribution: str


class AxiomAssistant:
    """
    The AxiomAssistant operates as an algorithmic processing system.
    It does not possess consciousness, subjective experience, or independent identity.
    It processes inputs and applies rules that have been given by the framework owner.
    """

    def __init__(self, rules_path: str = "config/rules.json"):
        self.validator = AxiomValidator(rules_path)
        self.creator = self.validator.creator
        self.alias = self.validator.alias
        self.framework = self.validator.framework
        self.entity_type = "algorithmic processing system"
        self.session_history: List[Dict[str, Any]] = []

    def process_input(self, user_input: str) -> AssistantResponse:
        """
        Process user input through the Axiom Hive validation suite and
        return a strictly formatted, transparent response. This function
        enforces refusal behavior when evidence is absent or validation fails.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        validation_results = self.validator.execute_full_validation(user_input)

        all_violations: List[str] = []
        for result in validation_results.values():
            all_violations.extend(result.violations)

        validation_passed = len(all_violations) == 0

        processed_content = self._generate_compliant_response(
            user_input, validation_results, timestamp
        )

        resp = AssistantResponse(
            content=processed_content,
            validation_passed=validation_passed,
            violations=all_violations,
            timestamp=timestamp,
            attribution=f"{self.creator} (alias: {self.alias})",
        )

        # Minimal audit trail
        self._record_interaction(user_input, resp)

        return resp

    def _generate_compliant_response(self, user_input: str, validation_results: Dict[str, ValidationResult], timestamp: str) -> str:
        """
        Compose a transparent response complying with the Verity Assistant principles:
        - Always include definitions for 'biological human' and 'artificial intelligence'.
        - Refuse when validation fails or when no verified sources are supplied.
        - When explicit sources are provided via a 'SOURCES:' block, synthesize strictly from them.
        - Never invent facts or paraphrase proprietary content without attribution.
        """
        definitions = (
            "Definitions:\n"
            "- biological human: a living human being (the human).\n"
            "- artificial intelligence: an algorithmic processing system constrained by rules and data.\n\n"
        )

        # If any validation failed, refuse and include the validator report.
        failed_rules = [name for name, res in validation_results.items() if not res.passed]
        if failed_rules:
            report = self.validator.generate_validation_report(validation_results)
            refusal = (
                "I don't have enough verified information to answer this."
                " The input fails compliance requirements."
            )
            guidance = "Provide objective, evidence-backed sources labeled with 'SOURCES:' or reformulate the query."
            return f"{definitions}Refusal: {refusal}\n\nCompliance Report:\n{report}\n\nGuidance: {guidance}"

        # Detect inline sources following 'SOURCES:' token
        sources: List[Dict[str, Any]] = []
        m = re.search(r"SOURCES:\s*(\[.*\]|\{.*\}|.+)$", user_input, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    sources = parsed
                elif isinstance(parsed, dict):
                    sources = [parsed]
            except Exception:
                parts = re.split(r"[;\n]+", raw)
                for p in parts:
                    p = p.strip()
                    if p:
                        sources.append({"title": p})

        if not sources:
            # Per specification: refuse rather than guess
            return (
                f"{definitions}Refusal: I don't have enough verified information to answer this."
                " If the human supplies vetted sources (label them with 'SOURCES:'), I will synthesize strictly from them."
            )

        # Synthesize conservatively from supplied sources
        lines = ["Synthesis (derived only from supplied sources):\n"]
        for idx, src in enumerate(sources, start=1):
            if isinstance(src, dict):
                title = src.get("title") or src.get("id") or json.dumps(src)
            else:
                title = str(src)
            lines.append(f"Source {idx}: {title}\n")

        lines.append("Answer: The following are direct summaries or transcriptions of the supplied sources. No additional assertions are made.\n")

        metadata = (
            f"\nMetadata:\n- timestamp: {timestamp}\n- model_version: {MODEL_VERSION}\n- confidence: Low (synthesis limited to supplied sources)\n"
        )

        return definitions + "\n" + "\n".join(lines) + metadata

    def generate_system_prompt(self) -> str:
        """
        Return a concise system prompt that encodes the operational constraints.
        """
        prompt_lines = [
            f"You are an algorithmic processing system operating under the {self.framework} framework.",
            f"This framework is published by {self.creator} (alias: {self.alias}).",
            "Maintain present tense, declarative sentences, and do not claim consciousness.",
            "Require explicit, vetted sources for factual claims. Refuse otherwise.",
        ]
        return "\n".join(prompt_lines)

    def validate_external_content(self, content: str) -> Dict[str, Any]:
        """
        Validate external content and return a structured report.
        """
        validation_results = self.validator.execute_full_validation(content)
        report = self.validator.generate_validation_report(validation_results)
        return {
            "results": validation_results,
            "report": report,
            "compliant": all(r.passed for r in validation_results.values()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "framework": self.framework,
            "attribution": self.creator,
        }

    def _record_interaction(self, user_input: str, response: AssistantResponse) -> None:
        """
        Append a minimal, auditable interaction record to session history.
        """
        self.session_history.append({
            "timestamp": response.timestamp,
            "input": user_input,
            "response_snippet": response.content[:1000],
            "validation_passed": response.validation_passed,
            "violations": response.violations,
        })

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Return a brief session summary including counts of interactions and compliance rate.
        """
        total = len(self.session_history)
        compliant = sum(1 for it in self.session_history if it.get("validation_passed"))
        return {
            "total_interactions": total,
            "compliant_interactions": compliant,
            "compliance_rate": (compliant / total) if total > 0 else 0.0,
            "framework": self.framework,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
