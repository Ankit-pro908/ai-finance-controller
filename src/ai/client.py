import json
import os
import time

from groq import Groq


from src.ai.response_schema import (
    AI_RESPONSE_JSON_SCHEMA,
)


MODEL_NAME = "openai/gpt-oss-20b"

# =========================================================
# API RETRY POLICY
# =========================================================

# Maximum number of HTTP/API attempts for one call.
#
# 1 = no retry
# 2 = one retry
#
# For our current debugging/testing phase we can override
# this from the caller.
MAX_API_ATTEMPTS = 2


# =========================================================
# GROQ CLIENT
# =========================================================

def get_groq_client():
    """
    Create and return a Groq client.

    The API key must exist in the GROQ_API_KEY
    environment variable.
    """

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not set."
        )

    return Groq(
        api_key=api_key
    )


# =========================================================
# ERROR CLASSIFICATION
# =========================================================

def _is_rate_limit_error(
    error: Exception,
) -> bool:
    """
    Return True when the exception indicates
    a Groq/API rate-limit response.
    """

    error_text = str(
        error
    ).lower()

    return (
        "rate_limit" in error_text
        or "rate limit" in error_text
        or "429" in error_text
    )


def _is_temporary_api_error(
    error: Exception,
) -> bool:
    """
    Return True for temporary infrastructure/network
    failures where one retry is reasonable.
    """

    error_text = str(
        error
    ).lower()

    temporary_signals = (
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "503",
        "502",
        "500",
    )

    return any(
        signal in error_text
        for signal in temporary_signals
    )


def _is_json_generation_error(
    error: Exception,
) -> bool:
    """
    Detect failures caused by structured JSON generation.
    """

    error_text = str(
        error
    ).lower()

    return (
        "json_validate_failed"
        in error_text
        or
        "failed to validate json"
        in error_text
        or
        "invalid json"
        in error_text
        or
        "empty content"
        in error_text
    )


# =========================================================
# GROQ REQUEST
# =========================================================
def call_groq(
    prompt: str,
    max_attempts: int = MAX_API_ATTEMPTS,
) -> dict:
    """
    Send one prompt to Groq and return parsed JSON.

    Retry behavior is explicitly bounded.

    JSON is requested in object mode and the Python-side
    validator remains the final schema/semantic gate.
    """

    if max_attempts < 1:
        raise ValueError(
            "max_attempts must be at least 1."
        )

    client = get_groq_client()

    last_error = None

    for attempt in range(max_attempts):

        try:

            response = (
                client
                .chat
                .completions
                .create(
                    model=MODEL_NAME,

                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a financial "
                                "reconciliation "
                                "investigation assistant. "
                                "Return ONLY a single valid "
                                "JSON object. Do not use "
                                "markdown. Do not use code "
                                "fences. Do not add commentary."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],

                    temperature=0,

                    response_format={
                        "type": "json_object",
                    },
                )
            )

            # -------------------------------------------------
            # Extract model content
            # -------------------------------------------------

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if not content:
                raise RuntimeError(
                    "Groq returned empty content."
                )

            content = content.strip()

            # -------------------------------------------------
            # Parse JSON
            # -------------------------------------------------

            try:

                parsed = json.loads(
                    content
                )

            except json.JSONDecodeError as error:

                raise RuntimeError(
                    "Groq returned invalid JSON."
                ) from error

            # -------------------------------------------------
            # Top-level JSON must be an object
            # -------------------------------------------------

            if not isinstance(
                parsed,
                dict,
            ):
                raise RuntimeError(
                    "Groq JSON response "
                    "must be an object."
                )

            return parsed

        except Exception as error:

            last_error = error

            # -------------------------------------------------
            # No retry budget remaining
            # -------------------------------------------------

            if attempt >= (
                max_attempts - 1
            ):
                break

            # -------------------------------------------------
            # Rate limit
            # -------------------------------------------------

            if _is_rate_limit_error(
                error
            ):
                time.sleep(2)
                continue

            # -------------------------------------------------
            # Temporary infrastructure/network error
            # -------------------------------------------------

            if _is_temporary_api_error(
                error
            ):
                time.sleep(2)
                continue

            # -------------------------------------------------
            # JSON generation failure
            # -------------------------------------------------

            if _is_json_generation_error(
                error
            ):
                time.sleep(1)
                continue

            # -------------------------------------------------
            # Everything else is non-retryable.
            # -------------------------------------------------

            raise

    raise RuntimeError(
        "Groq request failed after "
        f"{max_attempts} API attempt(s). "
        f"Underlying error: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    ) from last_error


# =========================================================
# DIRECT CLIENT TEST
# =========================================================

if __name__ == "__main__":

    test_prompt = """
Generate one minimal financial investigation hypothesis.

Return a response that follows the required financial investigation
JSON schema exactly.

Use this situation:

Payment amount is 2000.
Fee is 100.
Refund is 1800.
Expected settlement is 100.
Actual settlement is 150.

The settlement has a 50 discrepancy.

Do not invent record IDs.
"""

    result = call_groq(
        test_prompt,
        max_attempts=1,
    )

    print(
        "\n--- Groq Structured Investigation Test ---"
    )

    print(result)