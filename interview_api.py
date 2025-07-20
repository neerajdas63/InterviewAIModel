# ==================================================================================
# CORRECTED 4-ENDPOINT FLASK API (interview_api.py)
# This version uses a global agent and is functional for a single user.
# ==================================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Import your Agent class and the function to load config files
from interview import AIInterviewAgent, load_domain_config

# --- Initial Setup ---
load_dotenv()
app = Flask(__name__)
CORS(app) # Enable Cross-Origin Resource Sharing

# --- Global variables to store the state for a SINGLE interview session ---
# WARNING: This approach will only work correctly for one user at a time.
agent = None
domain_config = None

## ------------------------------------------------------------------ ##
## ENDPOINT 1: Start the Interview                                    ##
## ------------------------------------------------------------------ ##
@app.route('/start', methods=['POST'])
def start_interview():
    global agent, domain_config # Declare that we are modifying the global variables
    
    data = request.get_json()

    try:
        # Get the domain and profile from the request body
        domain_filename = data.get("domain_file")
        candidate_profile = data.get("profile")

        if not domain_filename or not candidate_profile:
            return jsonify({"status": "error", "message": "Domain or profile missing."}), 400

        # Load the configuration for the chosen domain
        domain_config = load_domain_config(domain_filename)
        if not domain_config:
            return jsonify({"status": "error", "message": f"Config for {domain_filename} not found."}), 404

        # Get the API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
             return jsonify({"status": "error", "message": "API key not configured on server."}), 500

        # --- THE FIX: Pass BOTH required arguments to the agent ---
        agent = AIInterviewAgent(google_api_key=api_key, domain_config=domain_config)
        
        # Initialize the interview with the candidate's specific profile
        intro_message = agent.initialize_adaptive_interview(candidate_profile)

        # Return just the introduction message as per your original design
        return jsonify({"status": "success", "message": intro_message})

    except Exception as e:
        print(f"Error in /start: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

## ------------------------------------------------------------------ ##
## ENDPOINT 2: Get the Next Question                                  ##
## ------------------------------------------------------------------ ##
@app.route('/next-question', methods=['GET'])
def next_question():
    global agent
    if not agent:
        return jsonify({"error": "Interview not started. Please call /start first."}), 400

    # The agent already holds the state, so it knows which question to generate
    question_data = agent.generate_next_question()
    return jsonify(question_data)

## ------------------------------------------------------------------ ##
## ENDPOINT 3: Submit an Answer                                       ##
## ------------------------------------------------------------------ ##
@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    global agent
    if not agent:
        return jsonify({"error": "Interview not started. Please call /start first."}), 400
        
    data = request.get_json()
    answer = data.get("answer")
    question = data.get("question")

    if answer is None or question is None:
        return jsonify({"error": "Request body must include 'question' and 'answer'."}), 400

    # Evaluate the answer
    evaluation = agent.evaluate_answer(question, answer)
    
    # Store the results within the agent's state
    agent.interview_data["answers_received"].append({
        "question": question,
        "answer": answer,
        "evaluation": evaluation,
        "timestamp": datetime.now()
    })

    # Generate the adaptive feedback
    feedback = agent._generate_adaptive_feedback(evaluation, question)
    
    # Return both the raw evaluation and the spoken feedback
    return jsonify({"evaluation": evaluation, "feedback": feedback})

## ------------------------------------------------------------------ ##
## ENDPOINT 4: Conclude the Interview                                 ##
## ------------------------------------------------------------------ ##
@app.route('/conclude', methods=['GET'])
def conclude_interview():
    global agent
    if not agent:
        return jsonify({"error": "Interview not started. Please call /start first."}), 400

    conclusion_data = agent._generate_conclusion()
    summary = agent.get_interview_summary()

    # Reset the global agent for the next user
    agent = None
    domain_config = None

    return jsonify({
        "conclusion": conclusion_data,
        "summary": summary
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)