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
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

def configure_opentelemetry():

    logging.info('About to instrument ARS app for OTEL')
    try:
        otlp_host = os.environ.get('OTLP_HOST', 'gov-otlp.nr-data.net')
        otlp_port = int(os.environ.get('OTLP_PORT', '4317'))
        otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
        service_name= 'ARS'
        service_instance='Test'
        resource = Resource.create({telemetery_service_name_key: service_name})

        trace.set_tracer_provider(TracerProvider(resource=resource))

        tracer_provider = trace.get_tracer_provider()

        # Configure Jaeger Exporter
        OTLP_exporter = OTLPSpanExporter(
            endpoint=f"https://{otlp_host}:{otlp_port}",
            headers=(("api-key",otel_headers),)
        )

        span_processor = BatchSpanProcessor(OTLP_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Optional: Console exporter for debugging
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        
        @worker_process_init.connect(weak=False)
        def init_celery_tracing(*args, **kwargs):
            CeleryInstrumentor().instrument()
        
        logger_provider = LoggerProvider(
            resource=Resource.create(
                {
                    "service.name": service_name,
                    "service.instance.id": service_instance,
                }
            ),
        )
        set_logger_provider(logger_provider)
        exporter = OTLPLogExporter(
            endpoint=f"https://{otlp_host}:{otlp_port}",
            headers=(("api-key",otel_headers),)
            )
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

        # Attach OTLP handler to root logger
        logging.getLogger().addHandler(handler)
        #logger_provider.shutdown()
        
        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))
