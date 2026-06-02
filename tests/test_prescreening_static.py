from pathlib import Path


def test_prescreening_handlers_are_defined_once() -> None:
    source = Path("integrations/telegram/prescreening.py").read_text(encoding="utf-8")

    assert source.count('"""Prescreening flow handlers."""') == 1
    assert source.count("async def on_skip_name") == 1
    assert source.count("async def on_gender_select") == 1
    assert source.count("async def on_patient_sex_select") == 1
    assert source.count("async def on_address_mode_select") == 1
    assert source.count("async def on_style_toggle") == 1
    assert source.count("async def on_styles_done") == 1
