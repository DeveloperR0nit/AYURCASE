import os

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@app.route("/api/recommend", methods=["POST"])
def recommend():

    data = request.json
    problem = data.get("problem")

    print("Patient problem:", repr(problem))

    if not problem:
        return jsonify({
            "error": "Please enter some patient information."
        }), 400

    prompt = f"""
You are a patient guidance assistant for a healthcare application.

The patient has reported:

{problem}

Provide general health information and appropriate next-step guidance.

Important rules:
- Do not claim to diagnose the patient.
- Do not prescribe medication.
- Do not provide medication dosages.
- Do not present your response as a medical diagnosis.
- Explain uncertainty when appropriate.
- Recommend consulting a qualified healthcare professional when appropriate.
- If the symptoms could indicate an emergency, clearly recommend seeking urgent medical attention.
- Keep the response clear and easy to understand.
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        recommendation = response.text

        return jsonify({
            "recommendation": recommendation
        })

    except Exception as e:

        print("Gemini error:", repr(e))

        return jsonify({
            "error": "The AI service is currently unavailable. Please try again later."
        }), 500

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:path>")
def frontend_files(path):
    return send_from_directory(BASE_DIR, path)

if __name__ == "__main__":
    app.run(debug=True)