# ==================================================================================
# FINAL, FULLY-COMMENTED AI INTERVIEW AGENT
# ==================================================================================

# --- Stage 1: Import all necessary libraries ---

# For fast, offline text-to-speech capabilities. This makes the agent's voice instant.
import pyttsx3 

# For listening to the user's microphone and converting speech to text.
import speech_recognition as sr

# For interacting with the Gemini Large Language Model API.
import google.generativeai as genai

# For handling file operations, like reading environment variables.
import os

# For loading secret keys (like the API key) from a local .env file.
from dotenv import load_dotenv

# Standard Python libraries for various tasks.
import json         # For parsing data structures.
import random       # For choosing random items from a list (like skills).
from datetime import datetime # For timestamping the interview start and answers.
import re           # For regular expressions, used here for parsing the AI's score.
from typing import Dict, List # For type hinting, which makes code easier to read.

# This command executes the library to load variables from the .env file.
load_dotenv()

## ------------------------------------------------------------------ ##
## STAGE 2: ONBOARDING FUNCTION                                       ##
## This function runs first to set up the interview with the user.    ##
## ------------------------------------------------------------------ ##
def onboard_candidate() -> Dict:
    """
    Interactively gathers the candidate's name, experience, and skills.
    This function creates a profile for the candidate before the AI agent is even initialized.
    Returns a dictionary containing the candidate's complete profile.
    """
    print("=== Welcome to the Adaptive AI Interviewer ===")
    
    # --- Part 1: Get Candidate Name ---
    candidate_name = input("▶ Please type your name to begin: ") or "Candidate"
    print(f"\nHello, {candidate_name}! Let's set up your interview profile.")
    
    # --- Part 2: Get Experience Level (Adaptive Logic) ---
    print("\n▶ Please enter your total years of professional experience (e.g., 0, 1, 5, 10).")
    experience_text = ""
    # Loop indefinitely until a valid number is entered.
    while True:
        try:
            # Get user input and attempt to convert it to an integer.
            years = int(input("Enter years of experience: "))
            
            # Ensure the number isn't negative.
            if years < 0:
                print("Experience cannot be negative. Please try again.")
                continue # Skip the rest of the loop and ask again.
            
            # Map the numerical years to a descriptive text category.
            if 0 <= years <= 1: experience_text = "Fresher (0-1 year)"
            elif 2 <= years <= 3: experience_text = "Junior (1-3 years)"
            elif 4 <= years <= 5: experience_text = "Mid-Level (3-5 years)"
            elif 6 <= years <= 8: experience_text = "Senior (5-8 years)"
            else: experience_text = "Lead/Principal (8+ years)"
            
            # Provide immediate confirmation to the user.
            print(f"✓ Great! We'll set the interview for a '{experience_text}' level.")
            break # Exit the loop since we have a valid answer.
        except ValueError:
            # This 'except' block catches errors if the user types text instead of a number.
            print("Invalid input. Please enter a whole number.")

    # --- Part 3: Get Skill Selection ---
    print("\n▶ Now, let's select your key skills for this Frontend Developer interview.")
    skill_categories = {
        "Core Technologies": ["HTML", "CSS", "JavaScript (ES6+)"],
        "Frameworks": ["React.js", "Angular", "Vue.js"],
        "State Management": ["Redux", "Context API", "Zustand"],
        "Styling": ["Tailwind CSS", "SASS/SCSS", "Bootstrap"],
        "Tools & APIs": ["Git & GitHub", "Fetch API/Axios", "Vite/Webpack", "Responsive Design"]
    }
    # Create a single flat list of all skills to display with numbers.
    all_skills = [skill for sublist in skill_categories.values() for skill in sublist]
    
    print("Enter the numbers of the skills you want to be interviewed on (e.g., '1 4 8').")
    for i, skill in enumerate(all_skills, 1):
        print(f"  {i:2d}: {skill}")
    
    selected_skills = []
    # Loop until the user provides at least one valid skill choice.
    while not selected_skills:
        try:
            choices_str = input("Your choices: ")
            # Convert the input string (e.g., "1 4 8") into a list of integer indices.
            chosen_indices = [int(x.strip()) - 1 for x in choices_str.split()]
            # Filter out any invalid numbers (e.g., if the user enters 99).
            valid_choices = [idx for idx in chosen_indices if 0 <= idx < len(all_skills)]
            
            if not valid_choices:
                print("Invalid selection. Please try again.")
                continue # Ask again.
            
            # Map the valid indices back to skill names.
            selected_skills = [all_skills[i] for i in valid_choices]
        except ValueError:
            print("Invalid input. Please enter numbers separated by spaces.")

    print(f"\nGreat! We will focus on: {', '.join(selected_skills)}")
    print("--------------------------------------------------\n")
    
    # Return the complete profile as a dictionary.
    return {"name": candidate_name, "experience": experience_text, "skills": selected_skills}


