import React from 'react';

const FSM_STATES = [
  'DETECT',
  'INVESTIGATE',
  'DIAGNOSE',
  'PROPOSE',
  'POLICY_CHECK',
  'HITL',
  'REMEDIATE',
  'VERIFY',
  'RESOLVED',
  'REFLEXION',
  'ESCALATED',
];

export function IncidentTimeline({ currentRunEvents, currentState, stateStatus, formatTime }) {
  if (currentRunEvents.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">Incident Timeline</div>
        </div>
        <div className="empty-state">
          <div style={{ color: 'var(--color-text-primary)' }}>No Active Timeline</div>
          <div style={{ fontSize: '13px' }}>Awaiting incident detection.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">Live FSM Timeline</div>
      </div>
      
      <div className="timeline-container">
        {FSM_STATES.map((state) => {
          const stateClass = stateStatus(state);
          const event = currentRunEvents.find(e => e.stage === state);
          
          return (
            <div className={`timeline-item ${stateClass}`} key={state}>
              <div className="timeline-marker">
                {stateClass === 'complete' && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                )}
                {stateClass === 'active' && (
                  <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor' }} />
                )}
              </div>
              
              <div className="timeline-content">
                <div className="timeline-header">
                  <span className="timeline-title">{state}</span>
                  <span className="timeline-time">
                    {stateClass === 'complete' ? formatTime(event?.timestamp) : (stateClass === 'active' ? 'IN PROGRESS' : '')}
                  </span>
                </div>
                {event?.message && (
                  <div className="timeline-desc">{event.message}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
