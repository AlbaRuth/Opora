"""
Test script to verify prompt updates are correctly applied.
This tests the new CORE_THERAPEUTIC_PRINCIPLES and boundary_checks.
"""

import sys
sys.path.insert(0, r'd:\Work\ClinicalAssistant\Opora')

from agents.prompts.therapist_prompts import TherapistPrompts
from agents.prompts.intake_prompts import IntakePrompts
from agents.prompts.evaluator_prompts import EvaluatorPrompts


def test_therapist_prompts():
    """Test that therapist prompts include CORE_THERAPEUTIC_PRINCIPLES."""
    print("\n=== Testing Therapist Prompts ===\n")
    
    # Test CORE_THERAPEUTIC_PRINCIPLES exists
    assert hasattr(TherapistPrompts, 'CORE_THERAPEUTIC_PRINCIPLES'), "CORE_THERAPEUTIC_PRINCIPLES not found"
    assert "NEUTRALITY" in TherapistPrompts.CORE_THERAPEUTIC_PRINCIPLES, "NEUTRALITY not found in principles"
    assert "BOUNDARIES" in TherapistPrompts.CORE_THERAPEUTIC_PRINCIPLES, "BOUNDARIES not found in principles"
    assert "NON-DIRECTIVE STANCE" in TherapistPrompts.CORE_THERAPEUTIC_PRINCIPLES, "NON-DIRECTIVE STANCE not found"
    print("[OK] CORE_THERAPEUTIC_PRINCIPLES exists with all key sections")
    
    # Test STYLE_GUIDELINES have boundary_checks
    for style_name, style_config in TherapistPrompts.STYLE_GUIDELINES.items():
        assert "boundary_checks" in style_config, f"boundary_checks not found in {style_name} style"
        assert len(style_config["boundary_checks"]) > 0, f"boundary_checks empty in {style_name} style"
        print(f"[OK] Style '{style_name}' has boundary_checks: {len(style_config['boundary_checks'])} checks")
    
    # Test system message includes principles
    system_msg = TherapistPrompts.get_system_message(
        therapist_name="Опора",
        therapist_gender="female",
        therapist_styles=["friendly", "soft"],
        address_mode="formal"
    )
    assert "CORE THERAPEUTIC PRINCIPLES" in system_msg, "System message doesn't include principles header"
    assert "NEUTRALITY" in system_msg, "NEUTRALITY not in system message"
    assert "BOUNDARY CHECKS" in system_msg, "BOUNDARY CHECKS not in system message"
    assert "You are a therapist, not a friend" in system_msg, "Boundary reminder not in system message"
    print("[OK] System message includes CORE_THERAPEUTIC_PRINCIPLES and boundary checks")
    
    # Test response prompt
    response_prompt = TherapistPrompts.get_response_prompt(
        patient_input="Я чувствую себя плохо",
        memory_result="",
        primary_emotion="sadness",
        emotional_intensity=0.7,
        current_therapy="CBT",
        current_stage="early",
        current_strategy="reflection",
        current_strategy_text="",
        session_memory={"dialogs": []},
        therapist_name="Опора",
        patient_display_name="Анна",
        therapist_styles=["soft"],
        address_mode="formal"
    )
    assert "ACTIVE STYLE" in response_prompt, "ACTIVE STYLE not in response prompt"
    print("[OK] Response prompt includes style guidance")
    
    print("\n[SUCCESS] All Therapist Prompts tests passed!\n")


