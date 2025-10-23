import google.generativeai as genai
import os

# Replace with your actual Gemini API key, or load from environment variable
# It's recommended to store API keys securely, e.g., in environment variables
# For testing, you can directly assign it:
# API_KEY = "YOUR_GEMINI_API_KEY"
# Or load from an environment variable:
API_KEY = "AIzaSyAUAxn8oturB4WSi0NL6ManQm0yi936GWc"

if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    print("Please set the environment variable or replace with your key directly in the script.")
else:
    genai.configure(api_key=API_KEY)

    try:
        # Choose a model, e.g., 'gemini-family'
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Make a simple request
        response = model.generate_content("Hello, Gemini!")

        # Print the response to confirm success
        print("API Key is working! Response:")
        print(response.text)

    except Exception as e:
        print(f"Error testing API key: {e}")
        print("The API key might be invalid, expired, or there might be a configuration issue.")