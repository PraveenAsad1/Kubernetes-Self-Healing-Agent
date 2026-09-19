import React from 'react';
import { Cpu, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react';

function metadataValue(event, keys) {
  if (!event?.metadata) return null;
  for (const key of keys) {
    if (event.metadata[key] !== undefined) {
      return event.metadata[key];
    }
  }
  return null;
}

export function AgentPanel({ currentRunEvents, latestEvent, status, remediationEvent, verifyEvent }) {
  const isActive = status === 'REMEDIATING';
  
  return (
    <div className="card agent-panel">
      <div className="agent-header">
        <div className="agent-icon-wrapper">
          <Cpu size={24} className={isActive ? 'status-dot pulse' : ''} />
        </div>
        <div className="agent-info">
          <h2>Self-Healing Agent</h2>
          <div className={`agent-status-text ${isActive ? 'active' : ''}`}>
            ● {isActive ? 'ACTIVE - RESOLVING INCIDENT' : 'STANDBY - MONITORING'}
          </div>
        </div>
      </div>
      
      {currentRunEvents.length > 0 ? (
        <div className="agent-details">
          <div className="agent-detail-row">
            <span className="agent-detail-label">Latest Incident</span>
            <span className="agent-detail-value">
              {latestEvent?.event_type || 'Unknown'} - {metadataValue(latestEvent, ['pod_name', 'pod']) || 'Cluster'}
            </span>
          </div>
          
          <div className="agent-detail-row">
            <span className="agent-detail-label">Current Action</span>
            <span className="agent-detail-value" style={{ color: remediationEvent ? 'var(--color-info)' : 'var(--color-text-secondary)' }}>
              {metadataValue(remediationEvent, ['operation', 'action']) || 'Analyzing telemetry...'}
            </span>
          </div>
          
          <div className="agent-detail-row">
            <span className="agent-detail-label">Verification Result</span>
            <span className="agent-detail-value" style={{
              color: verifyEvent?.status === 'SUCCESS' ? 'var(--color-success)' : 
                     verifyEvent?.status === 'ERROR' ? 'var(--color-critical)' : 'var(--color-text-secondary)'
            }}>
              {verifyEvent ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {verifyEvent.status === 'SUCCESS' ? <CheckCircle2 size={14} /> : 
                   verifyEvent.status === 'ERROR' ? <XCircle size={14} /> : <AlertCircle size={14} />}
                  {verifyEvent.status}
                </span>
              ) : 'Pending resolution'}
            </span>
          </div>
        </div>
      ) : (
        <div className="empty-state" style={{ padding: '24px 0' }}>
          <CheckCircle2 size={32} color="var(--color-success)" />
          <div style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>System Healthy</div>
          <div style={{ fontSize: '13px' }}>Agent is monitoring workloads normally.</div>
        </div>
      )}
    </div>
  );
}
