import sys
from src.agent.schemas import RemediationProposal
from src.safety.policy_engine import requires_human_approval

def request_approval(proposal: RemediationProposal) -> bool:
    """
    Presents the proposed action to a human operator via the terminal and blocks until a response is given.
    Returns True if approved, False otherwise.
    """
    action = proposal.proposed_action
    incident = proposal.incident
    
    if not requires_human_approval(action.operation):
        print(f"[HITL] Operation '{action.operation}' does not require human approval according to policy. Auto-approving.")
        return True

    print("\n" + "="*50)
    print("SAFEHEAL ACTION REQUEST")
    print("="*50)
    print(f"Namespace: {incident.namespace}")
    print(f"Deployment: {incident.workload}")
    print("-" * 50)
    print(f"Operation: {action.operation}")
    
    if action.current_memory and action.proposed_memory:
        print(f"Current memory limit: {action.current_memory}")
        print(f"Proposed memory limit: {action.proposed_memory}")
        
    print("-" * 50)
    print("Reason:")
    print(action.reason)
    print("-" * 50)
    print("Policy:")
    print("PASS")
    print("="*50)
    
    while True:
        try:
            response = input("Approve remediation? [y/N]: ").strip().lower()
            if response == 'y' or response == 'yes':
                return True
            elif response == 'n' or response == 'no' or response == '':
                return False
            else:
                print("Please answer 'y' or 'N'.")
        except EOFError:
            # Handle non-interactive environments safely
            print("\n[HITL] EOF encountered. Defaulting to rejection.")
            return False
        except KeyboardInterrupt:
            print("\n[HITL] Interrupted. Defaulting to rejection.")
            return False
