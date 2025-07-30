# ==================================================================================
# AI INTERVIEW AGENT LIBRARY (interview.py)
# This file contains the core logic and classes for the AI agent.
# It is intended to be imported by a server application (like Flask) and not run directly.
# ==================================================================================

# --- Stage 1: Import all necessary libraries ---
import pyttsx3 
import speech_recognition as sr
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import random
from datetime import datetime
import re
from typing import Dict, List

# Load environment variables, which will be used by the importing script (e.g., api.py)
load_dotenv()

## ------------------------------------------------------------------ ##
## STAGE 2: HELPER FUNCTION FOR CONFIGURATION                         ##
## ------------------------------------------------------------------ ##

def load_domain_config(domain_file: str) -> Dict:
    """Loads the specific JSON configuration file for the selected domain."""
    try:
        # The path to the configurations folder.
        path = os.path.join('configurations', domain_file)
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not parse the JSON in {path}")
        return None

## --------------------------------------------------------- ##
## STAGE 3: THE AI INTERVIEW AGENT CLASS                     ##
## --------------------------------------------------------- ##
class AIInterviewAgent:
    def __init__(self, google_api_key: str, domain_config: Dict):
        if not google_api_key:
            raise ValueError("Google API key is required.")
        genai.configure(api_key=google_api_key)
        self.model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        
        self.domain_config = domain_config
        self.personality = {"name": "Alex", "role": "Senior Technical Interviewer", "tone": "Professional but friendly"}
        
        self.interview_state = {
            "question_count": 0,
            "max_questions": random.randint(5, 10),
            "job_role": self.domain_config.get("domain_name", "Technical Professional"),
            "candidate_name": None, "skills_to_assess": [],
            "difficulty_level": "medium", "experience_text": ""
        }
        self.interview_data = {"start_time": None, "questions_asked": [], "answers_received": [], "scores": {}}

    def initialize_adaptive_interview(self, candidate_profile: Dict):
        self.interview_state["candidate_name"] = candidate_profile["name"]
        self.interview_state["skills_to_assess"] = candidate_profile["skills"]
        self.interview_state["experience_text"] = candidate_profile["experience"]
        exp_lower = candidate_profile["experience"].lower()
        if "fresher" in exp_lower: self.interview_state["difficulty_level"] = "Easy"
        elif "junior" in exp_lower: self.interview_state["difficulty_level"] = "Easy-to-Medium"
        elif "mid-level" in exp_lower: self.interview_state["difficulty_level"] = "Medium"
        elif "senior" in exp_lower: self.interview_state["difficulty_level"] = "Hard"
        else: self.interview_state["difficulty_level"] = "Expert / Architectural"
        self.interview_data["start_time"] = datetime.now()
        return self._generate_introduction()

    def _call_gemini_api(self, prompt: str) -> str:
        try:
            return self.model.generate_content(prompt).text.strip()
        except Exception as e:
            print(f"An error occurred with the Gemini API: {e}")
            return "Sorry, I encountered an error."

    def _generate_introduction(self) -> str:
        prompt = f"""
        You are {self.personality['name']}, a {self.personality['role']}. Generate a warm, professional introduction for a candidate named {self.interview_state['candidate_name']}.
        **Candidate's Profile (Use ONLY this information):**
        - Role: {self.interview_state['job_role']}
        - Stated Experience: {self.interview_state['experience_text']}
        - Selected Skills: {', '.join(self.interview_state['skills_to_assess'])}
        **Your Task:**
        1. Welcome the candidate.
        2. Acknowledge their experience: "I see you have about {self.interview_state['experience_text']} of experience."
        3. Confirm the interview will focus on their selected skills.
        4. Explain the structure: "The interview will consist of about {self.interview_state['max_questions']} questions."
        5. Ask if they are ready to begin.
        **Crucial Instruction: Do NOT add any extra details or assumptions.**
        Keep it concise and conversational.
        """
        return self._call_gemini_api(prompt)

    def generate_next_question(self) -> Dict:
        if self.interview_state["question_count"] >= self.interview_state["max_questions"]:
            return {"type": "conclusion"}
        
        if self.interview_state["question_count"] == 0:
            question = f"Great, let's start. To begin, could you please tell me a bit about yourself and your journey as a {self.interview_state['job_role']}?"
            question_type = "introduction"
        else:
            if self.interview_state["question_count"] == 3 or (self.interview_state["max_questions"] > 7 and self.interview_state["question_count"] == 7):
                question_type = "behavioral"
            else:
                question_type = "technical"
            
            if question_type == "technical":
                question = self._generate_technical_question()
            else:
                question = self._generate_behavioral_question()
            
        self.interview_state["question_count"] += 1
        return {"question": question, "type": question_type}

    def _generate_technical_question(self) -> str:
        selected_skill = random.choice(self.interview_state["skills_to_assess"])
        job_role_prompt = self.domain_config.get("job_role_prompt", self.interview_state["job_role"])
        prompt = f"""You are an expert technical interviewer. Generate a single, high-quality interview question for **{job_role_prompt}**. Candidate's Profile: Experience: {self.interview_state['experience_text']}, Difficulty: **{self.interview_state['difficulty_level']}**, Specific Skill to Test: **{selected_skill}**. The question must be practical and its complexity must match the experience level. Return ONLY the question."""
        return self._call_gemini_api(prompt)

    def _generate_behavioral_question(self) -> str:
        context = self.domain_config.get("behavioral_question_context", "their professional field")
        prompt = f"""You are an expert interviewer. Refine the question "Tell me about a challenging project" to be specific for a {self.interview_state['job_role']} with {self.interview_state['experience_text']} of experience. Tie it to concepts like **{context}**. Return only the refined question."""
        return self._call_gemini_api(prompt)

    def evaluate_answer(self, question: str, answer: str) -> Dict:
        prompt = f"""You are an expert interviewer. Evaluate a candidate's answer. Context: Role: {self.interview_state['job_role']}, Experience: {self.interview_state['experience_text']}. Question: "{question}". Candidate's Answer: "{answer}". Provide evaluation in this exact format, with each key on a new line. Be concise.
SCORE: [A number from 1-10]
STRENGTHS: [A brief summary]
IMPROVEMENTS: [A brief summary]"""
        return self._parse_feedback(self._call_gemini_api(prompt))

    def _parse_feedback(self, feedback: str) -> Dict:
        evaluation = {'score': 0, 'strengths': "N/A", 'improvements': "N/A"}
        try:
            for line in feedback.strip().split('\n'):
                if line.startswith('SCORE:'): evaluation['score'] = int(re.search(r'\d+', line).group())
                elif line.startswith('STRENGTHS:'): evaluation['strengths'] = line.split(':', 1)[1].strip()
                elif line.startswith('IMPROVEMENTS:'): evaluation['improvements'] = line.split(':', 1)[1].strip()
            return evaluation
        except Exception as e:
            print(f"Error parsing feedback: {e}\nOriginal: {feedback}")
            return evaluation

    def _generate_detailed_feedback_summary(self) -> str:
        print("...Compiling detailed feedback...")
        feedback_log = ""
        for item in self.interview_data.get("answers_received", []):
            question = item.get("question")
            evaluation = item.get("evaluation", {})
            score = evaluation.get("score", "N/A")
            strengths = evaluation.get("strengths", "N/A")
            improvements = evaluation.get("improvements", "N/A")
            if "tell me about yourself" in question.lower():
                continue
            feedback_log += f"Question: {question}\nScore: {score}/10\nStrengths: {strengths}\nImprovements: {improvements}\n---\n"
        if not feedback_log:
            return "We've completed the questions for today."
        prompt = f"""
        You are Alex, a senior interviewer, providing end-of-interview feedback to {self.interview_state['candidate_name']}.
        Synthesize the following log into a professional, constructive, and encouraging spoken summary.
        **Instructions:**
        1. Start positively: "Thanks for walking me through those questions."
        2. Mention one or two overall strengths (e.g., "I was impressed with your communication...").
        3. Mention one or two general areas for improvement constructively (e.g., "An area to focus on would be...").
        4. Keep the summary conversational and under 150 words.
        **Interview Log:**
        ---
        {feedback_log}
        ---
        Generate the spoken feedback summary for {self.interview_state['candidate_name']}.
        """
        return self._call_gemini_api(prompt)

    def _generate_conclusion(self) -> Dict:
        detailed_feedback = self._generate_detailed_feedback_summary()
        scores = [ans['evaluation']['score'] for ans in self.interview_data['answers_received'] if 'evaluation' in ans]
        overall_score = sum(scores) / len(scores) if scores else 0
        self.interview_data['overall_rating'] = overall_score
        prompt = f"""
        You have just delivered detailed feedback to the candidate, {self.interview_state['candidate_name']}.
        Now, generate the final closing remarks for the interview.
        The remarks should:
        1. Thank the candidate for their time.
        2. Mention next steps (e.g., "our team will review the feedback and be in touch").
        3. End with a positive and encouraging closing statement.
        Keep it professional and concise.
        """
        closing_remarks = self._call_gemini_api(prompt)
        full_conclusion_message = f"{detailed_feedback} {closing_remarks}"
        return {"type": "conclusion", "message": full_conclusion_message, "overall_score": overall_score}

    def get_interview_summary(self) -> Dict:
        start_time = self.interview_data.get("start_time")
        duration = str(datetime.now() - start_time) if start_time else "N/A"
        return {"candidate_name": self.interview_state["candidate_name"], "job_role": self.interview_state["job_role"], "duration": duration, "overall_rating": self.interview_data.get("overall_rating", 0), "questions_and_answers": self.interview_data["answers_received"], "skills_assessed": self.interview_state["skills_to_assess"]}

    # --- VOICE I/O FUNCTIONS ---
    # NOTE: These functions (speak, listen) are part of the agent's logic for defining its
    # capabilities, but they are NOT used by the Flask server. The server will not speak or listen.
    # The actual speaking and listening will happen in the React frontend using browser APIs.
    def speak(self, text: str):
        try:
            print(f"\nAlex: {text}")
            tts_engine = pyttsx3.init()
            voices = tts_engine.getProperty('voices')
            tts_engine.setProperty('voice', voices[1].id if len(voices) > 1 else voices[0].id)
            tts_engine.setProperty('rate', 175)
            tts_engine.say(text)
            tts_engine.runAndWait()
            tts_engine.stop()
        except Exception as e:
            print(f"--- Error in TTS module: {e} ---")

    def listen(self) -> str:
        r = sr.Recognizer()
        r.pause_threshold = 2.0
        with sr.Microphone() as source:
            print("\n🎤 You can take a moment to think. I'm ready to listen...")
            r.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = r.listen(source, timeout=None, phrase_time_limit=300)
                print("🧠 Processing your answer...")
                user_text = r.recognize_google(audio)
                print(f"You said: {user_text}")
                return user_text
            except sr.UnknownValueError:
                self.speak("I'm sorry, I couldn't quite make that out. Could you please try rephrasing?")
                return self.listen()
            except sr.RequestError as e:
                return f"Speech service error: {e}"

# --- NOTE: The `if __name__ == "__main__"` block has been removed. ---
# This file is now a library and should not be run directly.
# The `interview_api.py` file is the new entry point for running the application.