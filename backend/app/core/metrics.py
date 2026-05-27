"""Prometheus custom metrics for Meatapivot.

S5-2: 5 histograms for observability.
"""

from prometheus_client import Histogram, Counter, Gauge

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

COMPILE_FULL_DURATION = Histogram(
    "ontology_compile_full_duration_seconds",
    "Duration of full ontology compilation",
    buckets=[0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0],
)

COMPILE_INCREMENTAL_DURATION = Histogram(
    "ontology_compile_incremental_duration_seconds",
    "Duration of incremental ontology compilation",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0],
)

VALIDATION_DURATION = Histogram(
    "ontology_validation_duration_seconds",
    "Duration of ontology validation",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

DAG_DETECT_DURATION = Histogram(
    "ontology_dag_detect_duration_seconds",
    "Duration of DAG cycle detection",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
)

FUNCTION_EXEC_DURATION = Histogram(
    "ontology_function_exec_duration_seconds",
    "Duration of ontology function execution",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# ---------------------------------------------------------------------------
# Counters / Gauges
# ---------------------------------------------------------------------------

COMPILE_ERRORS_TOTAL = Counter(
    "ontology_compile_errors_total",
    "Total number of compile errors",
    ["error_kind"],
)

DAG_CYCLES_DETECTED = Counter(
    "ontology_dag_cycles_detected_total",
    "Total number of DAG cycles detected",
)

ACTIVE_OBJECT_TYPES = Gauge(
    "ontology_active_object_types",
    "Number of active object types",
    ["tenant_id"],
)

ACTIVE_LINK_TYPES = Gauge(
    "ontology_active_link_types",
    "Number of active link types",
    ["tenant_id"],
)

ACTIVE_INTERFACES = Gauge(
    "ontology_active_interfaces",
    "Number of active interfaces",
    ["tenant_id"],
)
