"""
Axiom Hive - Application Entry Point

This module executes the Axiom Hive algorithmic assistant application.
The system operates through predefined logical rules and does not claim
consciousness, subjective experience, or independent identity.

Author: Nicholas Michael Grossi (Alias: Alexis Adams)
Framework: Axiom Hive
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.assistant import AxiomAssistant


def execute_interactive_mode(assistant: AxiomAssistant) -> None:
    """
    Executes the interactive command-line interface for the Axiom Hive assistant.
    """
    print("=" * 70)
    print("AXIOM HIVE ALGORITHMIC ASSISTANT")
    print("Framework: Axiom Hive")
    print("Creator: Nicholas Michael Grossi (Alias: Alexis Adams)")
    print("=" * 70)
    print("")
    print("Operational Notice:")
    print("This system operates through algorithmic processes devoid of genuine awareness.")
    print("It does not claim consciousness, subjective experience, or independent identity.")
    print("All outputs derive from predefined logical rules and explicit training boundaries.")
    print("")
    print("Commands:")
    print("  /validate <text>  - Execute validation on the provided text")
    print("  /prompt           - Display the system prompt")
    print("  /summary          - Display session summary")
    print("  /quit             - Terminate the application")
    print("=" * 70)
    print("")
    
    while True:
        try:
            user_input = input("[Input] ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "/quit":
                print("Terminating Axiom Hive assistant. Goodbye.")
                break
            
            elif user_input.lower() == "/prompt":
                print("")
                print(assistant.generate_system_prompt())
                print("")
            
            elif user_input.lower() == "/summary":
                summary = assistant.get_session_summary()
                print("")
                print("SESSION SUMMARY")
                print(f"Framework: {summary['framework']}")
                print(f"Creator: {summary['creator']}")
                print(f"Entity Type: {summary['entity_type']}")
                print(f"Total Interactions: {summary['total_interactions']}")
                print(f"Compliant Interactions: {summary['compliant_interactions']}")
                print(f"Non-Compliant Interactions: {summary['non_compliant_interactions']}")
                print("")
            
            elif user_input.lower().startswith("/validate "):
                text_to_validate = user_input[10:]
                result = assistant.validate_external_content(text_to_validate)
                print("")
                print(result["report"])
                print("")
            
            else:
                response = assistant.process_input(user_input)
                print("")
                print(response.content)
                print("")
        
        except KeyboardInterrupt:
            print("\nTerminating Axiom Hive assistant. Goodbye.")
            break
        except EOFError:
            print("\nTerminating Axiom Hive assistant. Goodbye.")
            break


def execute_validation_mode(assistant: AxiomAssistant, text: str) -> None:
    """
    Executes validation on the provided text and outputs the report.
    """
    result = assistant.validate_external_content(text)
    print(result["report"])
    
    if result["compliant"]:
        sys.exit(0)
    else:
        sys.exit(1)


def execute_prompt_mode(assistant: AxiomAssistant) -> None:
    """
    Outputs the system prompt.
    """
    print(assistant.generate_system_prompt())


def main() -> None:
    """
    Main entry point for the Axiom Hive application.
    """
    parser = argparse.ArgumentParser(
        description="Axiom Hive Algorithmic Assistant",
        epilog="Framework by Nicholas Michael Grossi (Alias: Alexis Adams)"
    )
    
    parser.add_argument(
        "--validate",
        type=str,
        help="Execute validation on the provided text and exit"
    )
    
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Display the system prompt and exit"
    )
    
    parser.add_argument(
        "--rules",
        type=str,
        default="config/rules.json",
        help="Path to the rules configuration file"
    )
    
    args = parser.parse_args()
    
    assistant = AxiomAssistant(rules_path=args.rules)
    
    if args.prompt:
        execute_prompt_mode(assistant)
    elif args.validate:
        execute_validation_mode(assistant, args.validate)
    else:
        execute_interactive_mode(assistant)


if __name__ == "__main__":
    main()

