"""Opt-in integration smoke test to verify real Gemini API connectivity and model access.

Usage:
    python scripts/check_gemini_connection.py

Requirements:
    - GEMINI_API_KEY configured in environment or .env file.
    - Active internet connection.
    - Never runs automatically in pytest.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load local environment configuration
load_dotenv()

from google import genai
from google.genai import types
from google.genai import errors as genai_errors


async def check_connection() -> int:
    """Verify Gemini API connection and model access using configured environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    print("=" * 60)
    print("IIMBx Helpdesk — Gemini API Connection Verification")
    print("=" * 60)

    # 1. Verify API Key presence
    if not api_key or not api_key.strip():
        print("\n[ERROR] GEMINI_API_KEY is not configured in the environment.")
        print("Please copy .env.example to .env and configure your real Gemini API key:")
        print("    Copy-Item .env.example .env")
        print("    (Edit .env to set GEMINI_API_KEY=...)")
        print("\nSmoke test cannot run without configured credentials.")
        return 1

    # Print masked key verification (never print real key!)
    masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
    print(f"API Key: Configured ({masked_key})")
    print(f"Configured Model: {model_name}")
    print("\nSending test ping request to Gemini API...")

    try:
        client = genai.Client(api_key=api_key)
        
        # Test minimal generation ping
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Say 'OK' if you can read this.",
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=10,
            ),
        )

        if response and response.text and response.text.strip():
            print("\n[SUCCESS] Gemini API connection verified successfully!")
            print(f"Model: {model_name}")
            print(f"Response Received: {response.text.strip()!r}")
            print("Status: CONNECTED AND OPERATIONAL")
            print("=" * 60)
            return 0
        else:
            print("\n[WARNING] Received empty response from model.")
            print(f"Model: {model_name}")
            print("Status: EMPTY_RESPONSE")
            return 2

    except genai_errors.APIError as e:
        code = getattr(e, "code", 0)
        msg = getattr(e, "message", str(e))
        print(f"\n[API ERROR] Gemini API call failed with code {code}:")
        print(f"Details: {msg}")

        if code in (401, 403):
            print("\nDiagnosis: AUTHENTICATION_FAILED")
            print("Your GEMINI_API_KEY appears invalid or lacks permissions for this project.")
        elif code == 404:
            print(f"\nDiagnosis: MODEL_NOT_FOUND ({model_name})")
            print("The configured model name is either invalid or your key does not have access to it.")
            print("Try checking available models or setting GEMINI_MODEL in .env.")
        elif code == 429:
            print("\nDiagnosis: RATE_LIMIT_OR_QUOTA_EXHAUSTED")
            print("You have hit the Gemini API rate limit or daily free-tier quota.")
        else:
            print(f"\nDiagnosis: HTTP_{code}_ERROR")
        return 3

    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {type(e).__name__}: {e}")
        return 4


if __name__ == "__main__":
    exit_code = asyncio.run(check_connection())
    sys.exit(exit_code)
