"""The Actor — who is making a request, resolved server-side every time.

Client-supplied role/owner/isAdmin is NEVER authoritative (DOMAIN_MODEL §4).
The Actor is built from the resolved principal: a human user (with a fixed
role), the non-login system Agent, an internal system service, or anonymous.
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role


@dataclass(frozen=True, slots=True)
class Actor:
    principal_id: str | None
    principal_type: PrincipalType
    role: Role | None
    request_id: str = ""
    correlation_id: str = ""

    @property
    def is_authenticated(self) -> bool:
        return self.principal_type != PrincipalType.ANONYMOUS and self.principal_id is not None

    @property
    def is_admin(self) -> bool:
        return self.principal_type == PrincipalType.HUMAN and self.role == Role.ADMIN

    @property
    def is_agent(self) -> bool:
        return self.principal_type == PrincipalType.AGENT

    @property
    def actor_kind(self) -> ActorKind:
        if self.principal_type == PrincipalType.AGENT:
            return ActorKind.AGENT
        if self.principal_type == PrincipalType.SYSTEM:
            return ActorKind.SYSTEM_SERVICE
        return ActorKind.HUMAN

    @staticmethod
    def anonymous(request_id: str = "", correlation_id: str = "") -> Actor:
        return Actor(
            principal_id=None,
            principal_type=PrincipalType.ANONYMOUS,
            role=None,
            request_id=request_id,
            correlation_id=correlation_id,
        )
