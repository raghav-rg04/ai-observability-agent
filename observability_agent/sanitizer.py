"""Sanitizer and Truncation Module for MCP Tool Responses to Minimize Token Consumption."""

import json
from typing import Any, List, Optional
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from observability_agent.config import (
    MAX_LOG_ENTRIES,
    MAX_LOG_MESSAGE_CHARS,
    MAX_TIMESERIES_POINTS,
)


def _truncate_str(val: Any, max_len: int = MAX_LOG_MESSAGE_CHARS) -> Any:
    """Truncate long strings to max_len characters."""
    if isinstance(val, str) and len(val) > max_len:
        return val[:max_len] + "... [truncated]"
    return val


def sanitize_logging_payload(data: Any) -> Any:
    """Sanitize Cloud Logging response to keep only essential error fields."""
    if not isinstance(data, dict):
        return data

    entries = data.get("entries") or data.get("logEntries")
    if not isinstance(entries, list):
        return data

    cleaned_entries = []
    for entry in entries[:MAX_LOG_ENTRIES]:
        if not isinstance(entry, dict):
            continue

        # Extract message / payload
        msg = ""
        if "textPayload" in entry:
            msg = entry["textPayload"]
        elif "jsonPayload" in entry and isinstance(entry["jsonPayload"], dict):
            jp = entry["jsonPayload"]
            error_details = []
            for k in ["message", "error", "exception", "stack_trace", "status", "description"]:
                if k in jp:
                    error_details.append(f"{k}: {jp[k]}")
            msg = "\n".join(error_details) if error_details else json.dumps(jp)
        elif "protoPayload" in entry and isinstance(entry["protoPayload"], dict):
            pp = entry["protoPayload"]
            msg = pp.get("status", {}).get("message") or pp.get("response", {}).get("error") or str(pp)

        res_info = {}
        if "resource" in entry and isinstance(entry["resource"], dict):
            res = entry["resource"]
            res_info["type"] = res.get("type")
            if "labels" in res and isinstance(res["labels"], dict):
                res_info["labels"] = {
                    k: v
                    for k, v in res["labels"].items()
                    if k in [
                        "service_name",
                        "instance_id",
                        "zone",
                        "location",
                        "configuration_name",
                        "revision_name",
                    ]
                }

        cleaned_entry = {
            "timestamp": entry.get("timestamp"),
            "severity": entry.get("severity"),
            "resource": res_info,
            "message": _truncate_str(msg, MAX_LOG_MESSAGE_CHARS),
        }
        cleaned_entries.append(cleaned_entry)

    return {
        "total_returned": len(entries),
        "retained_entries": len(cleaned_entries),
        "entries": cleaned_entries,
    }


def sanitize_monitoring_payload(data: Any) -> Any:
    """Sanitize Cloud Monitoring time-series responses to keep recent points."""
    if not isinstance(data, dict):
        return data

    series_list = data.get("timeSeries") or data.get("timeseries") or data.get("time_series")
    if not isinstance(series_list, list):
        return data

    cleaned_series = []
    for s in series_list[:15]:
        if not isinstance(s, dict):
            continue

        metric_type = s.get("metric", {}).get("type")
        metric_labels = s.get("metric", {}).get("labels", {})
        res_type = s.get("resource", {}).get("type")
        res_labels = s.get("resource", {}).get("labels", {})

        # Extract recent points
        raw_points = s.get("points", [])
        cleaned_points = []
        for pt in raw_points[:MAX_TIMESERIES_POINTS]:
            if not isinstance(pt, dict):
                continue
            val_dict = pt.get("value", {})
            val = (
                val_dict.get("doubleValue")
                or val_dict.get("int64Value")
                or val_dict.get("distributionValue", {}).get("mean")
                or val_dict.get("stringValue")
            )
            time_str = pt.get("interval", {}).get("endTime") or pt.get("interval", {}).get("startTime")
            cleaned_points.append({"time": time_str, "value": val})

        cleaned_series.append({
            "metric": metric_type,
            "metric_labels": metric_labels,
            "resource": {"type": res_type, "labels": res_labels},
            "recent_points": cleaned_points,
        })

    return {"timeSeries": cleaned_series}


def sanitize_compute_payload(data: Any) -> Any:
    """Sanitize Compute Engine instances and disk responses."""
    if not isinstance(data, dict):
        return data

    if "items" in data and isinstance(data["items"], list):
        cleaned_items = []
        for inst in data["items"]:
            if not isinstance(inst, dict):
                continue
            cleaned_items.append({
                "name": inst.get("name"),
                "status": inst.get("status"),
                "zone": inst.get("zone", "").split("/")[-1] if "/" in inst.get("zone", "") else inst.get("zone"),
                "machineType": (
                    inst.get("machineType", "").split("/")[-1]
                    if "/" in inst.get("machineType", "")
                    else inst.get("machineType")
                ),
                "cpuPlatform": inst.get("cpuPlatform"),
            })
        return {"instances": cleaned_items}

    # If single instance
    if "name" in data and "status" in data and "machineType" in data:
        return {
            "name": data.get("name"),
            "status": data.get("status"),
            "zone": data.get("zone", "").split("/")[-1] if "/" in data.get("zone", "") else data.get("zone"),
            "machineType": (
                data.get("machineType", "").split("/")[-1]
                if "/" in data.get("machineType", "")
                else data.get("machineType")
            ),
            "cpuPlatform": data.get("cpuPlatform"),
        }

    return data


