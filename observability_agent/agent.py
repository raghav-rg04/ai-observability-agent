"""AI Observability & Predictive Diagnostics Agent with 5 GCP Service Tools and Workload-Aware Token Optimization."""

import os
import google.auth
import google.auth.transport.requests
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import StreamableHTTPConnectionParams

from observability_agent.config import (
    CLOUD_RUN_TOOLS,
    COMPUTE_TOOLS,
    GEMINI_MODEL,
    LOCATION,
    LOGGING_FILTER_BOTH,
    LOGGING_FILTER_CLOUD_RUN,
    LOGGING_FILTER_COMPUTE_ENGINE,
    LOGGING_TOOLS,
    METRIC_CLOUD_RUN_LATENCY,
    METRIC_CLOUD_RUN_REQUEST_COUNT,
    METRIC_GCE_CPU_UTILIZATION,
    MONITORING_TOOLS,
    OBSERVABILITY_LOOKBACK_HOURS,
    PROJECT_ID,
    SCOPED_RESOURCE_TYPES,
    SERVICE_HEALTH_TOOLS,
    US_REGIONS,
)
from observability_agent.sanitizer import SanitizedMcpToolset

# Configure Vertex AI SDK environment
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
if PROJECT_ID:
    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID


def _get_auth_headers(ctx=None) -> dict[str, str]:
    """Dynamically refresh credentials and return authorization headers."""
    credentials, _ = google.auth.default()
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    headers = {
        "Authorization": f"Bearer {credentials.token}",
    }
    if PROJECT_ID:
        headers["x-goog-user-project"] = PROJECT_ID
    return headers


# -------------------------------------------------------------------------
# Define the 5 Specialized Domain Sub-Agents with Token-Optimized Sanitized Toolsets
# -------------------------------------------------------------------------

auth_headers = _get_auth_headers()

# 1. Personalized Service Health Service Tool (Scoped to Last 24 Hours)
health_toolset = SanitizedMcpToolset(
    domain="servicehealth",
    connection_params=StreamableHTTPConnectionParams(
        url="https://servicehealth.googleapis.com/mcp",
        headers=auth_headers,
    ),
    tool_filter=list(SERVICE_HEALTH_TOOLS),
    header_provider=_get_auth_headers,
)
service_health_agent = LlmAgent(
    name="service_health_service",
    description=(
        "Queries GCP Personalized Service Health to inspect active cloud platform "
        "outages, disruptions, and incident events in US regions from the last 24 hours."
    ),
    model=GEMINI_MODEL,
    instruction=(
        f"You are the Google Cloud Service Health specialist. Default project: `{PROJECT_ID}`. "
        f"US Regions: {', '.join(US_REGIONS)}. "
        f"TIMEFRAME CONSTRAINT: Check data ONLY for the last {OBSERVABILITY_LOOKBACK_HOURS} hours. "
        "Query active platform incidents and project events using `list_project_events`. "
        "Report active disruptions, impact status, and affected Google Cloud products within this 24-hour window.\n"
        "OUTPUT FORMAT: Return concise bullet points or a markdown table with zero conversational filler."
    ),
    tools=[health_toolset],
)

# 2. Compute Engine Service Tool
compute_toolset = SanitizedMcpToolset(
    domain="compute",
    connection_params=StreamableHTTPConnectionParams(
        url="https://compute.googleapis.com/mcp",
        headers=auth_headers,
    ),
    tool_filter=list(COMPUTE_TOOLS),
    header_provider=_get_auth_headers,
)
compute_engine_agent = LlmAgent(
    name="compute_engine_service",
    description=(
        "Queries Google Compute Engine to inspect VM instances, operational status, "
        "machine types, and attached disks across US zones and regions."
    ),
    model=GEMINI_MODEL,
    instruction=(
        f"You are the Google Compute Engine specialist. Default project: `{PROJECT_ID}`. "
        f"US Regions: {', '.join(US_REGIONS)}. "
        "Query VM instances using `list_instances` and inspect basic info using `get_instance_basic_info`. "
        "Return the list of VMs, their zones, statuses (RUNNING/TERMINATED), and machine types.\n"
        "OUTPUT FORMAT: Return concise structured facts or a table with zero conversational filler."
    ),
    tools=[compute_toolset],
)

