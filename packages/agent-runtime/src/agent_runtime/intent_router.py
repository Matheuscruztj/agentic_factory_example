"""Rule-based conversation intent routing; mutations become inert proposals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class IntentKind(StrEnum):
    ASK = "ask"
    READ = "read"
    PROPOSE = "propose"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class TaskProposal:
    title: str
    description: str
    path_scopes: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    executable: bool = False
    requires_human_review: bool = True


@dataclass(frozen=True, slots=True)
class ConversationIntent:
    kind: IntentKind
    text: str
    invoke_workflow: bool
    proposal: TaskProposal | None = None
    persona: str | None = None


_READ_ACTION = re.compile(
    r"\b(?:show|read|find|search|list|inspect|status|explain|summarize|mostre|leia|busque|procure|liste|inspecione|explique|resuma)\b",
    re.IGNORECASE,
)
_DISCOVERY_ONLY = re.compile(
    r"\b(?:discovery|read[- ]only|somente\s+leitura|apenas\s+leitura|"
    r"liste\s+(?:somente\s+)?(?:as\s+)?(?:ambiguidades|d[uú]vidas|fatos)|"
    r"identifique\s+(?:o|a)\s+(?:alvo|bot[aã]o|tema))\b",
    re.IGNORECASE,
)
_PROPOSE_ACTION = re.compile(
    r"\b(?:propose|suggest|proposal|proponha|sugira|proposta)\b", re.IGNORECASE
)
_NEGATED_PROPOSE_ACTION = re.compile(
    r"\b(?:do\s+not|don't|never|not|without|não|nao|nunca|sem)\s+"
    r"(?:to\s+)?(?:propose|suggest|proposal|proponha|sugira|proposta)\b",
    re.IGNORECASE,
)
_DIRECTIVE = re.compile(
    r"^(?:(?:please|can you|could you|would you|por favor|pode|poderia|eu quero|quero|"
    r"gostaria de|preciso|I want to|I need to|we need to)\s+)?"
    r"(?:implement|add|change|modify|remove|delete|fix|refactor|create|update|build|"
    r"implementa(?:r)?|implemente|adicione|adicionar|altere|alterar|mude|remova|remover|"
    r"corrija|corrigir|refatore|refatorar|crie|criar|atualize|atualizar|construa|construir)\b",
    re.IGNORECASE,
)


def route_conversation_intent(text: str) -> ConversationIntent:
    content = text.strip()
    if not content or len(content) > 20_000:
        raise ValueError("INVALID_CONVERSATION_MESSAGE")
    mentioned = re.search(r"@([a-z][a-z0-9_-]{1,31})\b", content, re.IGNORECASE)
    persona = mentioned.group(1).casefold() if mentioned else None
    if persona not in {"analyst", "planner", "backend", "frontend", "qa", "reviewer"}:
        persona = None
    if _DISCOVERY_ONLY.search(content):
        return ConversationIntent(IntentKind.READ, content, False, persona=persona)
    if _DIRECTIVE.search(content):
        proposal = TaskProposal(
            title=next((line.strip() for line in content.splitlines() if line.strip()), "")[:240],
            description=content,
        )
        return ConversationIntent(IntentKind.WRITE, content, False, proposal, persona)
    if _PROPOSE_ACTION.search(_NEGATED_PROPOSE_ACTION.sub("", content)):
        proposal = TaskProposal(
            title=next((line.strip() for line in content.splitlines() if line.strip()), "")[:240],
            description=content,
        )
        return ConversationIntent(IntentKind.PROPOSE, content, False, proposal, persona)
    if _READ_ACTION.search(content):
        return ConversationIntent(IntentKind.READ, content, False, persona=persona)
    return ConversationIntent(IntentKind.ASK, content, False, persona=persona)
