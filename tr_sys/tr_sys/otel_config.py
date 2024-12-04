import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME as telemetery_service_name_key, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from celery.signals import worker_process_init
from opentelemetry.sdk._logs import LoggingHandler, LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")

def configure_opentelemetry():

    logging.info('About to instrument ARS app for OTEL')
    try:
        otlp_host = os.environ.get('OTLP_HOST', 'otlp.nr-data.net')
        otlp_port = int(os.environ.get('OTLP_PORT', '4317'))
        service_name= 'ARS'
        resource = Resource.create({telemetery_service_name_key: service_name})

        trace.set_tracer_provider(TracerProvider(resource=resource))

        tracer_provider = trace.get_tracer_provider()

        # Configure Jaeger Exporter
        OTLP_exporter = OTLPSpanExporter(
            endpoint=f"https://{otlp_host}:{otlp_port}"
        )

        span_processor = BatchSpanProcessor(OTLP_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Optional: Console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Define custom log record mapping to define how log records are mapped
        def map_log_record(record: logging.LogRecord) -> dict:
            # Get current span from the context
            span = trace.get_current_span()
            span_context = span.get_span_context() if span else None

            return {
                "severity_text": record.levelname,
                "severity_number": record.levelno,
                "body": record.getMessage(),
                "attributes": {
                    "logger.name": record.name,
                    "file.name": record.pathname,
                    "line.number": record.lineno,
                    "function.name": record.funcName,
                    "thread.name": record.threadName,
                    "trace_id": span_context.trace_id if span_context else None,
                    "span_id": span_context.span_id if span_context else None,
                },
            }
        # Custom LogExporter that uses the mapping
        class CustomOTLPLogExporter(OTLPLogExporter):
            def export(self, batch):
                mapped_logs = [map_log_record(record) for record in batch]
                return super().export(mapped_logs)

        # Logger provider setup
        logger_provider = LoggerProvider(resource=resource)
        log_processor = BatchLogProcessor(CustomOTLPLogExporter(
            endpoint=f"https://{otlp_host}:{otlp_port}",
            headers=(("api-key", otel_headers),)))
        logger_provider.add_log_processor(log_processor)
        logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()

        @worker_process_init.connect(weak=False)
        def init_celery_tracing(*args, **kwargs):
            CeleryInstrumentor().instrument()


        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))
