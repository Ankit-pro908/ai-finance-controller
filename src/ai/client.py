import json
import os

from groq import Groq


MODEL_NAME = "openai/gpt-oss-20b"


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set."
        )

    return Groq(
        api_key=api_key
    )


def call_groq(prompt: str) -> dict:

    client = get_groq_client()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a financial reconciliation "
                    "investigator. Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object"
        },
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    try:
        return json.loads(content)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Groq returned invalid JSON."
        ) from error


if __name__ == "__main__":

    test_prompt = """
Return a JSON object with exactly these fields:

{
  "message": "string",
  "status": "string"
}

Set message to "Groq connection successful".
Set status to "OK".
"""

    result = call_groq(
        test_prompt
    )

    print(
        "\n--- Groq Test Response ---"
    )

    print(result)