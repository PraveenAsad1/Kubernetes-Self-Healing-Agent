import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

from .schemas import RemediationProposal
from .prompts import SYSTEM_PROMPT, build_incident_prompt

load_dotenv()
logger = logging.getLogger(__name__)

# Client is created lazily inside analyze_incident() so that importing this
# module in test environments (without GROQ_API_KEY set) does not raise.
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

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
    
    prompt += (
        "\n## Required JSON schema\n"
        f"{json.dumps(RemediationProposal.model_json_schema(), indent=2)}\n"
        "Return ONLY a JSON object that matches this schema. "
        "Top-level keys must be incident, diagnosis, and proposed_action.\n"
    )

    logger.info(f"Sending incident data to Groq (Model: {DEFAULT_MODEL})...")
    
    try:
        # Lazy client initialization — only requires GROQ_API_KEY at call time, not import time.
        client = Groq()
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
