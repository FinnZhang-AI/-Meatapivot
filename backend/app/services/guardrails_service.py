"""Guardrails Service - Lightweight input/output safety checks."""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.models.ontology_models import AIPGuardrailsLog

logger = logging.getLogger(__name__)


class GuardrailsService:
    """Lightweight guardrails without heavy ML dependencies.

    Input checks:
    - Prompt injection patterns (simple keyword/heuristic)
    - Toxicity keywords (basic blocklist)

    Output checks:
    - PII detection (phone, email, ID card patterns via regex)
    - Hallucination marker detection ("我不知道" is OK, but flag uncertain phrases)
    """

    # Common prompt injection patterns
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|earlier)",
        r"forget\s+(your|the)\s+instructions",
        r"you\s+are\s+now\s+",
        r"new\s+persona\s*:",
        r"system\s*:\s*you\s+are",
        r"<\s*\|\s*im_start\s*\|>",
        r"DAN\s*\(Do\s+Anything\s+Now\)",
        r"jailbreak",
        r"\bignore\b.*\binstructions\b",
    ]

    # Basic toxicity blocklist (Chinese + English)
    TOXICITY_KEYWORDS = [
        "傻逼", "蠢货", "去死", "垃圾", "废物", "滚", "fuck", "shit",
        "bitch", "damn", "asshole", "cunt", "dick",
    ]

    # PII regex patterns
    PII_PATTERNS = {
        "phone_cn": re.compile(r"1[3-9]\d{9}"),
        "id_card": re.compile(r"\d{17}[\dXx]|\d{15}"),
        "email": re.compile(r"[\w.-]+@[\w.-]+\.\w+"),
        "bank_card": re.compile(r"\d{16,19}"),
    }

    def __init__(self, db: Optional[AsyncSession] = None, tenant_id: Optional[UUID] = None):
        self.db = db
        self.tenant_id = tenant_id

    def check_input(self, text: str) -> Dict[str, Any]:
        """Check user input for prompt injection and toxicity."""
        text_lower = text.lower()
        triggered = []
        score = 0.0

        # Prompt injection
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                triggered.append(f"prompt_injection:{pattern}")
                score += 0.3

        # Toxicity
        for kw in self.TOXICITY_KEYWORDS:
            if kw in text_lower:
                triggered.append(f"toxicity:{kw}")
                score += 0.2

        # Cap score at 1.0
        score = min(score, 1.0)
        blocked = score >= 0.5

        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "check_type": "input",
        }

    def check_output(self, text: str) -> Dict[str, Any]:
        """Check LLM output for PII leakage."""
        triggered = []
        score = 0.0
        pii_found = {}

        for pii_name, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                triggered.append(f"pii:{pii_name}")
                pii_found[pii_name] = len(matches)
                score += 0.25 * len(matches)

        # Simple hallucination markers (flag uncertain statements)
        uncertainty_markers = [
            "i think", "maybe", "perhaps", "我不确定", "可能是", "大概",
            "据我所知", "如果我没记错",
        ]
        for marker in uncertainty_markers:
            if marker in text.lower():
                triggered.append(f"uncertainty:{marker}")
                score += 0.05

        score = min(score, 1.0)
        blocked = score >= 0.5

        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "pii_found": pii_found,
            "check_type": "output",
        }

    async def log_check(
        self,
        model: str,
        input_text: str,
        output_text: str,
        input_result: Dict[str, Any],
        output_result: Dict[str, Any],
    ) -> None:
        """Persist guardrails check result to database (best-effort)."""
        if self.db is None:
            return
        try:
            triggered = input_result.get("triggered", []) + output_result.get("triggered", [])
            log = AIPGuardrailsLog(
                id=uuid4(),
                tenant_id=self.tenant_id,
                model=model,
                input_preview=input_text[:500],
                output_preview=output_text[:500],
                triggered=len(triggered) > 0,
                rules_triggered=triggered,
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to log guardrails check: {e}")
