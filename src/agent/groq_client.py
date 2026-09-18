import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

from .schemas import RemediationProposal
from .prompts import SYSTEM_PROMPT, build_incident_prompt

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize Groq client
# This expects GROQ_API_KEY to be set in environment variables or .env file
client = Groq()
# We will use llama3-8b-8192 or llama3-70b-8192 for the hackathon
DEFAULT_MODEL = "llama3-70b-8192"

def analyze_incident(
    namespace: str,
    deployment: str, 
    pod_name: str,
    status: dict, 
    logs: str, 
    events: list, 
    limits: dict, 
    sop_content: str,
    previous_attempts: list = None
) -> RemediationProposal:
    """
    Analyzes the incident using Groq LLM and returns a structured RemediationProposal.
    """
    prompt = build_incident_prompt(
        namespace=namespace,
        deployment=deployment,
        pod_name=pod_name,
        status=status,
        logs=logs,
        events=events,
        limits=limits,
        sop_content=sop_content,
        previous_attempts=previous_attempts
    )
    
    logger.info(f"Sending incident data to Groq (Model: {DEFAULT_MODEL})...")
    
    try:
        # Use structured output feature of Groq or simply instruct it to output JSON
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            temperature=0.1, # Low temperature for more deterministic/analytical response
        )
        
        response_text = chat_completion.choices[0].message.content
        logger.debug(f"Raw LLM Response: {response_text}")
        
        # Parse the JSON response into our Pydantic model
        response_json = json.loads(response_text)
        proposal = RemediationProposal(**response_json)
        
        return proposal
        
    except Exception as e:
        logger.error(f"Error during LLM analysis: {e}")
        # Return a safe fallback or re-raise
        raise e
