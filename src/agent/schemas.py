from pydantic import BaseModel, Field
from typing import List, Optional

class IncidentInfo(BaseModel):
    type: str = Field(..., description="Type of the incident, e.g., OOMKilled")
    namespace: str = Field(..., description="Namespace of the affected workload")
    workload: str = Field(..., description="Name of the affected workload/deployment")

class DiagnosisInfo(BaseModel):
    probable_cause: str = Field(..., description="The probable cause of the incident based on evidence")
    confidence: float = Field(..., description="Confidence level in the diagnosis, between 0.0 and 1.0")
    evidence: List[str] = Field(..., description="List of key evidence points used for the diagnosis")
    reflection: Optional[str] = Field(None, description="Reflection on previous failed attempts, why they failed, and why this proposal addresses it")

class ProposedAction(BaseModel):
    operation: str = Field(..., description="The operation to perform, e.g., increase_memory_limit or escalate")
    resource: str = Field(..., description="The target resource name")
    current_memory: Optional[str] = Field(None, description="Current memory limit (if applicable)")
    proposed_memory: Optional[str] = Field(None, description="Proposed new memory limit (if applicable)")
    reason: str = Field(..., description="Reasoning for this specific proposed action")

class RemediationProposal(BaseModel):
    incident: IncidentInfo
    diagnosis: DiagnosisInfo
    proposed_action: ProposedAction
