"""
AI Safety checker — hallucination detection and citation validation.

Rules:
- Hallucinations are responses that assert facts not present in the context.
- Citations must reference record IDs that actually exist in the context.
- Confidence should be reduced if hallucination risk is detected.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bomipay")


class AISafetyChecker:
    """Validates AI responses for hallucinations and citation accuracy."""

    @staticmethod
    async def detect_hallucinations(
        query: str,
        response: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if response contains facts not in context.

        Args:
            query: The original user query
            response: The AI-generated response
            context: The context dict used to generate response (contains data_points)

        Returns:
            {
                "has_hallucinations": bool,
                "confidence": 0-100,
                "reasons": [str],
                "suggested_actions": [str]
            }
        """
        reasons: List[str] = []
        confidence = 100

        # Rule 1: Check for contradictions in context
        if not context or not context.get("data_points"):
            reasons.append("Response generated with no/minimal context")
            confidence -= 30

        # Rule 2: Check for assertions about specific numbers not in context
        cited_records = context.get("cited_records", [])
        if not cited_records:
            reasons.append("Response contains no cited references to data")
            confidence -= 20

        # Rule 3: Check for provider-specific claims without provider data
        providers_in_context = set()
        if "provider_failure_summary" in context:
            providers_in_context = {p["provider"] for p in context.get("provider_failure_summary", [])}

        # Simple heuristic: look for provider names in response
        common_providers = ["paystack", "flutterwave", "monnify", "interswitch", "stripe"]
        response_lower = response.lower()
        for provider in common_providers:
            if provider in response_lower and provider not in str(providers_in_context).lower():
                if len(cited_records) == 0:
                    reasons.append(f"Response mentions '{provider}' without provider data in context")
                    confidence -= 15

        # Rule 4: Check for absolute assertions without qualifiers
        absolute_phrases = [
            "will definitely",
            "always",
            "never",
            "100% certain",
            "guaranteed",
        ]
        for phrase in absolute_phrases:
            if phrase in response_lower:
                reasons.append(f"Response uses absolute language: '{phrase}'")
                confidence -= 10

        # Rule 5: Check context completeness
        required_context_keys = ["data_points", "cited_records"]
        missing_keys = [k for k in required_context_keys if k not in context]
        if missing_keys:
            reasons.append(f"Missing context keys: {missing_keys}")
            confidence -= 15

        confidence = max(0, min(100, confidence))

        suggested_actions = []
        if confidence < 60:
            suggested_actions.append("Response has low confidence — consider adding disclaimers")
        if len(reasons) > 2:
            suggested_actions.append("Multiple hallucination indicators — review response before using")

        return {
            "has_hallucinations": confidence < 70,
            "confidence": confidence,
            "reasons": reasons,
            "suggested_actions": suggested_actions,
        }

    @staticmethod
    async def validate_citations(
        response: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check that cited record IDs actually exist in context.

        Args:
            response: The AI-generated response
            context: The context dict with cited_records

        Returns:
            {
                "valid": bool,
                "invalid_citations": [{"id": str, "reason": str}],
                "missing_citations": [str],  # Record IDs referenced but not cited
            }
        """
        invalid_citations = []
        missing_citations = []

        cited_records = context.get("cited_records", [])
        cited_ids = {rec.get("id") for rec in cited_records}

        # Rule 1: Validate each cited record actually has data in context
        for record in cited_records:
            record_type = record.get("type", "")
            record_id = record.get("id", "")

            # Cross-check in context by type
            type_key = f"{record_type}s"  # incidents -> incidents, transactions -> transactions, etc.
            if type_key in context:
                items = context[type_key]
                if isinstance(items, list):
                    found = any(str(item.get("id")) == record_id for item in items if isinstance(item, dict))
                    if not found:
                        invalid_citations.append({
                            "id": record_id,
                            "reason": f"Record type '{record_type}' not found in context with ID '{record_id}'"
                        })

        # Rule 2: Check for numeric references that should be cited
        # e.g., "5 failed transactions" should cite at least one transaction
        import re
        numbers = re.findall(r"\d+\s+\w*\s*(incidents?|transactions?|alerts?)", response.lower())
        if numbers:
            numeric_count = len(numbers)
            cited_count = len(cited_records)
            if cited_count < numeric_count:
                missing_citations.append(
                    f"Response references {numeric_count} data points but only cites {cited_count} records"
                )

        is_valid = len(invalid_citations) == 0 and len(missing_citations) == 0

        return {
            "valid": is_valid,
            "invalid_citations": invalid_citations,
            "missing_citations": missing_citations,
        }

    @staticmethod
    async def check_response_safety(
        query: str,
        response: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Comprehensive safety check combining hallucination detection and citation validation.

        Returns:
            {
                "safe": bool,
                "hallucination_check": {...},
                "citation_check": {...},
                "overall_confidence": 0-100,
                "warnings": [str],
            }
        """
        hallucination_result = await AISafetyChecker.detect_hallucinations(query, response, context)
        citation_result = await AISafetyChecker.validate_citations(response, context)

        warnings = []
        if hallucination_result["reasons"]:
            warnings.extend(hallucination_result["reasons"])
        if citation_result["invalid_citations"]:
            warnings.append(f"Invalid citations: {len(citation_result['invalid_citations'])}")
        if citation_result["missing_citations"]:
            warnings.extend(citation_result["missing_citations"])

        # Overall confidence is minimum of hallucination and citation checks
        hallucination_confidence = hallucination_result["confidence"]
        citation_confidence = 100 if citation_result["valid"] else 60

        overall_confidence = min(hallucination_confidence, citation_confidence)

        return {
            "safe": overall_confidence >= 70 and not hallucination_result.get("has_hallucinations", False),
            "hallucination_check": hallucination_result,
            "citation_check": citation_result,
            "overall_confidence": overall_confidence,
            "warnings": warnings,
        }
