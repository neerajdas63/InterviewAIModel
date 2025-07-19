from flask import Flask, request, jsonify
from interview import AIInterviewAgent  # assume your big logic is in interview_agent.py
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Global interview agent instance
agent = None

@app.route('/start', methods=['POST'])
def start_interview():
    global agent
    data = request.get_json()

    try:
        candidate_profile = {
            "name": data["name"],
            "experience": data["experience"],
            "skills": data["skills"]
        }

        api_key = os.getenv("GOOGLE_API_KEY")
        agent = AIInterviewAgent(google_api_key=api_key)
        intro_message = agent.initialize_adaptive_interview(candidate_profile)

        return jsonify({"status": "success", "message": intro_message})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/next-question', methods=['GET'])
def next_question():
    global agent
    if not agent:
        return jsonify({"error": "Interview not started"}), 400

    question_data = agent.generate_next_question()
    return jsonify(question_data)

@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    global agent
    data = request.get_json()
    answer = data.get("answer", "")
    question = data.get("question", "")

    evaluation = agent.evaluate_answer(question, answer)
    agent.interview_data["answers_received"].append({
        "question": question,
        "answer": answer,
        "evaluation": evaluation
    })

    feedback = agent._generate_adaptive_feedback(evaluation, question)
    return jsonify({"evaluation": evaluation, "feedback": feedback})

@app.route('/conclude', methods=['GET'])
def conclude_interview():
    global agent
    if not agent:
        return jsonify({"error": "Interview not started"}), 400

    conclusion = agent._generate_conclusion()
    summary = agent.get_interview_summary()

    return jsonify({
        "conclusion": conclusion,
        "summary": summary
    })

if __name__ == '__main__':
    app.run(debug=True)
