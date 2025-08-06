# ==================================================================================
# FINAL, SIMPLIFIED FLASK API (Based on Official HeyGen SDK Architecture)
# ==================================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import requests

# We still import your agent to handle the interview logic (questions/feedback)
from interview import AIInterviewAgent, load_domain_config

# --- Initial Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app) 

# --- Get API Keys from .env ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")

if not GEMINI_API_KEY or not HEYGEN_API_KEY:
    raise ValueError("FATAL ERROR: GOOGLE_API_KEY or HEYGEN_API_KEY not set.")


## ------------------------------------------------------------------ ##
## ENDPOINT 1: Get a Temporary HeyGen Session Token                   ##
## This is the ONLY HeyGen-related endpoint needed on the backend.    ##
## Its sole purpose is to keep your main HEYGEN_API_KEY a secret.     ##
## ------------------------------------------------------------------ ##
@app.route('/get-heygen-token', methods=['POST'])
def get_heygen_token():
    """
    Securely creates a temporary session token using the secret API key from the server.
    The frontend will use this temporary token to initialize the HeyGen SDK.
    """
    try:
        print("Received request for HeyGen token...")
        response = requests.post(
            'https://api.heygen.com/v1/streaming.create_token',
            headers={'X-Api-Key': HEYGEN_API_KEY},
            json={} # The body can be empty
        )
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        token = response.json()['data']['token']
        print("Successfully created and sent HeyGen token to frontend.")
        return jsonify({"status": "success", "token": token})
        
    except requests.exceptions.RequestException as e:
        # Log the actual error from HeyGen if available
        error_text = e.response.text if hasattr(e, 'response') else str(e)
        print(f"Error getting HeyGen token: {error_text}")
        return jsonify({"status": "error", "message": "Failed to retrieve access token from HeyGen."}), 500
    except Exception as e:
        print(f"An unknown error occurred: {e}")
        return jsonify({"status": "error", "message": "An internal server error occurred."}), 500


## ------------------------------------------------------------------ ##
## ENDPOINT 2: The Interview "Brain" (Your Gemini Logic)              ##
## This endpoint takes the context of the interview and returns the   ##
## next thing for the avatar to say.                                  ##
## ------------------------------------------------------------------ ##
@app.route('/get-interview-response', methods=['POST'])
def get_interview_response():
    """
    Handles the core interview logic using your AIInterviewAgent.
    It receives the current state of the interview and the user's last answer,
    then returns the AI's next line of dialogue.
    """
    try:
        data = request.get_json()
        turn_type = data.get("type") # Will be "start" or "submit"
        
        domain_filename = data.get("domain_file")
        candidate_profile = data.get("profile")

        if not domain_filename or not candidate_profile:
            return jsonify({"status": "error", "message": "Domain or profile missing."}), 400

        # Create a temporary agent instance for every turn. This is the stateless approach.
        domain_config = load_domain_config(domain_filename)
        agent = AIInterviewAgent(google_api_key=GEMINI_API_KEY, domain_config=domain_config)

        if turn_type == "start":
            intro_message = agent.initialize_adaptive_interview(candidate_profile)
            first_question = agent.generate_next_question().get('question')
            
            # Return an array of text for the avatar to speak sequentially
            return jsonify({
                "status": "success",
                "dialogue": [intro_message, first_question]
            })

        elif turn_type == "submit":
            user_answer = data.get("answer")
            last_question = data.get("question")
            
            if user_answer is None or last_question is None:
                return jsonify({"status": "error", "message": "Question or answer missing."}), 400

            # Here you can add your logic for feedback, etc.
            # For now, we'll just get the next question.
            # You need to restore the agent's state to continue the question count
            agent.interview_state = data.get("interviewState")
            
            # Get the next question
            next_question_data = agent.generate_next_question()

            if next_question_data.get("type") == "conclusion":
                conclusion = agent._generate_conclusion()
                return jsonify({
                    "status": "success",
                    "isComplete": True,
                    "dialogue": [conclusion.get("message")]
                })
            else:
                return jsonify({
                    "status": "success",
                    "isComplete": False,
                    "dialogue": [
                        "Okay, thank you for that.", # Simple transition phrase
                        next_question_data.get("question")
                    ],
                    "newState": agent.interview_state
                })
        else:
            return jsonify({"status": "error", "message": "Invalid turn type provided."}), 400

    except Exception as e:
        print(f"Error in /get-interview-response: {e}")
        return jsonify({"status": "error", "message": "An error occurred in the AI logic."}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)