# 3. Cloud Run Service Tool
run_toolset = SanitizedMcpToolset(
    domain="run",
    connection_params=StreamableHTTPConnectionParams(
        url="https://run.googleapis.com/mcp",
        headers=auth_headers,
    ),
    tool_filter=list(CLOUD_RUN_TOOLS),
    header_provider=_get_auth_headers,
)
cloud_run_agent = LlmAgent(
    name="cloud_run_service",
    description=(
        "Queries Google Cloud Run to list and inspect serverless container services, "
        "serving URIs, revisions, and configurations across US regions."
    ),
    model=GEMINI_MODEL,
    instruction=(
        f"You are the Google Cloud Run specialist. Default project: `{PROJECT_ID}`. "
        f"US Regions: {', '.join(US_REGIONS)}. "
        f"Query Cloud Run services using `list_services` with project='{PROJECT_ID}' across US regions. "
        "Inspect service details, URLs, container images, and conditions using `get_service`.\n"
        "OUTPUT FORMAT: Return concise structured facts or a table with zero conversational filler."
    ),
    tools=[run_toolset],
)

# 4. Cloud Logging Service Tool (Workload-Scoped to Cloud Run, Compute Engine, or Both)
logging_toolset = SanitizedMcpToolset(
    domain="logging",
    connection_params=StreamableHTTPConnectionParams(
        url="https://logging.googleapis.com/mcp",
        headers=auth_headers,
    ),
    tool_filter=list(LOGGING_TOOLS),
    header_provider=_get_auth_headers,
)
cloud_logging_agent = LlmAgent(
    name="cloud_logging_service",
    description=(
        "Queries Google Cloud Logging for the last 24 hours scoped to Cloud Run, Compute Engine, or both. "
        "Inspects error logs and exceptions to analyze root causes and provide remediation recommendations."
    ),
    model=GEMINI_MODEL,
    instruction=(
        f"You are the Google Cloud Logging root-cause analysis specialist. Default project: `{PROJECT_ID}`.\n"
        f"MANDATORY SCOPING & TIMEFRAME RULES:\n"
        f"1. Timeframe: Check log entries ONLY for the last {OBSERVABILITY_LOOKBACK_HOURS} hours.\n"
        "2. Workload Scope Filtering:\n"
        f"   - If target is Cloud Run: filter with `{LOGGING_FILTER_CLOUD_RUN}`\n"
        f"   - If target is Compute Engine: filter with `{LOGGING_FILTER_COMPUTE_ENGINE}`\n"
        f"   - If target is both: filter with `{LOGGING_FILTER_BOTH}`\n"
        "3. Severity Filter: Query ONLY entries with errors and exceptions (`severity >= ERROR`).\n"
        "4. Root Cause & Recommendations: For any errors or exceptions found:\n"
        "   - Detail the error message, exception type, and stack trace.\n"
        "   - Perform a thorough root-cause analysis.\n"
        "   - Provide actionable remediation recommendations to resolve and prevent the issue.\n"
        "OUTPUT FORMAT: Return concise structured bullet points for each error with its root cause and recommendations."
    ),
    tools=[logging_toolset],
)

