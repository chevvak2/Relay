from logging import Formatter
from opentelemetry.trace import get_current_span

class OpenTelemetryFormatter(Formatter):
    def format(self, record):
        span = get_current_span()
        if span is not None:
            context = span.get_span_context()
            record.trace_id = format(context.trace_id, '032x') if context.trace_id else "None"
            record.span_id = format(context.span_id, '016x') if context.span_id else "None"
        else:
            record.trace_id = "None"
            record.span_id = "None"

        return super().format(record)
      
