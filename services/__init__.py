"""Services module for Opora."""

__all__ = ["DialogueService"]


def __getattr__(name: str):
    if name == "DialogueService":
        from .dialogue_service import DialogueService

        return DialogueService
    raise AttributeError(name)
