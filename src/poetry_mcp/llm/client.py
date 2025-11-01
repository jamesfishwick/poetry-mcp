"""Claude API client for poetry analysis.

Provides a wrapper around the Anthropic Claude API with:
- Structured JSON output parsing
- Automatic retries with exponential backoff
- Cost tracking and logging
- Response validation
"""

import os
import json
import time
import logging
from typing import Optional, Any
from dataclasses import dataclass

from anthropic import Anthropic, APIError, APITimeoutError
from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM API call."""
    content: str
    parsed_json: Optional[dict] = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0


class ClaudeClient:
    """
    Client for Anthropic Claude API with retry logic and cost tracking.

    Uses Claude 3.5 Sonnet for poetry analysis with structured JSON output.
    Implements exponential backoff for rate limits and transient failures.

    Example:
        >>> client = ClaudeClient()
        >>> response = await client.complete(
        ...     prompt="Analyze this poem for themes...",
        ...     response_model=ThemeDetectionResult
        ... )
        >>> response.parsed_json['themes']
        [{'name': 'water', 'confidence': 0.85}, ...]
    """

    # Claude 3.5 Sonnet pricing (as of 2024)
    COST_PER_1M_INPUT_TOKENS = 3.00  # $3 per 1M input tokens
    COST_PER_1M_OUTPUT_TOKENS = 15.00  # $15 per 1M output tokens

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    DEFAULT_MAX_TOKENS = 2048

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout_seconds: int = 60,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            max_retries: Maximum retry attempts for failed requests
            timeout_seconds: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.total_requests = 0

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage."""
        input_cost = (input_tokens / 1_000_000) * self.COST_PER_1M_INPUT_TOKENS
        output_cost = (output_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT_TOKENS
        return input_cost + output_cost

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_model: Optional[type[BaseModel]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """
        Send a completion request to Claude with retry logic.

        Args:
            prompt: User prompt/message
            system_prompt: Optional system prompt
            response_model: Optional Pydantic model for JSON validation
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            LLMResponse with content and metadata

        Raises:
            APIError: If all retries fail
        """
        start_time = time.time()

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Make API call
                response = self.client.messages.create(
                    model=self.DEFAULT_MODEL,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt if system_prompt else None,
                    messages=messages,
                )

                # Extract content
                content = response.content[0].text

                # Track usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost = self.calculate_cost(input_tokens, output_tokens)

                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_cost_usd += cost
                self.total_requests += 1

                duration = time.time() - start_time

                logger.info(
                    f"Claude API success: {input_tokens} in + {output_tokens} out = ${cost:.4f} "
                    f"(total: ${self.total_cost_usd:.4f})"
                )

                # Parse JSON if response model provided
                parsed_json = None
                if response_model:
                    try:
                        # Extract JSON from markdown code blocks if present
                        json_str = content
                        if "```json" in content:
                            json_str = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            json_str = content.split("```")[1].split("```")[0].strip()

                        # Parse and validate
                        parsed_data = json.loads(json_str)
                        validated = response_model(**parsed_data)
                        parsed_json = validated.model_dump()

                    except (json.JSONDecodeError, ValidationError) as e:
                        logger.warning(f"JSON parsing failed: {e}")
                        logger.debug(f"Raw content: {content}")
                        # Don't fail the request, just log warning

                return LLMResponse(
                    content=content,
                    parsed_json=parsed_json,
                    model=self.DEFAULT_MODEL,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    duration_seconds=duration,
                )

            except APITimeoutError as e:
                last_error = e
                logger.warning(f"API timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except APIError as e:
                last_error = e
                # Check if retryable
                if e.status_code in {429, 500, 502, 503, 504}:
                    logger.warning(
                        f"API error {e.status_code} on attempt {attempt + 1}/{self.max_retries}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                else:
                    # Non-retryable error
                    raise

        # All retries failed
        raise last_error or APIError("All retry attempts failed")

    def get_cost_summary(self) -> dict[str, Any]:
        """Get summary of API usage and costs."""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "avg_cost_per_request": (
                self.total_cost_usd / self.total_requests if self.total_requests > 0 else 0.0
            ),
        }
