# ==================================================================================
# FINAL 4-ENDPOINT FLASK API with CORRECT HEYGEN V1 AUTHENTICATION
# ==================================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from datetime import datetime
import requests
import time

from interview import AIInterviewAgent, load_domain_config

# --- Initial Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app) 

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")

if not GEMINI_API_KEY or not HEYGEN_API_KEY:
    raise ValueError("FATAL ERROR: GOOGLE_API_KEY or HEYGEN_API_KEY not set.")

# --- Global variables for a SINGLE interview session ---
agent = None
heygen_session_id = None
heygen_session_token = None


## ------------------------------------------------------------------ ##
## ENDPOINT 1: Start the Interview & Create and START Avatar Session  ##
## ------------------------------------------------------------------ ##
@app.route('/start-interview', methods=['POST'])
def start_interview():
    global agent, heygen_session_id, heygen_session_token
    data = request.get_json()
    try:
        domain_filename = data.get("domain_file")
        candidate_profile = data.get("profile")
        if not domain_filename or not candidate_profile:
            return jsonify({"status": "error", "message": "Domain or profile missing."}), 400

        print("\n--- NEW INTERVIEW START ---")
        print("Step 1: Getting HeyGen session token...")
        token_response = requests.post('https://api.heygen.com/v1/streaming.create_token', headers={'X-Api-Key': HEYGEN_API_KEY}, json={})
        token_response.raise_for_status()
        local_session_token = token_response.json()['data']['token']
        heygen_session_token = local_session_token
        print("Step 1: Token obtained.")

        print("Step 2: Creating new session...")
        new_session_response = requests.post(
            'https://api.heygen.com/v1/streaming.new',
            headers={'Authorization': f'Bearer {local_session_token}'},
            # ## YOUR AVATAR AND VOICE ##
            json={ "quality": "high", "avatar_name": "Anastasia_ProfessionalLook_public", "voice": {"voice_id": "2730df66e1474d79b879ddf66fc5d090"} }
        )
        new_session_response.raise_for_status()
        session_data = new_session_response.json()['data']
        local_session_id = session_data.get('session_id')
        heygen_session_id = local_session_id
        print(f"Step 2: Session created: {local_session_id}")

        # ## THIS IS THE FINAL, DEFINITIVE FIX BASED ON THE OFFICIAL DEMO ##
        print("Step 3: Starting the streaming session...")
        start_response = requests.post(
            'https://api.heygen.com/v1/streaming.start',
            # The 'start' call MUST use the temporary Bearer token in the header.
            headers={'Authorization': f'Bearer {local_session_token}'},
            # The body for the 'start' command MUST ONLY contain the session_id.
            json={ 
                "session_id": local_session_id
            }
        )
        start_response.raise_for_status()
        print("Step 3: Streaming started successfully.")
        
        # Part 4: Initialize AI Agent
        domain_config = load_domain_config(domain_filename)
        agent = AIInterviewAgent(google_api_key=GEMINI_API_KEY, domain_config=domain_config)
        intro_message = agent.initialize_adaptive_interview(candidate_profile)
        
        # Part 5: Command Avatar to Speak (using the temporary Bearer token)
        print(f"Telling avatar to speak intro...")
        requests.post(
            'https://api.heygen.com/v1/streaming.task',
            headers={'Authorization': f'Bearer {local_session_token}'},
            json={ "session_id": local_session_id, "text": intro_message, "task_type": "talk" }
        ).raise_for_status()
        
        return jsonify({
            "status": "success", 
            "introduction": intro_message,
            "heygen_session_data": session_data
        })

    except Exception as e:
        if isinstance(e, requests.exceptions.HTTPError):
            print(f"HeyGen API Error: {e.response.status_code} - {e.response.text}")
        else:
            print(f"Error in /start-interview: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

## ------------------------------------------------------------------ ##
## ENDPOINT 2: Get Next Question & Make Avatar Speak                  ##
## ------------------------------------------------------------------ ##
@app.route('/next-question', methods=['GET'])
def next_question():
    global agent, heygen_session_id, heygen_session_token
    if not agent: return jsonify({"error": "Interview not started."}), 400

    question_data = agent.generate_next_question()
    question_text = question_data.get("question")

    if question_text and heygen_session_id:
        try:
            print(f"Telling avatar to speak: {question_text}")
            # ## FIX: Use the temporary Bearer token for the task endpoint ##
            requests.post(
                'https://api.heygen.com/v1/streaming.task',
                headers={'Authorization': f'Bearer {heygen_session_token}'},
                json={ "session_id": heygen_session_id, "text": question_text, "task_type": "talk" }
            ).raise_for_status()
        except Exception as e:
            print(f"Error telling HeyGen avatar to speak: {e}")
    
    return jsonify(question_data)

## ------------------------------------------------------------------ ##
## ENDPOINT 3: Submit an Answer (No changes needed here)              ##
## ------------------------------------------------------------------ ##
@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    global agent
    if not agent: return jsonify({"error": "Interview not started."}), 400
    data = request.get_json()
    answer, question = data.get("answer"), data.get("question")
    if answer is None or question is None:
        return jsonify({"error": "Request body must include 'question' and 'answer'."}), 400
    evaluation = agent.evaluate_answer(question, answer)
    agent.interview_data["answers_received"].append({
        "question": question, "answer": answer, "evaluation": evaluation, "timestamp": datetime.now()
    })
    return jsonify({ "status": "success", "message": "Answer received." })


## ------------------------------------------------------------------ ##
## ENDPOINT 4: Conclude Interview & Close Avatar Session              ##
## ------------------------------------------------------------------ ##
@app.route('/conclude', methods=['GET'])
def conclude_interview():
    global agent, heygen_session_id, heygen_session_token
    if not agent: return jsonify({"error": "Interview not started."}), 400

    conclusion_data = agent._generate_conclusion()
    summary = agent.get_interview_summary()
    conclusion_text = conclusion_data.get("message")

    if conclusion_text and heygen_session_id:
        try:
            print(f"Telling avatar to speak conclusion...")
            # ## FIX: Use the temporary Bearer token here too ##
            requests.post(
                'https://api.heygen.com/v1/streaming.task',
                headers={'Authorization': f'Bearer {heygen_session_token}'},
                json={ "session_id": heygen_session_id, "text": conclusion_text, "task_type": "talk" }
            ).raise_for_status()
            
            print(f"Closing HeyGen session: {heygen_session_id}")
            requests.post(
                'https://api.heygen.com/v1/streaming.stop',
                headers={'Authorization': f'Bearer {heygen_session_token}'},
                json={ "session_id": heygen_session_id }
            ).raise_for_status()
        except Exception as e:
            print(f"Error during HeyGen conclusion/closing: {e}")

    # Reset all global variables for the next user
    agent = None
    heygen_session_id = None
    heygen_session_token = None
    return jsonify({ "conclusion": conclusion_data, "summary": summary })

if __name__ == '__main__':
    app.run(debug=True, port=5000)