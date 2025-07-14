import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load the environment variables from .env file
load_dotenv()

print("Checking available models for your API key...")

try:
    # Configure the client with your API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: Could not find GOOGLE_API_KEY. Make sure it is in your .env file.")
    else:
        genai.configure(api_key=api_key)

        print("\n--- Models that support 'generateContent' ---")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
        print("-------------------------------------------\n")
        print("If a model is listed above, copy its name and paste it into your interview.py script.")
        print("The most common one is 'models/gemini-1.0-pro-latest' or similar.")

except Exception as e:
    print(f"\nAn error occurred while trying to connect to the API: {e}")