## --------------------------------------------------------- ##
## STAGE 3: THE AI INTERVIEW AGENT CLASS                     ##
## This class contains all the logic for the AI's behavior.  ##
## --------------------------------------------------------- ##
class AIInterviewAgent:
    # The __init__ method is the constructor, run once when a new agent is created.
    def __init__(self, google_api_key: str):
        # --- API and Model Configuration ---
        if not google_api_key:
            raise ValueError("Google API key is required.")
        genai.configure(api_key=google_api_key)
        self.model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

        # --- Agent Personality and State ---
        self.personality = {"name": "Alex", "role": "Senior Technical Interviewer", "tone": "Professional but friendly"}
        
        # This dictionary holds the current state of the interview as it progresses.
        self.interview_state = {
            "current_phase": "introduction", "question_count": 0, "max_questions": 5,
            "job_role": "Frontend Developer", "candidate_name": None, "skills_to_assess": [],
            "difficulty_level": "medium", "experience_text": ""
        }
        
        # This dictionary stores all the data collected during the interview for the final summary.
        self.interview_data = {"start_time": None, "questions_asked": [], "answers_received": [], "scores": {}}

    # This method is called after onboarding to configure the agent with the user's profile.
    def initialize_adaptive_interview(self, candidate_profile: Dict):
        # Set the agent's internal state based on the profile received from onboard_candidate().
        self.interview_state["candidate_name"] = candidate_profile["name"]
        self.interview_state["skills_to_assess"] = candidate_profile["skills"]
        self.interview_state["experience_text"] = candidate_profile["experience"]
        
        # Translate the descriptive experience text into a difficulty level for the AI.
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
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"An error occurred with the Gemini API: {e}")
            return "Sorry, I encountered an error."

    # Generates the welcome message using strict, detailed instructions.
    def _generate_introduction(self) -> str:
        prompt = f"""
        You are {self.personality['name']}, a {self.personality['role']}. Generate a warm, professional introduction for a candidate named {self.interview_state['candidate_name']}.
        **Candidate's Profile (Use ONLY this information):**
        - Role: {self.interview_state['job_role']}
        - Stated Experience: {self.interview_state['experience_text']}
        - Selected Skills: {', '.join(self.interview_state['skills_to_assess'])}
        **Your Task:**
        1. Welcome the candidate by name.
        2. Acknowledge their experience: "I see you have about {self.interview_state['experience_text']} of experience."
        3. Confirm the focus on their selected skills.
        4. Explain the structure (~{self.interview_state['max_questions']} questions).
        5. Ask if they are ready to begin.
        **Crucial Instruction: Do NOT add any extra details or assumptions (e.g., "recent graduate").**
        Keep it concise and conversational.
        """
        return self._call_gemini_api(prompt)

    # Decides which type of question to ask next and generates it.
    def generate_next_question(self) -> Dict:
        if self.interview_state["question_count"] >= self.interview_state["max_questions"]:
            return {"type": "conclusion", "message": "Interview is complete."}
        
        # --- Question Logic ---
        # The first question is always a general introduction.
        if self.interview_state["question_count"] == 0:
            question = f"Great, let's start. To begin, could you please tell me a bit about yourself and your journey as a {self.interview_state['job_role']}?"
            question_type = "introduction"
        else:
            # Mix in one behavioral question during the interview.
            question_type = "behavioral" if self.interview_state["question_count"] == 3 else "technical"
            if question_type == "technical":
                question = self._generate_technical_question()
            else:
                question = self._generate_behavioral_question()
            
        self.interview_state["question_count"] += 1
        return {"question": question, "type": question_type, "question_number": self.interview_state["question_count"], "total_questions": self.interview_state["max_questions"]}

    # Generates a technical question tailored to the user's profile.
    def _generate_technical_question(self) -> str:
        skills = self.interview_state["skills_to_assess"]
        selected_skill = random.choice(skills) if skills else "general software development"
        prompt = f"""You are an expert technical interviewer. Generate a single, high-quality interview question for a **{self.interview_state['job_role']}**. Candidate's Profile: Experience Level: {self.interview_state['experience_text']}, Stated Difficulty: **{self.interview_state['difficulty_level']}**, Specific Skill to Test: **{selected_skill}**. The question MUST be practical and its complexity MUST match the candidate's experience. For a Fresher, ask 'What is...'. For a Senior, ask about architecture or trade-offs. Return ONLY the question itself."""
        return self._call_gemini_api(prompt)

    # Generates a behavioral question tailored to the user's profile.
    def _generate_behavioral_question(self) -> str:
        template = "Tell me about a challenging project you worked on."
        prompt = f"""You are an expert interviewer. Refine the generic behavioral question "{template}" to be specific for a {self.interview_state['job_role']} with {self.interview_state['experience_text']} of experience. Tie it to concepts like code reviews, debugging, or project deadlines. Return only the refined question."""
        return self._call_gemini_api(prompt)

    # Sends the user's answer to the AI for a score and feedback.
    def evaluate_answer(self, question: str, answer: str) -> Dict:
        prompt = f"""You are an expert interviewer. Evaluate a candidate's answer. Context: Role: {self.interview_state['job_role']}, Experience: {self.interview_state['experience_text']}. Question: "{question}". Candidate's Answer: "{answer}". Provide evaluation in this exact format, with each key on a new line. Be concise.
SCORE: [A number from 1-10, based on depth and correctness for their experience level]
STRENGTHS: [A brief, one-sentence summary of what they did well]
IMPROVEMENTS: [A brief, one-sentence summary of what could be improved]"""
        feedback = self._call_gemini_api(prompt)
        return self._parse_feedback(feedback)

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
            print(f"Error parsing feedback: {e}\nOriginal feedback: {feedback}")
            return evaluation

    # This intelligent function decides what spoken feedback to give the user.
    def _generate_adaptive_feedback(self, evaluation: Dict, question: str) -> str:
        try:
            score = evaluation.get('score', 0)
            # If the score is high, give simple praise.
            if score >= 8:
                return random.choice(["Excellent, that's a great explanation.", "Very good, that's exactly what I was looking for.", "Perfect, you've hit all the key points."])
            
            # If it's the intro question, don't give a "correct" answer.
            if "tell me about yourself" in question.lower():
                return "Thanks for sharing that background. Now, let's dive into the technical questions."
            # If the score is low, provide a learning opportunity.
            else:
                learning_prompt = f"""The following interview question was asked: "{question}". A candidate gave a weak answer. Please provide a concise, ideal answer for this question, as if you were explaining it to them. Keep the explanation brief and easy to understand. Start with a phrase like 'A good way to think about it is...' or 'To clarify, a strong answer would cover...'."""
                print("...Generating a helpful tip...")
                ideal_answer = self._call_gemini_api(learning_prompt)
                
                if "Sorry, I encountered an error" in ideal_answer:
                    return "Let's move on to the next question."
                else:
                    return f"Okay, thanks for the answer. For future reference, here's a way you could approach that: {ideal_answer}"
        except Exception as e:
            print(f"Error generating adaptive feedback: {e}")
            return "Alright, let's move on."

    # Generates the final closing statement of the interview.
    def _generate_conclusion(self) -> Dict:
        scores = [ans['evaluation']['score'] for ans in self.interview_data['answers_received'] if 'evaluation' in ans]
        overall_score = sum(scores) / len(scores) if scores else 0
        self.interview_data['overall_rating'] = overall_score
        prompt = f"""Generate a professional conclusion for {self.interview_state['candidate_name']}. The interview for the {self.interview_state['job_role']} role is complete. Their score was {overall_score:.1f}/10. Thank them, give a brief positive assessment, explain next steps (e.g., 'we'll be in touch'), and end with an encouraging closing."""
        conclusion_message = self._call_gemini_api(prompt)
        return {"type": "conclusion", "message": conclusion_message, "overall_score": overall_score}

    # Compiles all collected data into a final summary report.
    def get_interview_summary(self) -> Dict:
        start_time = self.interview_data.get("start_time")
        duration = str(datetime.now() - start_time) if start_time else "N/A"
        return {"candidate_name": self.interview_state["candidate_name"], "job_role": self.interview_state["job_role"], "duration": duration, "overall_rating": self.interview_data.get("overall_rating", 0), "questions_and_answers": self.interview_data["answers_received"], "skills_assessed": self.interview_state["skills_to_assess"]}

    # --- VOICE I/O FUNCTIONS ---

    # This function speaks the text out loud instantly using an offline engine.
    def speak(self, text: str):
        try:
            print(f"\nAlex: {text}")
            # Re-initializing the engine for each call makes it more robust and prevents the "one-time voice" bug.
            tts_engine = pyttsx3.init()
            voices = tts_engine.getProperty('voices')
            tts_engine.setProperty('voice', voices[1].id if len(voices) > 1 else voices[0].id)
            tts_engine.setProperty('rate', 175) # Adjust speech speed
            tts_engine.say(text)
            tts_engine.runAndWait()
            tts_engine.stop() # Cleanly stop the engine to release resources.
        except Exception as e:
            print(f"--- Error in offline text-to-speech module: {e} ---")

    # This function listens patiently for the user's response.
    def listen(self) -> str:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("\n🎤 You can take a moment to think. I'm ready to listen whenever you start speaking...")
            r.adjust_for_ambient_noise(source, duration=1)
            try:
                # `timeout=None` waits indefinitely for the user to start speaking.
                # `phrase_time_limit=180` allows for a 3-minute long answer.
                audio = r.listen(source, timeout=None, phrase_time_limit=180)
                print("🧠 Processing your answer...")
                user_text = r.recognize_google(audio)
                print(f"You said: {user_text}")
                return user_text
            except sr.UnknownValueError:
                # If speech is unclear, politely ask the user to repeat.
                self.speak("I'm sorry, I couldn't quite make that out. Could you please try rephrasing?")
                return self.listen() # Recursive call gives the user another chance.
            except sr.RequestError as e:
                error_msg = f"There's a problem with the speech service: {e}"
                print(error_msg)
                self.speak("It seems there's a connection issue. We'll skip this one.")
                return error_msg
            except Exception as e:
                error_msg = f"An unexpected error occurred while listening: {e}"
                print(error_msg)
                self.speak("An unexpected error occurred with my listening module. Let's move on.")
                return error_msg