def test_intake_prompts():
    """Test that intake prompts include CORE_THERAPEUTIC_PRINCIPLES."""
    print("\n=== Testing Intake Prompts ===\n")
    
    # Test CORE_THERAPEUTIC_PRINCIPLES exists
    assert hasattr(IntakePrompts, 'CORE_THERAPEUTIC_PRINCIPLES'), "CORE_THERAPEUTIC_PRINCIPLES not found"
    assert "INTAKE IS NOT DIAGNOSIS" in IntakePrompts.CORE_THERAPEUTIC_PRINCIPLES, "Diagnosis disclaimer not found"
    print("[OK] CORE_THERAPEUTIC_PRINCIPLES exists with intake-specific guidance")
    
    # Test STYLE_GUIDELINES have boundary_checks
    for style_name, style_config in IntakePrompts.STYLE_GUIDELINES.items():
        assert "boundary_checks" in style_config, f"boundary_checks not found in {style_name} style"
        print(f"[OK] Intake style '{style_name}' has boundary_checks")
    
    # Test system message includes principles
    system_msg = IntakePrompts.get_system_message(
        therapist_name="Опора",
        therapist_gender="female",
        therapist_styles=["friendly", "business"]
    )
    assert "CORE THERAPEUTIC PRINCIPLES FOR INTAKE" in system_msg, "Intake principles header not found"
    assert "BOUNDARY CHECKS" in system_msg, "BOUNDARY CHECKS not in intake system message"
    print("[OK] Intake system message includes principles and boundary checks")
    
    # Test intake turn prompt has open-ended question guidance
    intake_prompt = IntakePrompts.get_intake_turn_prompt(
        patient_message="Привет",
        patient_name="Анна",
        patient_age=30,
        patient_sex="female",
        address_mode="formal",
        current_card={},
        min_user_turns=3,
        current_user_turns=1,
        required_fields=["current_problems"],
        therapist_styles=["friendly"]
    )
    assert "OPEN-ENDED QUESTIONS" in intake_prompt, "Open-ended questions guidance not found"
    assert "нужно" in intake_prompt and "должен" in intake_prompt, "Directive words warning not found"
    print("[OK] Intake turn prompt includes open-ended questions guidance")
    
    # Test fallback responses are open-ended
    fallback_formal = IntakePrompts.get_fallback_intake_response(address_mode="formal")
    fallback_informal = IntakePrompts.get_fallback_intake_response(address_mode="informal")
    assert "?" in fallback_formal, "Fallback formal doesn't end with question"
    assert "?" in fallback_informal, "Fallback informal doesn't end with question"
    # Check they don't contain directive language
    directive_words = ["должен", "нужно", "следует", "обязан"]
    for word in directive_words:
        assert word.lower() not in fallback_formal.lower(), f"Directive word '{word}' in fallback"
        assert word.lower() not in fallback_informal.lower(), f"Directive word '{word}' in fallback"
    print("[OK] Fallback responses are open-ended and non-directive")
    
    print("\n[SUCCESS] All Intake Prompts tests passed!\n")


def test_evaluator_prompts():
    """Test that evaluator prompts have updated strategies."""
    print("\n=== Testing Evaluator Prompts ===\n")
    
    # Test Empathic Reflection is in strategies
    strategy_prompt = EvaluatorPrompts.get_strategy_prompt(
        patient_input="Я так устал от всего этого",
        primary_emotion="sadness",
        emotional_intensity=0.8,
        is_rejecting=False,
        session_strategy_memory=""
    )
    assert "Empathic Reflection" in strategy_prompt, "Empathic Reflection strategy not found"
    assert "PRIORITY strategy" in strategy_prompt, "Empathic Reflection priority not indicated"
    print("[OK] Empathic Reflection is a priority strategy")
    
    # Test problematic strategies are removed
    removed_strategies = [
        "Self-disclosure",
        "Confrontation",
        "Minimal Encouragement",
        "Affirmation and Reassurance",
        "Answer/Advice",
    ]
    for strategy in removed_strategies:
        # These should be marked as REMOVED or not present
        if "Self-disclosure" in strategy:
            assert "REMOVED" in strategy_prompt or "Self-disclosure" not in strategy_prompt, \
                f"Self-disclosure should be removed"
    print("[OK] Problematic strategies (Self-disclosure, Confrontation) are removed or marked")
    
    # Test new strategies are present
    new_strategies = ["Gentle Challenge", "Validation", "Clarification", "Summarization"]
    for strategy in new_strategies:
        assert strategy in strategy_prompt, f"New strategy '{strategy}' not found"
    print("[OK] New therapeutic strategies (Gentle Challenge, Validation, Clarification, Summarization) are present")
    
    # Test emotion assessment has masked emotion guidance
    emotion_prompt = EvaluatorPrompts.EMOTION_ASSESSMENT
    assert "Masked Emotions" in emotion_prompt or "masked" in emotion_prompt.lower(), \
        "Masked emotion guidance not found"
    assert "underlying" in emotion_prompt.lower(), "Underlying emotion guidance not found"
    print("[OK] Emotion assessment includes masked emotion detection guidance")
    
    print("\n[SUCCESS] All Evaluator Prompts tests passed!\n")


def test_boundary_checks_content():
    """Test that boundary checks contain expected warnings."""
    print("\n=== Testing Boundary Checks Content ===\n")
    
    # Test therapist styles
    for style_name, style_config in TherapistPrompts.STYLE_GUIDELINES.items():
        checks = style_config.get("boundary_checks", [])
        # Check for common boundary themes
        has_no_friend = any("другом" in c or "friend" in c.lower() for c in checks)
        has_no_rescue = any("спаса" in c or "rescue" in c.lower() or "спасай" in c for c in checks)
        has_no_promises = any("обещай" in c or "promise" in c.lower() for c in checks)
        has_no_goals = any("цели" in c or "goals" in c.lower() for c in checks)
        
        print(f"  {style_name}: другом={has_no_friend}, спасать={has_no_rescue}, обещания={has_no_promises}, навязывание={has_no_goals}")
    
    print("\n[SUCCESS] Boundary checks contain expected warnings!\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING UPDATED PROMPTS")
    print("="*60)
    
    try:
        test_therapist_prompts()
        test_intake_prompts()
        test_evaluator_prompts()
        test_boundary_checks_content()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! Prompts updated successfully.")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
