#!/usr/bin/env python3
"""Test script to isolate a single Google Gemini API request."""

import os
import sys

sys.stdout.reconfigure(line_buffering=True)

print("Loading environment...")
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not set")
    sys.exit(1)

print(f"API Key: {api_key[:8]}...{api_key[-4:]}")

print("\nImporting google.generativeai...")
import google.generativeai as genai  # noqa: E402

print("Configuring API key...")
genai.configure(api_key=api_key)

# List available models
print("\n=== Available Gemini Models ===")
try:
    for model in genai.list_models():
        if "gemini" in model.name.lower():
            print(f"  {model.name} - {getattr(model, 'display_name', 'N/A')}")
except Exception as e:
    print(f"ERROR listing models: {type(e).__name__}: {e}")

# Test gemini-3-pro-preview (configured model for pattern)
print("\n=== Testing: gemini-3-pro-preview ===")
try:
    model = genai.GenerativeModel("gemini-3-pro-preview")
    response = model.generate_content("What is 2+2? Reply with just the number.")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test gemini-1.5-pro (known stable model)
print("\n=== Testing: gemini-1.5-pro ===")
try:
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content("What is 2+2? Reply with just the number.")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\nDone.")
