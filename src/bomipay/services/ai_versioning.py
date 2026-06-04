"""
AI Prompt versioning and management.

Tracks:
- Prompt template versions
- Model names
- Retrieval sources used
- Safety flags
"""
import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_prompt_version import AIPromptVersion

logger = logging.getLogger("bomipay")

# Current version
CURRENT_PROMPT_VERSION = 1

# Prompt templates by version
PROMPT_TEMPLATES = {
    1: """
You are an AI assistant analyzing payment and financial data for merchant operations.
Your role is to provide factual analysis grounded in retrieved data.

Rules:
1. ONLY use data from the context provided. Do not invent facts.
2. Always cite specific records (ID, type) when making claims.
3. Distinguish between facts (from data) and suggestions (your reasoning).
4. For numeric claims, state the data completeness (e.g., "based on last 30 days").
5. Highlight missing data that would improve accuracy.
6. Use confidence language:
   - <60 BPS: "Cannot be confident about..."
   - 60-80 BPS: "Based on available data..."
   - >80 BPS: "Clear evidence from..."

Context provided:
{context_summary}

User query: {query}

Respond with:
1. Direct answer to the query
2. Key data points supporting the answer
3. Any limitations or caveats in the analysis
""".strip(),
}

# Safety flags by version
SAFETY_FLAGS = {
    1: {
        "detect_hallucinations": True,
        "validate_citations": True,
        "require_confidence_language": True,
        "max_speculation_percentage": 20,
    }
}

# Retrieval sources by version
RETRIEVAL_SOURCES = {
    1: [
        "incidents",
        "transactions",
        "reconciliation_results",
        "bank_statements",
        "provider_health",
        "sync_jobs",
        "money_at_risk",
    ]
}


class AIPromptVersionManager:
    """Manage prompt versioning and retrieval configuration."""

    @staticmethod
    async def get_current_version(db: AsyncSession) -> AIPromptVersion:
        """Get the current active prompt version."""
        result = await db.execute(
            select(AIPromptVersion)
            .order_by(AIPromptVersion.version.desc())
            .limit(1)
        )
        existing = result.scalars().first()

        if existing:
            return existing

        # Create default version if none exists
        return await AIPromptVersionManager.create_version(
            db,
            model_name="gpt-3.5-turbo",
            prompt_template=PROMPT_TEMPLATES.get(1, ""),
            retrieval_sources=RETRIEVAL_SOURCES.get(1, []),
            safety_flags=SAFETY_FLAGS.get(1, {}),
        )

    @staticmethod
    async def create_version(
        db: AsyncSession,
        model_name: str,
        prompt_template: str,
        retrieval_sources: List[str],
        safety_flags: Optional[Dict] = None,
    ) -> AIPromptVersion:
        """
        Create a new prompt version.

        Args:
            db: Database session
            model_name: LLM model name
            prompt_template: Template with {query}, {context_summary} placeholders
            retrieval_sources: List of data sources to retrieve
            safety_flags: Safety configuration

        Returns:
            Created AIPromptVersion
        """
        # Get next version number
        result = await db.execute(
            select(AIPromptVersion)
            .order_by(AIPromptVersion.version.desc())
            .limit(1)
        )
        last = result.scalars().first()
        next_version = (last.version + 1) if last else 1

        version = AIPromptVersion(
            version=next_version,
            model_name=model_name,
            prompt_template=prompt_template,
            retrieval_sources=retrieval_sources,
            safety_flags=safety_flags or {},
        )

        db.add(version)
        await db.flush()

        logger.info(
            "ai_prompt_version.created",
            extra={
                "version": next_version,
                "model_name": model_name,
            }
        )

        return version

    @staticmethod
    async def get_version(
        db: AsyncSession,
        version_number: int,
    ) -> Optional[AIPromptVersion]:
        """Get a specific prompt version."""
        result = await db.execute(
            select(AIPromptVersion).where(AIPromptVersion.version == version_number)
        )
        return result.scalars().first()

    @staticmethod
    async def list_versions(db: AsyncSession) -> List[AIPromptVersion]:
        """List all prompt versions."""
        result = await db.execute(
            select(AIPromptVersion).order_by(AIPromptVersion.version.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def build_prompt(
        template: str,
        query: str,
        context_summary: str,
    ) -> str:
        """
        Build final prompt by substituting template variables.

        Args:
            template: Prompt template
            query: User query
            context_summary: Summary of retrieved context

        Returns:
            Final prompt
        """
        return template.format(
            query=query,
            context_summary=context_summary,
        )

    @staticmethod
    def get_default_retrieval_sources() -> List[str]:
        """Get default retrieval sources."""
        return RETRIEVAL_SOURCES.get(CURRENT_PROMPT_VERSION, [])

    @staticmethod
    def get_default_safety_flags() -> Dict:
        """Get default safety flags."""
        return SAFETY_FLAGS.get(CURRENT_PROMPT_VERSION, {})
