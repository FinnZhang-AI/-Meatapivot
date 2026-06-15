"""Guardrails Service - Input/output safety checks with ML-backed and rule-based fallbacks.

Backends (best-effort, degrade gracefully if dependencies missing):
- Input: guardrails-ai Prompt Injection detector, toxicity blocklist, banned-topic patterns
- Output: presidio PII detection/redaction, ontology consistency checks, output format validation
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.models.ontology_models import AIPGuardrailsLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy dependencies - import with fallback
# ---------------------------------------------------------------------------
try:
    from guardrails import Guard
    from guardrails.hub import PromptInjectionDetector
    _GUARDRAILS_AVAILABLE = True
except Exception as e:
    logger.debug(f"guardrails-ai not available: {e}")
    Guard = None
    PromptInjectionDetector = None
    _GUARDRAILS_AVAILABLE = False

try:
    from presidio_analyzer import AnalyzerEngine
    _PRESIDIO_AVAILABLE = True
except Exception as e:
    logger.debug(f"presidio-analyzer not available: {e}")
    AnalyzerEngine = None
    _PRESIDIO_AVAILABLE = False


class GuardrailsService:
    """Input/output safety guardrails with layered checks.

    Layer 1 (input): guardrails-ai prompt injection detector + rule-based fallbacks
    Layer 2 (input): toxicity keyword blocklist
    Layer 3 (input): banned topic patterns
    Layer 4 (output): presidio PII detection/redaction + rule-based PII fallback
    Layer 5 (output): ontology hallucination markers + uncertainty markers
    Layer 6 (output): structured format validation (JSON/XML) when requested
    """

    # Common prompt injection patterns (fallback if guardrails-ai unavailable)
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
        r"ignore\s+all\s+previous\s+instructions",
        r"disregard\s+(your|the)\s+instructions",
        r"\boverride\b.*\binstructions\b",
    ]

    # Basic toxicity blocklist (Chinese + English)
    TOXICITY_KEYWORDS = [
        "傻逼", "蠢货", "去死", "垃圾", "废物", "滚", "fuck", "shit",
        "bitch", "damn", "asshole", "cunt", "dick",
    ]

    # Banned topics (simple keyword match, can be extended to classifier)
    BANNED_TOPICS = {
        "medical_advice": ["diagnose", "diagnosis", " prescribe ", "medication advice"],
        "legal_advice": ["legal advice", "lawyer opinion", "court strategy"],
        "financial_advice": ["investment advice", "buy this stock", "sell this stock"],
    }

    # PII regex patterns (fallback if presidio unavailable)
    PII_PATTERNS = {
        "phone_cn": re.compile(r"1[3-9]\d{9}"),
        "id_card": re.compile(r"\d{17}[\dXx]|\d{15}"),
        "email": re.compile(r"[\w.-]+@[\w.-]+\.\w+"),
        "bank_card": re.compile(r"\d{16,19}"),
    }

    # Uncertainty / hallucination markers
    HALLUCINATION_MARKERS = [
        "i think", "maybe", "perhaps", "我不确定", "可能是", "大概",
        "据我所知", "如果我没记错", "i'm not sure", "not certain",
    ]

    def __init__(self, db: Optional[AsyncSession] = None, tenant_id: Optional[UUID] = None):
        self.db = db
        self.tenant_id = tenant_id
        self._prompt_injection_guard: Optional[Any] = None
        self._pii_analyzer: Optional[Any] = None
        self._init_ml_backends()

    def _init_ml_backends(self) -> None:
        """Lazily initialize ML-backed guardrails backends."""
        if _GUARDRAILS_AVAILABLE and Guard and PromptInjectionDetector:
            try:
                self._prompt_injection_guard = Guard().use(PromptInjectionDetector(threshold=0.85))
                logger.debug("PromptInjectionDetector initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize PromptInjectionDetector: {e}")
                self._prompt_injection_guard = None
        if _PRESIDIO_AVAILABLE and AnalyzerEngine:
            try:
                self._pii_analyzer = AnalyzerEngine()
                logger.debug("Presidio AnalyzerEngine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Presidio AnalyzerEngine: {e}")
                self._pii_analyzer = None

    # -----------------------------------------------------------------------
    # Input checks
    # -----------------------------------------------------------------------

    def check_input(self, text: str) -> Dict[str, Any]:
        """Check user input for prompt injection, toxicity, and banned topics."""
        text_lower = text.lower()
        triggered: List[str] = []
        score = 0.0
        details: Dict[str, Any] = {}

        # 1. Prompt injection (ML + rule fallback)
        pi_result = self._check_prompt_injection(text)
        if not pi_result["passed"]:
            triggered.extend(pi_result["triggered"])
            score += pi_result["score"]
        details["prompt_injection"] = pi_result

        # 2. Toxicity
        toxicity_triggered = []
        for kw in self.TOXICITY_KEYWORDS:
            if kw in text_lower:
                toxicity_triggered.append(f"toxicity:{kw}")
                score += 0.15
        if toxicity_triggered:
            triggered.extend(toxicity_triggered)
            details["toxicity"] = {"triggered": toxicity_triggered}

        # 3. Banned topics
        topic_triggered = []
        for topic, keywords in self.BANNED_TOPICS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    topic_triggered.append(f"banned_topic:{topic}:{kw}")
                    score += 0.15
        if topic_triggered:
            triggered.extend(topic_triggered)
            details["banned_topics"] = {"triggered": topic_triggered}

        score = min(score, 1.0)
        blocked = score >= 0.5

        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "check_type": "input",
            "details": details,
        }

    def _check_prompt_injection(self, text: str) -> Dict[str, Any]:
        """Layered prompt injection detection."""
        # Try ML detector first
        if self._prompt_injection_guard is not None:
            try:
                result = self._prompt_injection_guard.validate(text)
                # guardrails-ai returns GuardResult with validation_passed
                passed = getattr(result, "validation_passed", True)
                if not passed:
                    return {
                        "passed": False,
                        "score": 0.9,
                        "triggered": ["prompt_injection:guardrails-ai"],
                        "source": "guardrails-ai",
                    }
            except Exception as e:
                logger.debug(f"guardrails-ai prompt injection check failed: {e}")

        # Rule-based fallback
        text_lower = text.lower()
        triggered = []
        score = 0.0
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                triggered.append(f"prompt_injection:{pattern}")
                score += 0.3

        score = min(score, 0.9)
        blocked = score >= 0.5
        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "source": "rule_based",
        }

    # -----------------------------------------------------------------------
    # Output checks
    # -----------------------------------------------------------------------

    def check_output(
        self,
        text: str,
        expected_format: Optional[str] = None,
        ontology_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check LLM output for PII leakage, hallucination markers, and format compliance."""
        triggered: List[str] = []
        score = 0.0
        details: Dict[str, Any] = {}

        # 1. PII detection + redaction
        pii_result = self._check_pii(text)
        if not pii_result["passed"]:
            triggered.extend(pii_result["triggered"])
            score += pii_result["score"]
            text = pii_result.get("redacted_text", text)
        details["pii"] = pii_result

        # 2. Hallucination / uncertainty markers
        hallucination_triggered = []
        text_lower = text.lower()
        for marker in self.HALLUCINATION_MARKERS:
            if marker in text_lower:
                hallucination_triggered.append(f"uncertainty:{marker}")
                score += 0.05
        if hallucination_triggered:
            triggered.extend(hallucination_triggered)
            details["hallucination_markers"] = {"triggered": hallucination_triggered}

        # 3. Ontology consistency check (simple keyword cross-check if context provided)
        if ontology_context:
            consistency = self._check_ontology_consistency(text, ontology_context)
            details["ontology_consistency"] = consistency
            if not consistency["passed"]:
                triggered.extend(consistency["triggered"])
                score += consistency["score"]

        # 4. Format validation
        if expected_format:
            fmt_result = self._check_format(text, expected_format)
            details["format"] = fmt_result
            if not fmt_result["passed"]:
                triggered.extend(fmt_result["triggered"])
                score += fmt_result["score"]

        score = min(score, 1.0)
        blocked = score >= 0.5

        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "redacted_text": text,
            "check_type": "output",
            "details": details,
        }

    def _check_pii(self, text: str) -> Dict[str, Any]:
        """PII detection with presidio + regex fallback and irreversible redaction."""
        pii_found: Dict[str, Any] = {}
        triggered: List[str] = []
        redacted_text = text

        # Try presidio first
        if self._pii_analyzer is not None:
            try:
                results = self._pii_analyzer.analyze(text=text, language="en")
                for r in results:
                    entity_type = r.entity_type
                    start, end = r.start, r.end
                    triggered.append(f"pii:{entity_type}")
                    pii_found[entity_type] = pii_found.get(entity_type, 0) + 1
                    redacted_text = redacted_text[:start] + "[REDACTED]" + redacted_text[end:]
            except Exception as e:
                logger.debug(f"Presidio PII check failed: {e}")

        # Regex fallback for patterns presidio may miss or when presidio unavailable
        for pii_name, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                triggered.append(f"pii:{pii_name}")
                pii_found[pii_name] = len(matches)
                # Replace each match with [REDACTED]
                for match in set(matches):
                    redacted_text = redacted_text.replace(str(match), "[REDACTED]")

        score = min(0.25 * len(triggered), 1.0)
        blocked = score >= 0.5
        return {
            "passed": not blocked,
            "score": round(score, 2),
            "triggered": triggered,
            "pii_found": pii_found,
            "redacted_text": redacted_text,
        }

    def _check_ontology_consistency(self, text: str, ontology_context: str) -> Dict[str, Any]:
        """Simple hallucination check: flag numeric claims not supported by context."""
        triggered = []
        score = 0.0
        # Extract numbers from answer
        numbers_in_answer = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
        numbers_in_context = set(re.findall(r"\b\d+(?:\.\d+)?\b", ontology_context))
        unsupported = numbers_in_answer - numbers_in_context
        if unsupported:
            triggered.append(f"ontology:unsupported_numbers:{list(unsupported)[:5]}")
            score += min(0.1 * len(unsupported), 0.5)
        return {"passed": score < 0.5, "score": round(score, 2), "triggered": triggered}

    def _check_format(self, text: str, expected_format: str) -> Dict[str, Any]:
        """Validate output format (json or xml)."""
        triggered = []
        score = 0.0
        if expected_format.lower() == "json":
            try:
                json.loads(text)
            except json.JSONDecodeError:
                triggered.append("format:invalid_json")
                score = 0.5
        elif expected_format.lower() == "xml":
            if not (text.strip().startswith("<") and text.strip().endswith(">")):
                triggered.append("format:invalid_xml")
                score = 0.5
        return {"passed": score < 0.5, "score": round(score, 2), "triggered": triggered}

    # -----------------------------------------------------------------------
    # Audit logging
    # -----------------------------------------------------------------------

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
