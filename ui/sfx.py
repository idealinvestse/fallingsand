from __future__ import annotations


class SfxManager:
    def __init__(self) -> None:
        self.enabled = True

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def play_event(self, event_name: str) -> None:
        if not self.enabled:
            return
        _ = event_name
