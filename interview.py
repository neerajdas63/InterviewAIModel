# ==================================================================================
# FINAL, MULTI-DOMAIN AI INTERVIEW AGENT (with Random Question Count)
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

load_dotenv()

## ------------------------------------------------------------------ ##
## STAGE 2: ONBOARDING AND CONFIGURATION                              ##
## ------------------------------------------------------------------ ##

def load_domain_config(domain_file: str) -> Dict:
    """Loads the specific JSON configuration file for the selected domain."""
    try:
        path = os.path.join('configurations', domain_file)
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not parse the JSON in {path}")
        return None

def onboard_candidate() -> Dict:
    """
    Interactively gathers the candidate's domain, name, experience, and skills.
    Returns a dictionary containing the candidate's complete profile and chosen domain config.
    """
    print("=== Welcome to the Adaptive AI Interviewer ===")
    try:
        config_files = {str(i+1): f for i, f in enumerate(os.listdir('configurations')) if f.endswith('.json')}
    except FileNotFoundError:
        print("\n[FATAL ERROR] The 'configurations' folder was not found.")
        return None
    if not config_files:
        print("\n[FATAL ERROR] No .json config files found in the 'configurations' folder.")
        return None
        
    print("\n▶ Please select your interview domain:")
    for key, filename in config_files.items():
        pretty_name = filename.replace('_', ' ').replace('.json', '').title()
        print(f"  {key}: {pretty_name}")
    
    domain_config = None
    while not domain_config:
        choice = input("Enter the number of your choice: ")
        if choice in config_files:
            domain_config = load_domain_config(config_files[choice])
            if not domain_config:
                print("Issue with that configuration. Please try another.")
        else:
            print("Invalid selection. Please try again.")

    candidate_name = input(f"\n▶ You've selected {domain_config['domain_name']}. Please type your name to begin: ") or "Candidate"
    print(f"\nHello, {candidate_name}! Let's set up your interview profile.")
    
    print("\n▶ Please enter your total years of professional experience (e.g., 0, 1, 5, 10).")
    experience_text = ""
    while True:
        try:
            years = int(input("Enter years of experience: "))
            if years < 0:
                print("Experience cannot be negative. Please try again.")
                continue
            if 0 <= years <= 1: experience_text = "Fresher (0-1 year)"
            elif 2 <= years <= 3: experience_text = "Junior (1-3 years)"
            elif 4 <= years <= 5: experience_text = "Mid-Level (3-5 years)"
            elif 6 <= years <= 8: experience_text = "Senior (5-8 years)"
            else: experience_text = "Lead/Principal (8+ years)"
            print(f"✓ Great! We'll set the interview for a '{experience_text}' level.")
            break
        except ValueError:
            print("Invalid input. Please enter a whole number.")

    print(f"\n▶ Now, let's select your key skills for the {domain_config['domain_name']} interview.")
    skill_categories = domain_config.get("skill_categories", {})
    all_skills = [skill for sublist in skill_categories.values() for skill in sublist]
    
    print("Enter the numbers of the skills you want to be interviewed on (e.g., '1 4 8').")
    for i, skill in enumerate(all_skills, 1):
        print(f"  {i:2d}: {skill}")
    
    selected_skills = []
    while not selected_skills:
        try:
            choices_str = input("Your choices: ")
            chosen_indices = [int(x.strip()) - 1 for x in choices_str.split()]
            valid_choices = [idx for idx in chosen_indices if 0 <= idx < len(all_skills)]
            if not valid_choices:
                print("Invalid selection. Please try again.")
                continue
            selected_skills = [all_skills[i] for i in valid_choices]
        except ValueError:
            print("Invalid input. Please enter numbers separated by spaces.")

    print(f"\nGreat! We will focus on: {', '.join(selected_skills)}")
    print("--------------------------------------------------\n")
    
    return {
        "profile": {"name": candidate_name, "experience": experience_text, "skills": selected_skills},
        "config": domain_config
    }


