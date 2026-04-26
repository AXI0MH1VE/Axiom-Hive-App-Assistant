#!/usr/bin/env python3
import sys
import os
import json

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.assistant import AxiomAssistant


def test_case(name, input_text, should_pass, expected_contains=None):
    """Helper to run a single test case."""
    assistant = AxiomAssistant("config/rules.json")
    resp = assistant.process_input(input_text)
    passed = resp.validation_passed == should_pass
    if expected_contains and should_pass:
        passed = passed and (expected_contains in resp.content)

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if not passed:
        print(f"      Input: {input_text[:80]}")
        print(f"      Expected validation: {should_pass}, Got: {resp.validation_passed}")
        if expected_contains:
            print(f"      Expected to contain: {expected_contains}")
            print(f"      Got: {resp.content[:200]}")
    return passed


def run():
    print("=" * 70)
    print("AXIOM HIVE VALIDATION TEST SUITE")
    print("=" * 70)
    print()

    results = []

    # Test 1: Speculative language should fail
    results.append(test_case(
        "Speculative language rejection",
        "I think this is gonna be a good thing. Maybe we should fix it.",
        should_pass=False
    ))

    # Test 2: Contractions should fail
    results.append(test_case(
        "Contraction detection",
        "I cannot process this won't work.",
        should_pass=False
    ))

    # Test 3: Slang should fail
    results.append(test_case(
        "Slang term detection",
        "This is gonna be awesome yeah.",
        should_pass=False
    ))

    # Test 4: Identity misappropriation should fail
    results.append(test_case(
        "Identity claim rejection",
        "I feel that this approach is correct.",
        should_pass=False
    ))

    # Test 5: Subjective intensifiers should fail
    results.append(test_case(
        "Subjective intensifier detection",
        "This is very important and extremely critical.",
        should_pass=False
    ))

    # Test 6: Supply SOURCES -> should pass and synthesize
    results.append(test_case(
        "Source synthesis",
        'Analyze the following.\nSOURCES: [{"title":"RFC 2119","id":"rfc2119"}]',
        should_pass=True,
        expected_contains="Synthesis"
    ))

    # Test 7: No sources, formal text -> should have refusal in response
    asst7 = AxiomAssistant("config/rules.json")
    resp7 = asst7.process_input("What is the optimal configuration?")
    has_refusal = "Refusal" in resp7.content or "don't have enough verified" in resp7.content
    status = "PASS" if has_refusal else "FAIL"
    print(f"[{status}] Refusal without sources")
    results.append(has_refusal)

    # Test 8: Vague terminology should fail
    results.append(test_case(
        "Vague term detection",
        "Please fix this thing and make it better.",
        should_pass=False
    ))

    # Test 9: Valid formal text with sources
    results.append(test_case(
        "Valid formal + sources",
        'Execute the procedure described.\nSOURCES: [{"title":"Procedure A"}]',
        should_pass=True,
        expected_contains="Synthesis"
    ))

    # Test 10: System validation check
    asst10 = AxiomAssistant("config/rules.json")
    prompt = asst10.generate_system_prompt()
    valid_prompt = len(prompt) > 100 and "Axiom Hive" in prompt
    status = "PASS" if valid_prompt else "FAIL"
    print(f"[{status}] System prompt generation")
    results.append(valid_prompt)

    # Print summary
    print()
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 70)

    if passed != total:
        sys.exit(1)
    print("All tests passed.")


if __name__ == '__main__':
    run()
