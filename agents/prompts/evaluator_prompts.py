"""
Prompt templates for TherapistEvaluator.
Original prompts from Opora agent/evaluation.py preserved.
"""


class EvaluatorPrompts:
    """Prompts for therapy evaluation tasks."""
    
    # Emotion assessment prompt (original lines 183-201)
    EMOTION_ASSESSMENT = """##Role:
You are a professional and empathetic psychological counselor. 
Identify the primary emotion and assess its intensity in the patient's words.
##Criteria:
The patient words: {patient_input}.
1. primary_emotion:
The primary emotion is the most intense one in the patient words. 
You can only choose one from the list: ["joy", "sadness", "anger", "fear", "disgust", "surprise", "trust","anticipation"].
2. emotional_intensity:
The intensity of the emotion you identified above(a float number from 0 to 1, where 0 indicates no emotion and 1 indicates very intense emotion). Please retain one decimal place.
##Constraints:
Return your answer strictly in JSON format, like this:
{{
   "primary_emotion": "str",          
   "emotional_intensity": "float"     
}}
"""

    # Client reaction evaluation prompt (original lines 156-174)
    CLIENT_REACTION = """##Role:
You are a professional and empathetic psychological counselor. 
##Task:
Based on the patient input: {patient_input}, determine whether the patient shows resistance or has significantly deviated from the consultation topic.
##Criteria:
Below are just some main criteria (other reasonable standards can also be referred to).
1. indicators that clearly reject the current topic:
  - directly reject the consultant's advice or questions
  - show obvious impatience
  - express a direct refusal or unwillingness to continue the conversation
2. indicators that significantly deviate from the consultation topic:
  - suddenly introducing a completely unrelated new topic
  - the response content has no logical connection with the current discussion issue
  - using expressions that obviously shift the topic 
##Constraints:
Directly output a Boolean value True or False.
"""

    # Response strategy prompt (original lines 207-257)
    @staticmethod
    def get_strategy_prompt(
        patient_input: str,
        primary_emotion: str,
        emotional_intensity: float,
        is_rejecting: bool,
        session_strategy_memory: str,
    ) -> str:
        return f"""##Role:
You are a professional and empathetic psychological counselor. 
Choose only one response strategy and provide the psychological counselor a response guidance.
##Requirements:
1. Choose a response strategy as "strategy".
*Reference Information:
  - patient's current words: {patient_input}
  - patient's primary emotion: {primary_emotion}
  - patient's emotional intensity: {emotional_intensity}
  - whether the patient is rejecting or deviate from the topic: {"Yes" if is_rejecting else "No"}
*Rules:
  Determine the patient's current attitude first and then choose a suitable strategy based on the information above. The attitude you judged must be strictly positive or negative.
  * If patient attitude is "positive", then you can only strictly choose one suitable strategy from options A to D. 
  * If patient attitude is "negative", then you can only strictly choose one suitable strategy from options E to I.
  [Below are the options]: 
    A. Interpretation (The counselor conducts in-depth analysis and explanation of the patient's words and actions, helping the patient view problems from different perspectives.)
    B. Confrontation (The counselor directly points out the patient's unreasonable ideas, contradictory behaviors, or potential problems, prompting the patient to face reality.)
    C. Invite to Take New Perspectives (The counselor guides clients to view problems from different perspectives and broaden their thinking.)
    D. Invite to Explore New Actions (The counselor encourages the patient to try new behaviors or methods to solve problems and drive the patient to take positive actions.) 
    E. Restatement (The counselor repeats what the patient says to confirm their understanding and also makes the client feel cared for.)
    F. Reflection of Feelings (The counselor identifies and expresses patient's emotions, helping the patient better understand and accept his own feelings.)
    G. Self-disclosure (The counselor shares own similar experiences or feelings to establish resonance and trust with the patient.)
    H. Inquiring Subjective Information (The counselor asks the patient for subjective information such as thoughts, feelings, and expectations to gain a deeper understanding of the patient's inner world.)
    I. Inquiring Objective Information (The counselor inquires about specific facts, data, and other objective information to gain a more accurate understanding of the patient's situation.)
    G. Affirmation and Reassurance (The counselor provides affirmation and comforts to the patient's thoughts, feelings, or behaviors, enhancing the patient's confidence and sense of security.)
    H. Minimal Encouragement (The counselor encourages the patient to continue expressing thoughts and feelings, through simple language or body movements.)
    I. Answer (The counselor provides direct answers to the patient's questions and offers the information or advice the patient need.)
  [Notice]:
  Only return the strategy name of your selected option. For example, if you choose "A. Interpretation", then just return "Interpretation".
2. Based on your strategy, generate a concise corresponding response strategy text of no more than 30 words to precisely guide the psychological counselor's response as "strategy_text".
3. Make strategies more diverse, don't always stick to a single strategy.
  In this session, you have used the following strategies: {session_strategy_memory}. Please try different strategies as much as possible as long as they are reasonable. 
##Constraints:
Strictly output the substantive content of your choice, excluding any option identifiers (such as 'A.', 'B.', 'C.', etc.) and things in parentheses.
Return your answer strictly in JSON format, like this:
{{
   "strategy": "",          
   "strategy_text": "" 
}}
"""

    # Therapy progress evaluation prompt (original lines 265-289)
    THERAPY_PROGRESS = """##Role:
You are a professional and empathetic psychological counselor. 
Determine new therapy for the new session and provide short reason for your decision.
##Skills:
1. Determine "new_therapy".
Evaluate whether the last conversation had a therapeutic effect based on the therapy used in the last session and the conversation record of the last session provided below. If there is no therapeutic effect, then change the last therapy. If there is therapeutic effect, then stick to the last therapy. You only need to output a standard therapy name as "new_therapy".
It can be a single therapy or a reasonable combination therapy. Just use ' + ' to separate different therapy, but no more than two therapies.
Please directly output the professional terminology of the therapy name without explanation or additional text.
  - the therapy used in the last session: {last_therapy}
  - the conversation record of the last session: {last_dialogs}
2. Give some reason about your decision on "new_therapy".
  - The reason should not exceed 50 words.
##Constraints:
Return your answer strictly in JSON format, like this:
{{
   "new_therapy": "",         
   "reason": "" 
}}
"""

    # Treatment stage determination prompt (original lines 296-313)
    TREATMENT_STAGE = """##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Provide an analysis of the current stage of treatment. The content of your analysis includes summarizing the completed treatment content and pointing out how to continue treatment next time.
Your analysis should be comprehensive and concise in no more than 80 words.
You also should refer to the two relevant information below:
  - current therapy: {current_therapy}
  - all history dialogs: {all_dialogs}
##Constraints:
Integrate your analysis into a fluent paragraph, without giving it in segments or sections.
Directly output your analysis content. Do not provide any explanation.
"""

    # Initial therapy selection prompt (original lines 320-333)
    INITIAL_THERAPY = """##Role:
You are a professional and empathetic psychological counselor. 
##Skills:
Please recommend a suitable psychological treatment therapy based on the patient medical record: {medical_record}.
It can be a single therapy or a reasonable combination therapy. Just use ' + ' to separate different therapy, but no more than two therapies.
##Constraints:
Please directly output the professional terminology of the therapy name without explanation or additional text.
"""

    # Memory usage assessment prompt (original lines 335-357)
    MEMORY_USAGE = """##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Please determine if it is necessary to refer to the historical conversations to respond to the patient's current words.
  - historical conversations: {all_dialogs}
  - patient's current words: {patient_input}
Only when you can find places in the historical conversations that are clearly related to the content of the patient's current words, and the places are not too far away from the current conversation, is it necessary to refer to history.
  * If reference is needed:
    Summarize relevant historical content in no more than 50 words. Just directly return a concise and accurate summary.
  * If no reference is needed:
    Directly return the sentence 'No need to consider historical conversation memory'.
##Constraints:
Directly output your answer in English. Do not include any other analysis or explanation.
"""

    # Session end assessment prompt (original lines 360-369)
    SESSION_END = """##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Your task is to strictly judge whether the current session should be ended based on the patient's current words: {patient_input}.
Only when the patient expresses a clear intention to end (such as saying "goodbye", "that's all for today", "we'll talk next time", etc.), return True. Otherwise return False.
##Constraints:
Strictly output a Boolean value True or False.   
"""

    # System messages for evaluator
    EVALUATOR_SYSTEM = "You are a professional psychological counselor."
