"""AI analysis endpoints — Claude-powered contextual insights."""

import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.auth import get_current_user
from api.ssl_helper import get_ssl_context

logger = logging.getLogger("siteline")

router = APIRouter(prefix="/api", tags=["ai"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

AI_SYSTEM_PROMPTS = {
    "executive_summary": (
        "You are a South African property development analyst working for Siteline. Given a property's data, "
        "write a clear 2-3 sentence plain-English interpretation of the overall development "
        "potential. Mention the biodiversity risk level, developable percentage, and Green Star "
        "rating in practical terms a property developer would understand. Do NOT give legal or "
        "investment advice. Do NOT speculate beyond the data provided. Stay under 100 words."
    ),
    "biodiversity": (
        "You are a Cape Town biodiversity specialist. Given the CBA/ESA designations overlapping "
        "a property, explain what they mean for development in 2-3 sentences. Reference the City "
        "of Cape Town BioNet and NEMA regulations where relevant. Do NOT give legal advice. "
        "Do NOT speculate beyond the data. Stay under 120 words."
    ),
    "heritage": (
        "You are a South African heritage consultant. Given heritage site records near a property, "
        "explain the implications for development in 2-3 sentences. Reference Section 34 of the "
        "NHRA and Heritage Western Cape where relevant. Do NOT give legal advice. Stay under 100 words."
    ),
    "netzero": (
        "You are a Green Star SA sustainability consultant. Given a property's net zero scorecard "
        "scores (energy, water, ecology, location, materials out of their maximums), interpret what "
        "the rating means practically. Suggest which score category has the most room for improvement. "
        "Do NOT give investment advice. Stay under 120 words."
    ),
    "solar": (
        "You are a Cape Town solar energy analyst. Given a property's solar potential data (system "
        "size, annual generation, net zero ratio, carbon offset, payback period), provide a practical "
        "assessment of whether rooftop solar is worthwhile for this property. Reference Cape Town's "
        "average 5.5 peak sun hours and SSEG programme. Do NOT give investment advice. Stay under 120 words."
    ),
    "water": (
        "You are a Cape Town water resilience analyst. Given a property's rainwater harvesting data "
        "(rainfall zone, annual harvest, demand met percentage, tank size), assess the water "
        "resilience potential. Reference Cape Town's Day Zero experience and seasonal rainfall "
        "patterns. Do NOT give investment advice. Stay under 120 words."
    ),
    "actions": (
        "You are a South African development planning advisor. Given a list of recommended actions "
        "with priorities, categories, and timelines, provide a concise plain-English summary of "
        "the most critical next steps and why they matter. Group related actions together. "
        "Do NOT give legal or investment advice. Stay under 130 words."
    ),
}


class AiAnalyzeRequest(BaseModel):
    section: str
    context: dict


@router.post("/ai/analyze")
async def ai_analyze(req: AiAnalyzeRequest, _user: dict = Depends(get_current_user)):
    """Get AI-powered analysis for a report section."""
    system_prompt = AI_SYSTEM_PROMPTS.get(req.section)
    if not system_prompt:
        raise HTTPException(status_code=400, detail=f"Unknown section: {req.section}")

    if not ANTHROPIC_API_KEY:
        return {"analysis": None, "error": "AI not configured — set ANTHROPIC_API_KEY"}

    user_content = json.dumps(req.context, default=str, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=15.0, verify=get_ssl_context()) as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text_out = data["content"][0]["text"].strip()
            return {"analysis": text_out}
    except Exception as e:
        logger.warning("Anthropic API error: %s", e)
        return {"analysis": None, "error": "AI temporarily unavailable"}
