from typing import List, Dict, Any
from datetime import datetime
import json

class ReflexionStore:
    """
    In-memory store for tracking previous remediation attempts and their results.
    For the hackathon, we keep this in memory per run_id, but it could be backed by a DB.
    """
    def __init__(self):
        self.attempts: List[Dict[str, Any]] = []
        
    def add_attempt(self, 
                    run_id: str,
                    operation: str,
                    old_value: str,
                    new_value: str, 
                    diagnosis: str, 
                    reason: str,
                    result: str,
                    failure_evidence: str):
        attempt_record = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": operation,
            "old_value": old_value,
            "new_value": new_value,
            "diagnosis": diagnosis,
            "reason": reason,
            "result": result,
            "failure_evidence": failure_evidence
        }
        self.attempts.append(attempt_record)
        
    def get_attempts(self, run_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve past attempts, optionally filtered by run_id.
        """
        if run_id:
            return [a for a in self.attempts if a["run_id"] == run_id]
        return self.attempts
        
    def get_attempt_count(self, run_id: str = None) -> int:
        return len(self.get_attempts(run_id))
        
    def format_for_llm(self, run_id: str = None) -> str:
        """
        Formats the attempts into a readable string for the LLM prompt.
        """
        relevant_attempts = self.get_attempts(run_id)
        if not relevant_attempts:
            return "No previous attempts."
            
        output = []
        for i, attempt in enumerate(relevant_attempts, 1):
            output.append(f"Attempt {i}:")
            output.append(f"- Operation: {attempt['operation']}")
            output.append(f"- Transition: {attempt['old_value']} -> {attempt['new_value']}")
            output.append(f"- Result: {attempt['result']}")
            output.append(f"- Failure Evidence: {attempt['failure_evidence']}")
            output.append(f"- Previous Diagnosis: {attempt['diagnosis']}")
            output.append("")
            
        return "\n".join(output)