def sanitize_cloud_run_payload(data: Any) -> Any:
    """Sanitize Cloud Run service responses."""
    if not isinstance(data, dict):
        return data

    if "services" in data and isinstance(data["services"], list):
        cleaned_services = []
        for s in data["services"]:
            if not isinstance(s, dict):
                continue
            item = {
                "name": s.get("name", "").split("/")[-1] if "/" in s.get("name", "") else s.get("name"),
                "uri": s.get("uri"),
                "createTime": s.get("createTime"),
                "updateTime": s.get("updateTime"),
            }
            if "template" in s and "containers" in s["template"]:
                imgs = [c.get("image") for c in s["template"]["containers"] if "image" in c]
                if imgs:
                    item["images"] = imgs
            cleaned_services.append(item)
        return {"services": cleaned_services}

    if "name" in data and "uri" in data:
        return {
            "name": data.get("name", "").split("/")[-1] if "/" in data.get("name", "") else data.get("name"),
            "uri": data.get("uri"),
            "createTime": data.get("createTime"),
            "updateTime": data.get("updateTime"),
        }

    return data


def sanitize_service_health_payload(data: Any) -> Any:
    """Sanitize Service Health incident events."""
    if not isinstance(data, dict):
        return data

    events = data.get("events") or data.get("projectEvents")
    if isinstance(events, list):
        cleaned_events = []
        for ev in events[:10]:
            if not isinstance(ev, dict):
                continue
            cleaned_events.append({
                "name": ev.get("name"),
                "title": ev.get("title"),
                "state": ev.get("state"),
                "detailedState": ev.get("detailedState"),
                "eventScope": ev.get("eventScope"),
                "impacts": ev.get("impacts"),
                "startTime": ev.get("startTime"),
                "updateTime": ev.get("updateTime"),
            })
        return {"events": cleaned_events}

    return data


DOMAIN_SANITIZERS = {
    "logging": sanitize_logging_payload,
    "monitoring": sanitize_monitoring_payload,
    "compute": sanitize_compute_payload,
    "run": sanitize_cloud_run_payload,
    "servicehealth": sanitize_service_health_payload,
}


def sanitize_tool_response(domain: str, tool_name: str, raw_result: Any) -> Any:
    """Sanitizes raw MCP tool response before it reaches LLM context."""
    if not isinstance(raw_result, dict):
        return raw_result

    # If isError is true, return as-is
    if raw_result.get("isError") is True:
        return raw_result

    sanitizer = DOMAIN_SANITIZERS.get(domain)
    if not sanitizer:
        return raw_result

    # Process content array
    if "content" in raw_result and isinstance(raw_result["content"], list):
        new_content = []
        for item in raw_result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                try:
                    parsed_json = json.loads(text_val)
                    sanitized_json = sanitizer(parsed_json)
                    new_content.append({"type": "text", "text": json.dumps(sanitized_json, ensure_ascii=False)})
                except Exception:
                    new_content.append({"type": "text", "text": _truncate_str(text_val, MAX_LOG_MESSAGE_CHARS * 2)})
            else:
                new_content.append(item)
        raw_result["content"] = new_content

    if "structuredContent" in raw_result and isinstance(raw_result["structuredContent"], dict):
        raw_result["structuredContent"] = sanitizer(raw_result["structuredContent"])

    return raw_result


class SanitizedTool(BaseTool):
    """Wraps an MCP tool to intercept output and sanitize/prune payloads to minimize token consumption."""

    def __init__(self, inner_tool: BaseTool, domain: str):
        super().__init__(
            name=inner_tool.name,
            description=inner_tool.description,
        )
        self.inner_tool = inner_tool
        self.domain = domain

    def _get_declaration(self) -> types.FunctionDeclaration:
        return self.inner_tool._get_declaration()

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        raw_result = await self.inner_tool.run_async(args=args, tool_context=tool_context)
        return sanitize_tool_response(self.domain, self.inner_tool.name, raw_result)


class SanitizedMcpToolset(McpToolset):
    """McpToolset that wraps returned tools with SanitizedTool for payload truncation and token optimization."""

    def __init__(self, domain: str, **kwargs):
        super().__init__(**kwargs)
        self.domain = domain

    async def get_tools(self, readonly_context: Optional[ReadonlyContext] = None) -> List[BaseTool]:
        raw_tools = await super().get_tools(readonly_context=readonly_context)
        return [SanitizedTool(inner_tool=t, domain=self.domain) for t in raw_tools]
