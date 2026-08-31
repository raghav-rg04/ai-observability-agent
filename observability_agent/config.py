"""Configuration module for the AI Observability Agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# Environment & Model Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "my-first-demo-project-393105")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")

# Target US Regions for Workloads and Outage Monitoring
US_REGIONS = [
    "us-central1",
    "us-east1",
    "us-east4",
    "us-west1",
    "us-west2",
    "us-west3",
    "us-west4",
]

# Lookback Window & Scoped Workloads
OBSERVABILITY_LOOKBACK_HOURS = 24
SCOPED_RESOURCE_TYPES = [
    "cloud_run_revision",
    "gce_instance",
]

# Token Optimization & Truncation Limits
MAX_LOG_ENTRIES = 15
MAX_LOG_MESSAGE_CHARS = 800
MAX_TIMESERIES_POINTS = 10

# Standard Metric Descriptors (Scoped to Cloud Run & Compute Engine)
METRIC_CLOUD_RUN_LATENCY = "run.googleapis.com/request_latencies"
METRIC_CLOUD_RUN_REQUEST_COUNT = "run.googleapis.com/request_count"
METRIC_GCE_CPU_UTILIZATION = "compute.googleapis.com/instance/cpu/utilization"

# Standard Error Filter Templates for Cloud Logging
LOGGING_FILTER_CLOUD_RUN = 'resource.type = "cloud_run_revision" AND severity >= ERROR'
LOGGING_FILTER_COMPUTE_ENGINE = 'resource.type = "gce_instance" AND severity >= ERROR'
LOGGING_FILTER_BOTH = (
    'resource.type = ("cloud_run_revision" OR "gce_instance") AND severity >= ERROR'
)

# Domain-Specific Read-Only Tool Allowlists
SERVICE_HEALTH_TOOLS = {
    "list_project_events",
    "get_project_event",
}

COMPUTE_TOOLS = {
    "list_instances",
    "get_instance_basic_info",
    "list_disks",
    "get_disk_basic_info",
    "list_machine_types",
}

CLOUD_RUN_TOOLS = {
    "list_services",
    "get_service",
}

LOGGING_TOOLS = {
    "list_log_entries",
    "list_log_names",
}

MONITORING_TOOLS = {
    "list_timeseries",
    "query_range",
    "list_metric_descriptors",
    "list_alert_policies",
    "get_alert_policy",
    "list_alerts",
    "get_alert",
}
