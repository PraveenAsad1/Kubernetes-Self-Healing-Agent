from typing import List, Dict, Any, Optional
from datetime import datetime

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
                    old_value: Optional[str],
                    new_value: Optional[str], 
                    diagnosis: str, 
                    reason: str,
                    result: str,
                    failure_evidence: Optional[str]):
        attempt_record = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": operation,
            "old_value": str(old_value) if old_value is not None else "",
            "new_value": str(new_value) if new_value is not None else "",
            "diagnosis": diagnosis or "",
            "reason": reason or "",
            "result": result or "FAILED",
            "failure_evidence": failure_evidence or "No specific evidence recorded"
        }
        self.attempts.append(attempt_record)
        
    def get_attempts(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve past attempts, optionally filtered by run_id.
        """
        if run_id:
            return [a for a in self.attempts if a.get("run_id") == run_id]
        return self.attempts
        
    def get_attempt_count(self, run_id: Optional[str] = None) -> int:
        return len(self.get_attempts(run_id))

    def get_latest_attempt(self, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Returns the most recent attempt for the given run_id (or overall), or None.
        """
        attempts = self.get_attempts(run_id)
        if attempts:
            return attempts[-1]
        return None

    def is_duplicate_proposal(self, run_id: Optional[str], operation: str, proposed_memory: Optional[str]) -> bool:
        """
        Checks if a proposal with the same operation and proposed memory limit was already attempted.
        """
        attempts = self.get_attempts(run_id)
        prop_str = str(proposed_memory) if proposed_memory is not None else ""
        for att in attempts:
            if att.get("operation") == operation and att.get("new_value") == prop_str:
                return True
        return False
        
    def format_for_llm(self, run_id: Optional[str] = None) -> str:
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