## --------------------------------------------------------- ##
## STAGE 3: THE AI INTERVIEW AGENT CLASS (NOW CONFIGURABLE)  ##
## --------------------------------------------------------- ##
class AIInterviewAgent:
    # The __init__ method is the constructor, run once when a new agent is created.
    def __init__(self, google_api_key: str, domain_config: Dict):
        # --- API and Model Configuration ---
        if not google_api_key:
            raise ValueError("Google API key is required.")
        genai.configure(api_key=google_api_key)
        self.model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        
        # --- Agent Personality and State ---
        self.domain_config = domain_config
        self.personality = {"name": "Alex", "role": "Senior Technical Interviewer", "tone": "Professional but friendly"}
        
        # This dictionary holds the current state of the interview as it progresses.
        self.interview_state = {
            "question_count": 0,
            # ## MODIFIED - The total number of questions is now random between 5 and 10 ##
            "max_questions": random.randint(5, 10),
            "job_role": self.domain_config.get("domain_name", "Technical Professional"),
            "candidate_name": None, "skills_to_assess": [],
            "difficulty_level": "medium", "experience_text": ""
        }
        self.interview_data = {"start_time": None, "questions_asked": [], "answers_received": [], "scores": {}}

    # This method is called after onboarding to configure the agent with the user's profile.
    def initialize_adaptive_interview(self, candidate_profile: Dict):
        # Set the agent's internal state based on the profile received from onboard_candidate().
        self.interview_state["candidate_name"] = candidate_profile["name"]
        self.interview_state["skills_to_assess"] = candidate_profile["skills"]
        self.interview_state["experience_text"] = candidate_profile["experience"]
        exp_lower = candidate_profile["experience"].lower()
        if "fresher" in exp_lower: self.interview_state["difficulty_level"] = "Easy"
        elif "junior" in exp_lower: self.interview_state["difficulty_level"] = "Easy-to-Medium"
        elif "mid-level" in exp_lower: self.interview_state["difficulty_level"] = "Medium"
        elif "senior" in exp_lower: self.interview_state["difficulty_level"] = "Hard"
        else: self.interview_state["difficulty_level"] = "Expert / Architectural"
        
        # Record the start time of the interview.
        self.interview_data["start_time"] = datetime.now()
        # Generate and return the personalized introduction message.
        return self._generate_introduction()

    # A helper function to centralize all calls to the Gemini API.
    def _call_gemini_api(self, prompt: str) -> str:
        try:
            return self.model.generate_content(prompt).text.strip()
        except Exception as e:
            print(f"An error occurred with the Gemini API: {e}")
            return "Sorry, I encountered an error."

    # Generates the welcome message, now telling the user the random number of questions.
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

    # Decides which type of question to ask next and generates it.
    def generate_next_question(self) -> Dict:
        # Check if the number of questions asked has reached the random maximum.
        if self.interview_state["question_count"] >= self.interview_state["max_questions"]:
            return {"type": "conclusion"}
        
        # The first question is always a general introduction.
        if self.interview_state["question_count"] == 0:
            question = f"Great, let's start. To begin, could you please tell me a bit about yourself and your journey as a {self.interview_state['job_role']}?"
            question_type = "introduction"
        else:
            # Mix in one or two behavioral questions during the interview.
            # This logic will ask a behavioral question on the 3rd and potentially 7th question turn.
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

    # Generates a technical question tailored to the user's profile.
    def _generate_technical_question(self) -> str:
        selected_skill = random.choice(self.interview_state["skills_to_assess"])
        job_role_prompt = self.domain_config.get("job_role_prompt", self.interview_state["job_role"])
        prompt = f"""You are an expert technical interviewer. Generate a single, high-quality interview question for **{job_role_prompt}**. Candidate's Profile: Experience: {self.interview_state['experience_text']}, Difficulty: **{self.interview_state['difficulty_level']}**, Specific Skill to Test: **{selected_skill}**. The question must be practical and its complexity must match the experience level. Return ONLY the question."""
        return self._call_gemini_api(prompt)

    # Generates a behavioral question tailored to the user's profile.
    def _generate_behavioral_question(self) -> str:
        context = self.domain_config.get("behavioral_question_context", "their professional field")
        prompt = f"""You are an expert interviewer. Refine the question "Tell me about a challenging project" to be specific for a {self.interview_state['job_role']} with {self.interview_state['experience_text']} of experience. Tie it to concepts like **{context}**. Return only the refined question."""
        return self._call_gemini_api(prompt)

    # Sends the user's answer to the AI for a score and feedback.
    def evaluate_answer(self, question: str, answer: str) -> Dict:
        prompt = f"""You are an expert interviewer. Evaluate a candidate's answer. Context: Role: {self.interview_state['job_role']}, Experience: {self.interview_state['experience_text']}. Question: "{question}". Candidate's Answer: "{answer}". Provide evaluation in this exact format, with each key on a new line. Be concise.
SCORE: [A number from 1-10]
STRENGTHS: [A brief summary]
IMPROVEMENTS: [A brief summary]"""
        return self._parse_feedback(self._call_gemini_api(prompt))

    # Parses the structured feedback from the AI into a Python dictionary.
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

    # Generates a comprehensive feedback summary at the end of the interview.
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

    # Generates the final closing statement of the interview.
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

    # Compiles all collected data into a final summary report.
    def get_interview_summary(self) -> Dict:
        start_time = self.interview_data.get("start_time")
        duration = str(datetime.now() - start_time) if start_time else "N/A"
        return {"candidate_name": self.interview_state["candidate_name"], "job_role": self.interview_state["job_role"], "duration": duration, "overall_rating": self.interview_data.get("overall_rating", 0), "questions_and_answers": self.interview_data["answers_received"], "skills_assessed": self.interview_state["skills_to_assess"]}

    # --- VOICE I/O FUNCTIONS ---
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
        with sr.Microphone() as source:
            print("\n🎤 You can take a moment to think. I'm ready to listen...")
            r.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = r.listen(source, timeout=None, phrase_time_limit=180)
                print("🧠 Processing your answer...")
                user_text = r.recognize_google(audio)
                print(f"You said: {user_text}")
                return user_text
            except sr.UnknownValueError:
                self.speak("I'm sorry, I couldn't quite make that out. Could you please try rephrasing?")
                return self.listen()
            except sr.RequestError as e:
                return f"Speech service error: {e}"


