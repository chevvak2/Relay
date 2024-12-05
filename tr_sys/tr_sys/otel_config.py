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

otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")

# Function to retrieve trace context
def get_trace_context():
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return {
            "trace_id": f"{span.get_span_context().trace_id:032x}",
            "span_id": f"{span.get_span_context().span_id:016x}",
        }
    return {}

# Function to send logs to New Relic
def send_log_to_new_relic(message, level="INFO"):
    context = get_trace_context()
    log_entry = {
        "common": {
            "attributes": {
                "service.name": "ARS",
                "host": os.getenv("HOSTNAME", "unknown"),
            }
        },
        "logs": [
            {
                "timestamp": int(logging.time.time() * 1000),
                "message": message,
                "level": level,
                "trace.id": context.get("trace_id"),
                "span.id": context.get("span_id"),
            }
        ],
    }
    endpoint = "https://otlp.nr-data.net/v1/logs"
    headers = {
        "Content-Type": "application/json",
        "Api-Key": otel_headers,
    }

    try:
        with httpx.Client() as client:
            response = client.post(endpoint, headers=headers, data=json.dumps(log_entry))
            if response.status_code != 202:
                logging.error(f"Failed to send log to New Relic: {response.text}")
    except Exception as e:
        logging.error(f"Error while sending log to New Relic: {str(e)}")

class NewRelicLoggingHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        level = record.levelname
        send_log_to_new_relic(log_entry, level)
        
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
        
        # Configure logging to use New Relic handler
        new_relic_handler = NewRelicLoggingHandler()
        new_relic_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(new_relic_handler)

        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))
