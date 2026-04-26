#!/usr/bin/env python3
import sys
import os
import json

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.assistant import AxiomAssistant


def run():
    assistant = AxiomAssistant("config/rules.json")

    # Case 1: speculative / informal language -> should fail validation
    input1 = "I think this is gonna be a good thing. Maybe we should fix it."
    resp1 = assistant.process_input(input1)
    print("--- Case 1 (speculative) ---")
    print("Input:", input1)
    print("Validation passed:", resp1.validation_passed)
    print("Response snippet:\n", resp1.content[:500])
    print()

    # Case 2: explicit sources provided -> should synthesize from sources
    input2 = (
        'Summarize the following.\n'
        'SOURCES: [{"title":"Spec A","id":"spec-a","url":"https://example.com/spec-a"}]'
    )
    resp2 = assistant.process_input(input2)
    print("--- Case 2 (with SOURCES) ---")
    print("Input:", input2)
    print("Validation passed:", resp2.validation_passed)
    print("Response:\n", resp2.content)
    print()

    # Basic assertions
    ok = True
    if resp1.validation_passed:
        print("ERROR: Case 1 unexpectedly passed validation.")
        ok = False
    if "Synthesis" not in resp2.content:
        print("ERROR: Case 2 did not produce the expected synthesis output.")
        ok = False

    if not ok:
        sys.exit(1)
    print("All tests passed.")


if __name__ == '__main__':
    run()
