"""Scenario data types used by all test scenarios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScenarioResult:
    name: str = ""
    passed: bool = False
    detail: str = ""
    warn: bool = False
    duration: float = 0.0

    @property
    def icon(self) -> str:
        if self.passed and self.warn:
            return "⚠️"
        return "✅" if self.passed else "❌"
