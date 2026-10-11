"""Provider selection and a small, stateless OpenAI Responses client.

Claude remains supported through its SDK. OpenAI needs only the Python standard
library and OPENAI_API_KEY; neither provider borrows a developer's login.
"""
import asyncio
import copy
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
DEFAULT_OPENAI_MODEL = "gpt-6.1-sol"


def provider():
    selected = os.getenv("BUILDER_PROVIDER", "auto").lower()
    if selected not in {"auto", "claude", "openai"}:
        raise ValueError("BUILDER_PROVIDER must be auto, claude or openai")
    if selected == "auto":
        return "openai" if os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY") else "claude"
    return selected


def model_for(stage):
    return os.getenv(stage.upper() + "_MODEL") or (
        os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL) if provider() == "openai" else DEFAULT_CLAUDE_MODEL)


def cost_sum(*values):
    """An unknown invoice amount must not be reported as a free model call."""
    return None if any(v is None for v in values) else sum(values)


def cost_round(value, digits=4):
    return None if value is None else round(value, digits)


def cost_label(value):
    return "cost unavailable (see provider usage)" if value is None else "$%.2f" % value


def strict_schema(schema):
    """Make optional fields nullable for Structured Outputs, without changing input."""
    result = copy.deepcopy(schema)
    def visit(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            props = node.get("properties", {})
            if not props and node.get("additionalProperties") not in (None, False):
                raise ValueError("Open-ended object schemas need named properties")
            required = set(node.get("required", []))
            for key, value in props.items():
                visit(value)
                if key not in required:
                    props[key] = {"anyOf": [value, {"type": "null"}]}
            node["required"] = list(props)
            node["additionalProperties"] = False
        if "items" in node:
            visit(node["items"])
        for value in node.get("anyOf", []):
            visit(value)
    visit(result)
    return result


def restore_optional(value, schema):
    """Restore omitted optional fields; retain nulls allowed by the original schema."""
    if isinstance(value, dict):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        return {key: restore_optional(item, props.get(key, {})) for key, item in value.items()
                if not (item is None and key not in required and
                        "null" not in props.get(key, {}).get("type", []))}
    if isinstance(value, list):
        return [restore_optional(item, schema.get("items", {})) for item in value]
    return value


def validate_json(value, schema, path="$"):
    """Check the schema subset used by the builder, including required fields/enums."""
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "number": (int, float), "null": type(None)}
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        if not any(isinstance(value, kinds[t]) and not (
                t in {"integer", "number"} and isinstance(value, bool)) for t in types):
            raise ValueError(path + ": wrong JSON type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(path + ": invalid enum")
    if isinstance(value, dict):
        if set(schema.get("required", [])) - value.keys():
            raise ValueError(path + ": missing required fields")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and value.keys() - props.keys():
            raise ValueError(path + ": unexpected fields")
        for key, item in value.items():
            validate_json(item, props.get(key, {}), path + "." + key)
    elif isinstance(value, list):
        for item in value:
            validate_json(item, schema.get("items", {}), path + "[]")


def response_text(response):
    if response.get("status") != "completed":
        raise RuntimeError("OpenAI response did not complete: %s %s" % (
            response.get("status"), response.get("incomplete_details") or response.get("error") or ""))
    text = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise RuntimeError("OpenAI refused this request")
            if content.get("type") == "output_text":
                text.append(content.get("text", ""))
    return "\n".join(text)


def request_response(payload, timeout=180):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set; source your local env file")
    request = urllib.request.Request("https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + key,
                                                   "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=max(.1, timeout)) as result:
            response = json.load(result)
    except urllib.error.HTTPError as error:
        # No headers, request body or credentials in failures. Auth/quota failures
        # are not retried or silently switched to a different paid provider.
        try:
            detail = json.loads(error.read()).get("error", {})
            reason = str(detail.get("code") or detail.get("type") or "request_failed")
        except (ValueError, AttributeError):
            reason = "request_failed"
        raise RuntimeError("OpenAI HTTP %s (%s)" % (error.code, reason)) from None
    response_text(response)
    return response


def request_options(model, effort=None):
    return {"model": model, "store": False, "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": effort or os.getenv("OPENAI_REASONING_EFFORT", "medium")},
            "max_output_tokens": 24000}


async def ask_json_openai(prompt, system_prompt, schema, purpose, model, log, effort=None):
    info = {"model": model, "provider": "openai", "cost_usd": None, "seconds": 0.0,
            "turns": 0, "attempts": 0, "usage": {}, "responses": []}
    started = time.monotonic()
    last_error = ""
    for attempt in range(2):
        info["attempts"] += 1
        log("model call: %s | purpose: %s%s" % (model, purpose, " (JSON repair)" if attempt else ""))
        payload = request_options(model, effort)
        payload.update(instructions=system_prompt, input=prompt + (
            "\nReturn valid JSON; previous schema error: " + last_error if attempt else ""),
            text={"format": {"type": "json_schema", "name": "builder_result", "strict": True,
                             "schema": strict_schema(schema)}})
        response = await asyncio.to_thread(request_response, payload)
        usage = response.get("usage", {})
        info["responses"].append({"id": response.get("id"), "usage": usage})
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            info["usage"][name] = info["usage"].get(name, 0) + usage.get(name, 0)
        info["turns"] += 1
        log("model call result: %s | response_id=%s | usage=%s | %s" % (
            model, response.get("id"), json.dumps(usage), cost_label(None)))
        try:
            result = restore_optional(json.loads(response_text(response)), schema)
            validate_json(result, schema)
            info["seconds"] = time.monotonic() - started
            return result, info
        except (ValueError, TypeError) as error:
            last_error = str(error)
    raise RuntimeError("OpenAI returned invalid JSON after two attempts: " + last_error)
