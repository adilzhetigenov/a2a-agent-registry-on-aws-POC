"""
Logging utilities for structured logging
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class StructuredLogger:
    """Structured logger for consistent log formatting"""
    
    def __init__(self, name: str = __name__):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Configure formatter for structured logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _log_structured(self, level: str, message: str, **kwargs):
        """Log structured message with additional context"""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        
        # Use appropriate logging level
        if level == "DEBUG":
            self.logger.debug(json.dumps(log_data))
        elif level == "INFO":
            self.logger.info(json.dumps(log_data))
        elif level == "WARNING":
            self.logger.warning(json.dumps(log_data))
        elif level == "ERROR":
            self.logger.error(json.dumps(log_data))
        elif level == "CRITICAL":
            self.logger.critical(json.dumps(log_data))
    
    def info(self, message: str, request_id: Optional[str] = None, **kwargs):
        """Log info message"""
        context = {"request_id": request_id} if request_id else {}
        context.update(kwargs)
        self._log_structured("INFO", message, **context)
    
    def warning(self, message: str, request_id: Optional[str] = None, **kwargs):
        """Log warning message"""
        context = {"request_id": request_id} if request_id else {}
        context.update(kwargs)
        self._log_structured("WARNING", message, **context)
    
    def error(self, message: str, error: Optional[Exception] = None, 
              request_id: Optional[str] = None, **kwargs):
        """Log error message"""
        context = {"request_id": request_id} if request_id else {}
        if error:
            context.update({
                "error_type": type(error).__name__,
                "error_message": str(error)
            })
        context.update(kwargs)
        self._log_structured("ERROR", message, **context)
    
    def debug(self, message: str, request_id: Optional[str] = None, **kwargs):
        """Log debug message"""
        context = {"request_id": request_id} if request_id else {}
        context.update(kwargs)
        self._log_structured("DEBUG", message, **context)
    
    def log_request(self, method: str, path: str, request_id: str, **kwargs):
        """Log incoming request"""
        self.info(
            f"Incoming request: {method} {path}",
            request_id=request_id,
            method=method,
            path=path,
            **kwargs
        )
    
    def log_response(self, status_code: int, request_id: str, duration_ms: Optional[float] = None, **kwargs):
        """Log outgoing response"""
        context = {
            "status_code": status_code,
            "request_id": request_id
        }
        if duration_ms is not None:
            context["duration_ms"] = duration_ms
        context.update(kwargs)
        
        self.info(f"Response sent: {status_code}", **context)
    
    def log_api_error(self, error_code: str, message: str, request_id: str, **kwargs):
        """Log API error"""
        self.warning(
            f"API error: {error_code} - {message}",
            request_id=request_id,
            error_code=error_code,
            **kwargs
        )


# Global logger instance
logger = StructuredLogger(__name__)


def get_logger(name: str = __name__) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)