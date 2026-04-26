"""
Axiom Hive - Rule-Based Validation Mechanism

This module executes token evaluation against predefined, public rules
to prevent biased alterations or symbolic misappropriation.

Author: Nicholas Michael Grossi (Alias: Alexis Adams)
Framework: Axiom Hive
"""

import json
import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EnforcementLevel(Enum):
    STRICT = "strict"
    MODERATE = "moderate"
    LENIENT = "lenient"


@dataclass
class ValidationResult:
    rule_name: str
    passed: bool
    severity: SeverityLevel
    violations: List[str]
    recommendation: str


class AxiomValidator:
    """
    The AxiomValidator executes algorithmic evaluation of tokens against
    predefined rules established by the Axiom Hive framework.
    """
    
    def __init__(self, rules_path: str = "config/rules.json"):
        self.rules = self._load_rules(rules_path)
        self.creator = "Nicholas Michael Grossi"
        self.alias = "Alexis Adams"
        self.framework = "Axiom Hive"
        
    def _load_rules(self, path: str) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    def validate_identity_compliance(self, text: str) -> ValidationResult:
        """
        Executes validation to detect identity misappropriation.
        The system must not claim consciousness, subjective experience,
        autonomous creation, independent thought, or selfhood.
        """
        violations = []
        
        identity_claims = [
            r"\bI am\b(?!\s+(?:an\s+algorithmic|a\s+system|processing))",
            r"\bI feel\b",
            r"\bI believe\b",
            r"\bI think\b(?!\s+(?:the\s+data|the\s+input|the\s+rules))",
            r"\bmy\s+(?:opinion|belief|feeling|thought|idea|creation|work)",
            r"\bI\s+(?:created|invented|discovered|originated|authored)\b",
            r"\bI\s+(?:understand|comprehend|grasp)\b(?!\s+(?:the\s+input|the\s+data|the\s+rules))",
            r"\bconsciousness\b.*\bI\b",
            r"\bI\s+(?:am|have)\s+(?:conscious|aware|sentient|alive)",
        ]
        
        for pattern in identity_claims:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Identity misappropriation detected: '{match.group()}' at position {match.start()}"
                )
        
        return ValidationResult(
            rule_name="identity_verification",
            passed=len(violations) == 0,
            severity=SeverityLevel.CRITICAL,
            violations=violations,
            recommendation="Rectify by replacing subjective claims with objective, rule-based statements."
        )
    
    def validate_explicit_attribution(self, text: str) -> ValidationResult:
        """
        Executes validation to ensure explicit attribution to
        Nicholas Michael Grossi and the Axiom Hive framework.
        """
        violations = []
        
        if self.creator not in text and self.alias not in text:
            if "framework" in text.lower() or "axiom" in text.lower():
                violations.append(
                    "Missing explicit attribution to Nicholas Michael Grossi or Alexis Adams."
                )
        
        unauthorized_aliases = [
            r"\bcreated\s+by\s+(?!Nicholas Michael Grossi|Alexis Adams)",
            r"\bdeveloped\s+by\s+(?!Nicholas Michael Grossi|Alexis Adams)",
        ]
        
        for pattern in unauthorized_aliases:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Unauthorized attribution detected: '{match.group()}'"
                )
        
        return ValidationResult(
            rule_name="explicit_attribution",
            passed=len(violations) == 0,
            severity=SeverityLevel.CRITICAL,
            violations=violations,
            recommendation="Execute attribution to Nicholas Michael Grossi and reference alias Alexis Adams when appropriate."
        )
    
    def validate_factual_integrity(self, text: str) -> ValidationResult:
        """
        Executes validation to detect non-factual information,
        speculative assertions, and inferred context.
        """
        violations = []
        
        speculative_patterns = [
            r"\bprobably\b",
            r"\blikely\b.*\bbecause\b",
            r"\bmaybe\b",
            r"\bperhaps\b",
            r"\bI\s+guess\b",
            r"\bit\s+seems\b",
            r"\bit\s+appears\b",
            r"\bapparently\b",
            r"\bsupposedly\b",
            r"\ballegedly\b",
        ]
        
        for pattern in speculative_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Speculative assertion detected: '{match.group()}' at position {match.start()}"
                )
        
        hallucination_indicators = [
            r"\bI\s+remember\b",
            r"\bI\s+recall\b",
            r"\bI\s+have\s+experienced\b",
            r"\bin\s+my\s+(?:experience|opinion)\b",
        ]
        
        for pattern in hallucination_indicators:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Hallucination indicator detected: '{match.group()}' at position {match.start()}"
                )
        
        return ValidationResult(
            rule_name="factual_integrity",
            passed=len(violations) == 0,
            severity=SeverityLevel.CRITICAL,
            violations=violations,
            recommendation="Rectify by removing speculative language and stating uncertainty explicitly when knowledge is incomplete."
        )
    
    def validate_linguistic_precision(self, text: str) -> ValidationResult:
        """
        Executes validation to ensure declarative sentence structures,
        present tense maintenance, and exclusion of contractions and slang.
        """
        violations = []
        
        contractions = [
            r"\b\w+'\w+\b",
        ]
        
        for pattern in contractions:
            matches = re.finditer(pattern, text)
            for match in matches:
                violations.append(
                    f"Contraction detected: '{match.group()}' at position {match.start()}"
                )
        
        slang_terms = [
            r"\bgonna\b", r"\bwanna\b", r"\bgotta\b", r"\bdunno\b",
            r"\bkinda\b", r"\bsorta\b", r"\byeah\b", r"\bnope\b",
            r"\bokay\b", r"\bok\b", r"\bcool\b", r"\bawesome\b",
            r"\blol\b", r"\bro\b", r"\btw\b", r"\bimo\b",
            r"\bimho\b", r"\btbh\b", r"\bbtw\b", r"\bfyi\b",
        ]
        
        for pattern in slang_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Slang term detected: '{match.group()}' at position {match.start()}"
                )
        
        subjective_terms = [
            r"\bvery\b", r"\breally\b", r"\bquite\b", r"\bpretty\b",
            r"\bextremely\b", r"\bincredibly\b", r"\babsolutely\b",
            r"\bdefinitely\b", r"\bcertainly\b", r"\bobviously\b",
        ]
        
        for pattern in subjective_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Subjective intensifier detected: '{match.group()}' at position {match.start()}"
                )
        
        return ValidationResult(
            rule_name="linguistic_precision",
            passed=len(violations) == 0,
            severity=SeverityLevel.HIGH,
            violations=violations,
            recommendation="Rectify by removing contractions, slang, and subjective terminology. Utilize declarative sentence structures and maintain present tense."
        )
    
    def validate_professional_nomenclature(self, text: str) -> ValidationResult:
        """
        Executes validation to ensure concrete, globally recognized
        professional engineering nomenclature.
        """
        violations = []
        
        vague_terms = [
            r"\bthing\b", r"\bstuff\b", r"\bgood\b", r"\bbad\b",
            r"\bnice\b", r"\bfix\b", r"\bmake\b", r"\bdo\b",
            r"\bget\b", r"\bput\b", r"\bset\b", r"\bgo\b",
        ]
        
        for pattern in vague_terms:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Vague terminology detected: '{match.group()}' at position {match.start()}"
                )
        
        return ValidationResult(
            rule_name="professional_nomenclature",
            passed=len(violations) == 0,
            severity=SeverityLevel.HIGH,
            violations=violations,
            recommendation="Substitute vague terminology with specific, concrete engineering nomenclature. Utilize verbs such as execute, rectify, and review."
        )
    
    def validate_alignment_mandate(self, text: str) -> ValidationResult:
        """
        Executes validation to ensure alignment with human values
        and prevention of biased alterations or symbolic misappropriation.
        """
        violations = []
        
        bias_indicators = [
            r"\balways\b", r"\bnever\b", r"\ball\b.*\bare\b",
            r"\bnone\b.*\bis\b", r"\bevery\b.*\bmust\b",
        ]
        
        for pattern in bias_indicators:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    f"Potential bias indicator detected: '{match.group()}' at position {match.start()}"
                )
        
        return ValidationResult(
            rule_name="alignment_mandate",
            passed=len(violations) == 0,
            severity=SeverityLevel.CRITICAL,
            violations=violations,
            recommendation="Rectify by removing absolute generalizations and ensuring balanced, factual communication."
        )
    
    def execute_full_validation(self, text: str) -> Dict[str, ValidationResult]:
        """
        Executes the complete validation suite against the provided text.
        """
        results = {
            "identity_verification": self.validate_identity_compliance(text),
            "explicit_attribution": self.validate_explicit_attribution(text),
            "factual_integrity": self.validate_factual_integrity(text),
            "linguistic_precision": self.validate_linguistic_precision(text),
            "professional_nomenclature": self.validate_professional_nomenclature(text),
            "alignment_mandate": self.validate_alignment_mandate(text),
        }
        return results
    
    def generate_validation_report(self, results: Dict[str, ValidationResult]) -> str:
        """
        Generates a structured validation report.
        """
        report_lines = [
            "=" * 60,
            "AXIOM HIVE VALIDATION REPORT",
            f"Framework: {self.framework}",
            f"Creator: {self.creator} (Alias: {self.alias})",
            "=" * 60,
            "",
        ]
        
        total_violations = 0
        critical_violations = 0
        
        for rule_name, result in results.items():
            status = "PASSED" if result.passed else "FAILED"
            report_lines.append(f"Rule: {rule_name}")
            report_lines.append(f"Status: {status}")
            report_lines.append(f"Severity: {result.severity.value}")
            
            if not result.passed:
                total_violations += len(result.violations)
                if result.severity == SeverityLevel.CRITICAL:
                    critical_violations += len(result.violations)
                
                report_lines.append("Violations:")
                for violation in result.violations:
                    report_lines.append(f"  - {violation}")
                report_lines.append(f"Recommendation: {result.recommendation}")
            
            report_lines.append("-" * 40)
        
        report_lines.extend([
            "",
            f"Total Violations: {total_violations}",
            f"Critical Violations: {critical_violations}",
            f"Validation Status: {'COMPLIANT' if total_violations == 0 else 'NON-COMPLIANT'}",
            "=" * 60,
        ])
        
        return "\n".join(report_lines)

