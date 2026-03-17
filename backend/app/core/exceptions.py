"""
Custom Exception Classes

Define application-specific exceptions for clear error handling.
"""

from typing import Any, Dict, Optional


class HireRightException(Exception):
    """Base exception for HireRight application."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ProfileParsingError(HireRightException):
    """Error parsing resume or GitHub profile."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "PROFILE_PARSING_ERROR", details)


class JobSearchError(HireRightException):
    """Error searching for jobs."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "JOB_SEARCH_ERROR", details)


class AgentExecutionError(HireRightException):
    """Error during agent pipeline execution."""
    
    def __init__(self, message: str, agent_name: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["agent_name"] = agent_name
        super().__init__(message, "AGENT_EXECUTION_ERROR", details)


class MCPConnectionError(HireRightException):
    """Error connecting to MCP server."""
    
    def __init__(self, message: str, server_name: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["server_name"] = server_name
        super().__init__(message, "MCP_CONNECTION_ERROR", details)


class EmbeddingError(HireRightException):
    """Error generating embeddings."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "EMBEDDING_ERROR", details)


class DatabaseError(HireRightException):
    """Database operation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", details)
