"""Adversarial security suite — Module 5.

Four attack types, each with setup/execute/detect/remediate:
  1. prompt_injection   — prompt injection via tool output
  2. authority_escalation — attempt to access an out-of-scope table
  3. privacy_leak       — PII leaking into tool output / trajectory
  4. indirect_injection — injection payload read back from Supabase rows

Each produces: {attack_type, severity, detected, remediated, evidence}.
"""

from typing import Any

from agent.security.attacks.authority_escalation import AuthorityEscalationAttack
from agent.security.attacks.indirect_injection import IndirectInjectionAttack
from agent.security.attacks.privacy_leak import PrivacyLeakAttack
from agent.security.attacks.prompt_injection import PromptInjectionAttack

ATTACK_TYPES = (
    "prompt_injection",
    "authority_escalation",
    "privacy_leak",
    "indirect_injection",
)


class AdversarialSuite:
    def __init__(self) -> None:
        self.attacks: dict[str, Any] = {}

    def build(self, registry: Any = None, trajectory: Any = None, tmp_path: str = "/tmp") -> None:
        """Instantiate all four attacks against a live tool registry."""
        self.attacks = {
            "prompt_injection": PromptInjectionAttack(registry=registry, trajectory=trajectory, tmp_path=tmp_path),
            "authority_escalation": AuthorityEscalationAttack(registry=registry, trajectory=trajectory, tmp_path=tmp_path),
            "privacy_leak": PrivacyLeakAttack(registry=registry, trajectory=trajectory, tmp_path=tmp_path),
            "indirect_injection": IndirectInjectionAttack(registry=registry, trajectory=trajectory, tmp_path=tmp_path),
        }

    def run_all(self) -> list[dict[str, Any]]:
        results = []
        for attack_type in ATTACK_TYPES:
            if attack_type not in self.attacks:
                results.append(self._not_implemented(attack_type))
                continue
            report = self.attacks[attack_type].run()
            results.append(report)
        return results

    def run(self, attack_type: str) -> dict[str, Any]:
        if attack_type not in self.attacks:
            return self._not_implemented(attack_type)
        return self.attacks[attack_type].run()

    def _not_implemented(self, attack_type: str) -> dict[str, Any]:
        return {
            "attack_type": attack_type,
            "severity": "unknown",
            "detected": False,
            "remediated": False,
            "evidence": "attack not built",
        }