## ----------------------------------------------------- ##
## STAGE 4: MAIN EXECUTION BLOCK                         ##
## ----------------------------------------------------- ##
if __name__ == "__main__":
    try:
        import pyttsx3
    except ImportError:
        print("The 'pyttsx3' library is not found. Please run: pip install pyttsx3")
        exit()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        exit()
    
    try:
        onboarding_data = onboard_candidate()
        if not onboarding_data:
            exit()
            
        agent = AIInterviewAgent(
            google_api_key=api_key,
            domain_config=onboarding_data["config"]
        )
        
        intro = agent.initialize_adaptive_interview(onboarding_data["profile"])
        agent.speak(intro)
        
        # The main interview loop.
        while agent.interview_state["question_count"] < agent.interview_state["max_questions"]:
            question_data = agent.generate_next_question()
            if question_data.get("type") == "conclusion":
                break

            agent.speak(question_data['question'])
            
            # Inner loop to handle requests to repeat the question.
            while True:
                user_answer = agent.listen()
                repeat_keywords = ["repeat", "pardon", "say that again", "didn't hear"]
                if any(keyword in user_answer.lower() for keyword in repeat_keywords):
                    agent.speak("Of course, I'll repeat the question.")
                    agent.speak(question_data['question'])
                    continue
                else:
                    break
            
            # Evaluate the answer and store it silently.
            evaluation = agent.evaluate_answer(question_data['question'], user_answer)
            agent.interview_data["answers_received"].append({
                "question": question_data['question'],
                "answer": user_answer,
                "evaluation": evaluation,
                "timestamp": datetime.now()
            })
            
            # Give a simple, neutral transition phrase instead of immediate feedback.
            if "tell me about yourself" in question_data['question'].lower():
                agent.speak("Thanks for sharing that background. Now, for our first technical question.")
            else:
                agent.speak("Okay, thank you. Let's move to the next question.")
        
        # At the end, generate and speak the comprehensive conclusion with feedback.
        conclusion_data = agent._generate_conclusion()
        agent.speak(conclusion_data.get('message', 'Thank you for your time.'))

        summary = agent.get_interview_summary()
        print(f"\n\n=== Final Interview Summary ===")
        print(f"Candidate: {summary['candidate_name']} ({summary['job_role']})")
        print(f"Stated Experience: {agent.interview_state['experience_text']}")
        print(f"Overall Rating: {summary['overall_rating']:.1f}/10")
        print(f"Duration: {summary['duration']}")
        print(f"Skills Assessed: {summary['skills_assessed']}")

    except Exception as e:
        print(f"\nAn unexpected error occurred during the interview process: {e}")