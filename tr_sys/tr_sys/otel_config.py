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
    
    #logging.basicConfig(level=logging.DEBUG)
    logging.info('About to instrument ARS app for OTEL')
    try:
        #otlp_host = os.environ.get('OTLP_HOST', 'gov-otlp.nr-data.net')
        otlp_host = 'otlp.nr-data.net'
        #otlp_port = int(os.environ.get('OTLP_PORT', '4317'))
        otlp_port = 4317
        otel_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
        service_name= 'ARS'
        logger_provider = LoggerProvider(
            resource=Resource.create(
                {
                    "service.name": "ARS",
                }
            ),
        )
        set_logger_provider(logger_provider)
        log_exporter = OTLPLogExporter(
            endpoint=f"https://otlp.nr-data.net:4317",
            headers=(("api-key",otel_headers),)
        )
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)

        # Attach OTLP handler to root logger
        try:
            logger = logging.getLogger()
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.info("Logger initialized and handler added.")
            logger.info(f"Current root logger level: {logging.getLevelName(logger.getEffectiveLevel())}")
            #otlp_handler_exists = any(isinstance(handler, LoggingHandler) for handler in logger.handlers)
            #print(f"OTLP handler attached: {otlp_handler_exists}")
            for handler in logger.handlers:
               logger.info(f"Handler: {handler}, Level: {handler.level}, Formatter: {handler.formatter}")
           #if isinstance(handler, LoggingHandler):  # Or any specific condition
               #logger.removeHandler(handler)
            

            logging.info("Handler attached successfully")
        except Exception as e:
            logging.info(f"Failed to attach handler: {e}")
        
        logging.info("Test message to verify handler attachment.")
        
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
        

        
        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))