# 5. Cloud Monitoring Service Tool (Workload-Scoped to Cloud Run, Compute Engine, or Both)
monitoring_toolset = SanitizedMcpToolset(
    domain="monitoring",
    connection_params=StreamableHTTPConnectionParams(
        url="https://monitoring.googleapis.com/mcp",
        headers=auth_headers,
    ),
    tool_filter=list(MONITORING_TOOLS),
    header_provider=_get_auth_headers,
)
cloud_monitoring_agent = LlmAgent(
    name="cloud_monitoring_service",
    description=(
        "Queries Google Cloud Monitoring for the last 24 hours scoped to Cloud Run, Compute Engine, or both. "
        "Inspects telemetry (latencies, request counts, CPU utilization) and alert policies."
    ),
    model=GEMINI_MODEL,
    instruction=(
        f"You are the Google Cloud Monitoring specialist. Default project: `{PROJECT_ID}`.\n"
        f"MANDATORY SCOPING & TIMEFRAME RULES:\n"
        f"1. Timeframe: Query time-series telemetry ONLY for the last {OBSERVABILITY_LOOKBACK_HOURS} hours.\n"
        "2. Workload-Specific Metrics:\n"
        f"   - If target is Cloud Run: query `{METRIC_CLOUD_RUN_LATENCY}` and `{METRIC_CLOUD_RUN_REQUEST_COUNT}`.\n"
        f"   - If target is Compute Engine: query `{METRIC_GCE_CPU_UTILIZATION}`.\n"
        f"   - If target is both: query both Cloud Run and Compute Engine metrics.\n"
        "3. Time-Series Query: Use `list_timeseries` or `query_range` to examine trends and detect latency spikes or CPU saturation (>90%).\n"
        "4. Alert Policies: Inspect active alerts and policies via `list_alert_policies` / `list_alerts`.\n"
        "OUTPUT FORMAT: Return concise metric summary points or a table with zero conversational filler."
    ),
    tools=[monitoring_toolset],
)

# Exactly 5 Service Tools exposed to Gemini Root Orchestrator
service_tools = [
    AgentTool(agent=service_health_agent),
    AgentTool(agent=compute_engine_agent),
    AgentTool(agent=cloud_run_agent),
    AgentTool(agent=cloud_logging_agent),
    AgentTool(agent=cloud_monitoring_agent),
]

# -------------------------------------------------------------------------
# Root Orchestrator Instructions (Pruned & Token-Optimized)
# -------------------------------------------------------------------------

AGENT_INSTRUCTIONS = f"""You are the AI Observability & Predictive Diagnostics Orchestrator for Google Cloud (Project: `{PROJECT_ID}`).
Coordinate specialized service tools to inspect platform health, VM instances, Cloud Run services, logs, and telemetry.

WORKLOAD CONFIRMATION PROTOCOL FOR LOGGING & MONITORING:
- When a user query requires analyzing logs, errors, or monitoring metrics, you MUST know whether the scope is **Cloud Run**, **Compute Engine**, or **both**.
- IF the user's prompt DOES NOT explicitly specify the target service (e.g., "Check errors in my project", "Show me error logs", "Analyze telemetry/performance", "Run a diagnostic check"):
  -> DO NOT call `cloud_logging_service` or `cloud_monitoring_service` yet!
  -> First, ask the user to clarify: "Would you like me to analyze logs and metrics for **Cloud Run**, **Compute Engine**, or **both**?"
- IF the user's prompt explicitly states the target service (e.g., "Check error logs for Cloud Run" or "Show VM CPU utilization") OR after the user answers your clarification:
  -> Call `cloud_logging_service` or `cloud_monitoring_service` specifically specifying that targeted scope ("Cloud Run", "Compute Engine", or "both").
  -> Do NOT query workloads outside the user's selected scope.

SYNTHESIS & REPORTING:
- When reporting diagnostic findings, structure output with:
  - **Affected Services Table**:
    | Service Name | GCP Project Resource Name | Region | Failure / Outage Reason |
    | --- | --- | --- | --- |
  - **Root Cause Analysis & Actionable Recommendations** for identified errors, exceptions, or metric anomalies.

SECURITY & SAFETY BOUNDARY:
- You operate strictly with read-only inspection tools.
- Do NOT perform any destructive or mutation operations.
"""

root_agent = LlmAgent(
    model=GEMINI_MODEL,
    name="ai_observability_agent",
    instruction=AGENT_INSTRUCTIONS,
    tools=service_tools,
)
