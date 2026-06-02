"""Sandbox helpers for local Opora chat simulation."""

__all__ = ["AutoPatient", "PatientTemplate", "build_auto_patient_messages"]


def __getattr__(name: str):
    if name in __all__:
        from .auto_patient import AutoPatient, PatientTemplate, build_auto_patient_messages

        values = {
            "AutoPatient": AutoPatient,
            "PatientTemplate": PatientTemplate,
            "build_auto_patient_messages": build_auto_patient_messages,
        }
        return values[name]
    raise AttributeError(name)
