"""OpenTelemetry tracing setup — optional, gracefully degrades when not configured."""
import logging
import os

logger = logging.getLogger("bomipay.tracing")

_tracing_initialized = False


def setup_tracing(app) -> None:  # app: FastAPI
    """
    Configure OpenTelemetry tracing.

    If OTEL_EXPORTER_OTLP_ENDPOINT is set an OTLP/HTTP exporter is wired up;
    otherwise a no-op tracer provider is used.  If the opentelemetry packages
    are missing the function returns silently.

    Idempotent — safe to call multiple times (e.g. in tests).
    """
    global _tracing_initialized
    if _tracing_initialized:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning("opentelemetry packages not available — tracing disabled")
        return

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    resource = Resource.create({"service.name": "bomipay"})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("tracing.otlp_configured", extra={"endpoint": otlp_endpoint})
        except Exception as exc:
            logger.warning("tracing.otlp_setup_failed", extra={"error": str(exc)})
    else:
        logger.info("tracing.no_op — set OTEL_EXPORTER_OTLP_ENDPOINT to enable OTLP export")

    trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("tracing.fastapi_instrument_failed", extra={"error": str(exc)})

    _tracing_initialized = True
