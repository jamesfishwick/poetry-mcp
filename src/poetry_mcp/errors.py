"""Custom exceptions for Poetry MCP."""


class PoetryMCPError(Exception):
    """Base exception for Poetry MCP errors."""

    pass


class BaseParseError(PoetryMCPError):
    """Error parsing BASE file."""

    pass


class YAMLSyntaxError(BaseParseError):
    """YAML syntax error in BASE file."""

    pass


class NexusNotFoundError(PoetryMCPError):
    """Nexus not found in registry."""

    pass


class FileSystemError(PoetryMCPError):
    """File system operation error."""

    pass


class ValidationError(PoetryMCPError):
    """Data validation error."""

    pass


class FrontmatterParseError(PoetryMCPError):
    """Error parsing markdown frontmatter."""

    pass