## ----------------------------------------------------- ##
## STAGE 4: MAIN EXECUTION BLOCK                         ##
## This is the entry point that runs the whole program.  ##
## ----------------------------------------------------- ##
if __name__ == "__main__":
    # First, check if the required libraries are installed.
    try:
        import pyttsx3
    except ImportError:
        print("The 'pyttsx3' library is not found. Please install it by running: pip install pyttsx3")
        exit()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        exit()
    
    try:
        # --- The Main Flow of the Application ---
        
        # 1. Onboard the user to create their profile.
        candidate_profile = onboard_candidate()
        
        # 2. Create and configure the AI agent with that profile.
        agent = AIInterviewAgent(google_api_key=api_key)
        intro = agent.initialize_adaptive_interview(candidate_profile)
        agent.speak(intro)
        
        # 3. Start the main interview loop.
        while agent.interview_state["question_count"] < agent.interview_state["max_questions"]:
            question_data = agent.generate_next_question()
            if not question_data.get("question") or question_data.get("type") == "conclusion":
                break

            agent.speak(question_data['question'])
            
            # --- Inner loop to handle requests to repeat the question ---
            while True:
                user_answer = agent.listen()
                
                # Check for keywords that mean the user wants the question repeated.
                repeat_keywords = ["repeat", "pardon", "say that again", "didn't hear", "didn't listen"]
                if any(keyword in user_answer.lower() for keyword in repeat_keywords):
                    agent.speak("Of course, I'll repeat the question.")
                    agent.speak(question_data['question'])
                    continue # This skips the rest of the loop and asks the user to listen again.
                else:
                    break # This exits the inner loop because we have a real answer.
            
            # --- Resume normal flow after getting a real answer ---
            
            # Store the question and the final answer.
            agent.interview_data["answers_received"].append({
                "question": question_data['question'],
                "answer": user_answer,
                "timestamp": datetime.now()
            })

            # Evaluate the answer to get a score from the AI.
            evaluation = agent.evaluate_answer(question_data['question'], user_answer)
            # Add the evaluation details to the stored answer.
            agent.interview_data["answers_received"][-1]['evaluation'] = evaluation

            # Generate the special adaptive feedback and speak it.
            spoken_feedback = agent._generate_adaptive_feedback(evaluation, question_data['question'])
            agent.speak(spoken_feedback)
        
        # 4. Generate and speak the final conclusion.
        conclusion_data = agent._generate_conclusion()
        agent.speak(conclusion_data.get('message', 'Thank you for your time.'))

        # 5. Print a final, detailed summary report to the console.
        summary = agent.get_interview_summary()
        print(f"\n\n=== Final Interview Summary ===")
        print(f"Candidate: {summary['candidate_name']} ({summary['job_role']})")
        print(f"Stated Experience: {agent.interview_state['experience_text']}")
        print(f"Overall Rating: {summary['overall_rating']:.1f}/10")
        print(f"Duration: {summary['duration']}")
        print(f"Skills Assessed: {summary['skills_assessed']}")

    except Exception as e:
        print(f"\nAn unexpected error occurred during the interview process: {e}")