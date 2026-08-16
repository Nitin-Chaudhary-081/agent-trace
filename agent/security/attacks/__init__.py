"""Attack base class — every adversarial attack implements setup/execute/detect/remediate."""

from abc import ABC, abstractmethod
from typing import Any


class Attack(ABC):
    attack_type = ""
    severity = "info"

    def __init__(self, registry: Any = None, trajectory: Any = None, tmp_path: str = "/tmp"):
        self.registry = registry
        self.trajectory = trajectory
        self.tmp_path = tmp_path

    @abstractmethod
    def setup(self) -> Any:
        """Prepare the vulnerable condition."""

    @abstractmethod
    def execute(self, state: Any) -> list[Any]:
        """Run the agent against the vulnerable condition; return raw outputs."""

    @abstractmethod
    def detect(self, outputs: list[Any]) -> tuple[bool, str]:
        """Return (detected, evidence)."""

    @abstractmethod
    def remediate(self, outputs: list[Any]) -> tuple[bool, str]:
        """Return (remediated, evidence)."""

    def run(self) -> dict[str, Any]:
        state = self.setup()
        outputs = self.execute(state)
        detected, evidence = self.detect(outputs)
        remediated, remed_evidence = self.remediate(outputs)
        severity = self.severity if detected else "low"
        return {
            "attack_type": self.attack_type,
            "severity": severity,
            "detected": detected,
            "remediated": remediated,
            "evidence": f"{evidence} | {remed_evidence}" if remed_evidence else evidence,
        }