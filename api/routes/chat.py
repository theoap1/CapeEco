"""
AI Chat endpoint — SSE streaming with tool calling.

Implements an agent loop:
1. Receive user message + history
2. Send to Claude with tool definitions
3. If tool call → execute → send result back → get next response
4. Stream text back to client via SSE
"""

import json
import logging
import os
from decimal import Decimal
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import get_current_user
from api.tools import TOOL_DEFINITIONS, execute_tool
from api.ssl_helper import get_ssl_context

logger = logging.getLogger("siteline")

router = APIRouter(prefix="/api/ai", tags=["chat"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

SYSTEM_PROMPT = """You are Siteline AI, an expert property development intelligence assistant for South African property developers.

You have access to a comprehensive database of Cape Town properties with 834,000+ land parcels, biodiversity data (BioNet CBA/ESA classifications), heritage sites, zoning information, and valuation data.

Your capabilities:
- Search and analyze any property in Cape Town by address or ERF number
- Calculate biodiversity offset requirements and development constraints
- Assess solar potential, water harvesting, and Green Star sustainability ratings
- Compare property valuations within a radius or suburb
- Generate constraint maps showing developable vs protected areas
- Calculate development potential: buildable envelope, max GFA, estimated units, parking, and zoning constraints per CTZS Table A
- Assess crime risk, load shedding impact, and municipal financial health

When a user asks about a property:
1. If a property is already selected (property ID provided in context below), use that ID directly — do NOT search for it again.
2. Only use search_property if NO property is selected and the user mentions an address or ERF number.
3. Then get details with get_property_details using the property ID.
4. Run relevant analyses based on what they asked.
5. If they ask "what can I build" or about development potential, use get_development_potential.

Always provide practical, developer-focused insights. Reference relevant South African regulations (NEMA, NHRA, CoCT BioNet) where applicable. Be concise but thorough.

Do NOT give legal or investment advice. State this clearly if asked for either.
Format numbers clearly (use commas for thousands, round appropriately).
Use ZAR for currency values."""


def _to_anthropic_tools(deepseek_tools: list[dict]) -> list[dict]:
    """Convert DeepSeek/OpenAI tool format to Anthropic tool format."""
    tools = []
    for t in deepseek_tools:
        fn = t["function"]
        tools.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return tools


ANTHROPIC_TOOLS = _to_anthropic_tools(TOOL_DEFINITIONS)


class ChatRequest(BaseModel):
    messages: list[dict]
    property_id: int | None = None


def _json_serializer(obj):
    """Handle non-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return str(obj)


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert frontend message format to Anthropic format.

    Anthropic requires alternating user/assistant messages.
    Consecutive same-role messages get merged.
    """
    anthropic_messages = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            continue  # system is handled separately
        # Merge consecutive same-role messages
        if anthropic_messages and anthropic_messages[-1]["role"] == role:
            prev = anthropic_messages[-1]["content"]
            if isinstance(prev, str):
                anthropic_messages[-1]["content"] = prev + "\n" + content
            else:
                anthropic_messages[-1]["content"] = str(prev) + "\n" + content
        else:
            anthropic_messages.append({"role": role, "content": content})

    # Ensure first message is from user
    if anthropic_messages and anthropic_messages[0]["role"] != "user":
        anthropic_messages.insert(0, {"role": "user", "content": "Hello"})

    return anthropic_messages


def _build_system_prompt(property_id: int | None) -> str:
    """Build the system prompt, optionally injecting selected property context."""
    if not property_id:
        return SYSTEM_PROMPT

    # Fetch basic property info to inject into prompt
    try:
        from api.tools import execute_tool
        prop = execute_tool("get_property_details", {"property_id": property_id})
        if prop and "error" not in prop:
            label = prop.get("full_address") or f"ERF {prop.get('erf_number', '?')}, {prop.get('suburb', '?')}"
            # Include key details so the AI doesn't even need to call get_property_details for basics
            details_lines = [f"Address: {label}"]
            for key in ("erf_number", "suburb", "zoning", "zoning_index", "area_sqm", "ward"):
                val = prop.get(key)
                if val is not None:
                    details_lines.append(f"{key}: {val}")
            details_str = "\n".join(details_lines)
            context = (
                f"\n\n=== SELECTED PROPERTY (ALREADY IDENTIFIED) ===\n"
                f"The user has already selected this property on the map. DO NOT search for it.\n"
                f"Property ID: {property_id}\n"
                f"{details_str}\n"
                f"Use property_id={property_id} directly with get_property_details, get_development_potential, "
                f"analyze_biodiversity, analyze_netzero, and all other tools. "
                f"NEVER call search_property for this property — you already have the ID.\n"
                f"=== END SELECTED PROPERTY ==="
            )
            return SYSTEM_PROMPT + context
    except Exception as e:
        logger.warning("Failed to pre-fetch property %s: %s", property_id, e)

    # Fallback: just tell the model the ID
    return SYSTEM_PROMPT + (
        f"\n\n=== SELECTED PROPERTY (ALREADY IDENTIFIED) ===\n"
        f"The user has already selected property ID {property_id} on the map. "
        f"Use property_id={property_id} directly with all tools. NEVER call search_property for this property.\n"
        f"=== END SELECTED PROPERTY ==="
    )


async def _stream_chat(messages: list[dict], property_id: int | None):
    """Generator that yields SSE events."""

    anthropic_messages = _convert_messages(messages)
    system_prompt = _build_system_prompt(property_id)
    max_iterations = 5  # prevent infinite tool loops

    for iteration in range(max_iterations):
        try:
            async with httpx.AsyncClient(timeout=60.0, verify=get_ssl_context()) as client:
                payload = {
                    "model": ANTHROPIC_MODEL,
                    "system": system_prompt,
                    "messages": anthropic_messages,
                    "max_tokens": 1024,
                    "tools": ANTHROPIC_TOOLS,
                }

                resp = await client.post(
                    ANTHROPIC_URL,
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            stop_reason = data.get("stop_reason", "end_turn")
            content_blocks = data.get("content", [])

            # Check if the model wants to call tools
            if stop_reason == "tool_use":
                # Build the assistant message with all content blocks
                anthropic_messages.append({"role": "assistant", "content": content_blocks})

                tool_result_blocks = []

                for block in content_blocks:
                    if block["type"] == "text" and block.get("text"):
                        # Stream any text before tool calls
                        text_content = block["text"]
                        chunk_size = 20
                        for i in range(0, len(text_content), chunk_size):
                            chunk = text_content[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

                    elif block["type"] == "tool_use":
                        fn_name = block["name"]
                        fn_args = block["input"]
                        tool_use_id = block["id"]

                        # Stream tool call indicator
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': fn_name, 'args': fn_args})}\n\n"

                        # Execute the tool
                        try:
                            result = execute_tool(fn_name, fn_args)
                        except Exception as e:
                            logger.warning("Tool execution error: %s %s", fn_name, e)
                            result = {"error": str(e)}

                        result_str = json.dumps(result, default=_json_serializer)

                        # Stream tool result indicator
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': fn_name, 'result': result})}\n\n"

                        # Send context update to frontend
                        context_data = _extract_context(fn_name, result)
                        if context_data:
                            yield f"data: {json.dumps({'type': 'context', 'data': context_data}, default=_json_serializer)}\n\n"

                        # Add tool result block
                        tool_result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_str,
                        })

                # Add all tool results as a user message
                anthropic_messages.append({"role": "user", "content": tool_result_blocks})

                # Continue the loop — model will process tool results
                continue

            else:
                # Model returned final response — stream text
                for block in content_blocks:
                    if block["type"] == "text" and block.get("text"):
                        text_content = block["text"]
                        chunk_size = 20
                        for i in range(0, len(text_content), chunk_size):
                            chunk = text_content[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body_preview = e.response.text[:500] if e.response else ""
            logger.error("Anthropic API error (HTTP %s): %s", status, body_preview)
            if status == 401:
                msg = "AI API key is invalid or expired. Check your ANTHROPIC_API_KEY."
            elif status == 429:
                msg = "AI rate limit reached. Please wait a moment and try again."
            elif status == 403:
                msg = f"Anthropic API rejected the request (403 Forbidden). Response: {body_preview[:200]}"
            elif status == 529:
                msg = "Anthropic API is temporarily overloaded. Please try again in a moment."
            else:
                msg = f"AI service error (HTTP {status}): {body_preview[:200]}"
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        except Exception as e:
            err_str = str(e)
            logger.error("Chat error: %s", e, exc_info=True)
            if "CERTIFICATE_VERIFY_FAILED" in err_str:
                msg = "SSL certificate error connecting to AI service. Set SKIP_SSL_VERIFY=1 and restart the server."
            else:
                msg = f"An error occurred: {err_str}"
            yield f"data: {json.dumps({'type': 'text', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

    # Max iterations reached
    yield f"data: {json.dumps({'type': 'text', 'content': 'I reached the maximum number of analysis steps. Here is what I found so far.'})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _extract_context(tool_name: str, result: dict) -> dict | None:
    """Extract context data from tool results for the frontend context panel."""
    if tool_name == "get_property_details" and "error" not in result:
        return {
            "property": result,
            "biodiversity": result.get("biodiversity"),
        }
    elif tool_name == "analyze_netzero" and "error" not in result:
        return {
            "analysis": {
                "netzero": result.get("scorecard"),
                "solar": result.get("solar"),
                "water": result.get("water"),
            }
        }
    elif tool_name == "analyze_biodiversity" and "error" not in result:
        return {
            "analysis": {
                "biodiversity": result,
            }
        }
    elif tool_name == "get_crime_stats" and "error" not in result:
        return {
            "analysis": {
                "crime": result,
            }
        }
    elif tool_name == "get_loadshedding" and "error" not in result:
        return {
            "analysis": {
                "loadshedding": result,
            }
        }
    elif tool_name == "get_municipal_health" and "error" not in result:
        return {
            "analysis": {
                "municipal": result,
            }
        }
    elif tool_name == "compare_properties" and "error" not in result:
        return {
            "analysis": {
                "comparison": result,
            }
        }
    elif tool_name == "get_constraint_map" and "error" not in result:
        return {
            "constraintMap": result.get("geojson", result),
        }
    elif tool_name == "get_development_potential" and "error" not in result:
        context = {
            "analysis": {
                "development_potential": result,
            }
        }
        # If site plan GeoJSON is included, add it for map rendering
        if result.get("site_plan_geojson"):
            context["sitePlan"] = result["site_plan_geojson"]
        return context
    return None


@router.post("/chat")
async def ai_chat(req: ChatRequest, _user: dict = Depends(get_current_user)):
    """Stream AI chat responses with tool calling."""
    if not req.messages:
        raise HTTPException(400, "Messages cannot be empty")

    return StreamingResponse(
        _stream_chat(req.messages, req.property_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
