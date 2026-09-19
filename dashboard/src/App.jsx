import { useEffect, useMemo, useState } from 'react';
import { supabase } from './supabase';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';
import { StatCard } from './components/Dashboard/StatCard';
import { AgentPanel } from './components/Dashboard/AgentPanel';
import { IncidentTimeline } from './components/Dashboard/IncidentTimeline';
import { WorkloadTable } from './components/Dashboard/WorkloadTable';
import { Activity, ShieldCheck, Server, AlertTriangle } from 'lucide-react';
import './App.css';

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

function sortEvents(eventList) {
  return [...eventList].sort((left, right) => {
    const timestampDifference =
      new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime();

    if (timestampDifference !== 0) return timestampDifference;
    return String(left.id).localeCompare(String(right.id));
  });
}

function formatTime(timestamp) {
  if (!timestamp) return '—';
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function App() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  async function loadEvents() {
    const { data, error } = await supabase
      .from('incident_events')
      .select('*')
      .order('timestamp', { ascending: true });

    if (error) {
      console.error('Failed to load events:', error);
      setConnected(false);
      setLoading(false);
      return;
    }

    setEvents((current) => {
      const merged = new Map(current.map((event) => [event.id, event]));
      for (const event of data || []) merged.set(event.id, event);
      return sortEvents([...merged.values()]);
    });
    setConnected(true);
    setLoading(false);
  }

  useEffect(() => {
    loadEvents();

    const channel = supabase
      .channel('incident-events')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'incident_events',
        },
        (payload) => {
          setEvents((current) => {
            if (current.some((event) => event.id === payload.new.id)) {
              return current;
            }
            return sortEvents([...current, payload.new]);
          });
        },
      )
      .subscribe((status, error) => {
        if (status === 'SUBSCRIBED') {
          setConnected(true);
        } else if (
          status === 'CHANNEL_ERROR' ||
          status === 'TIMED_OUT' ||
          status === 'CLOSED'
        ) {
          setConnected(false);
        }
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const orderedEvents = useMemo(() => sortEvents(events), [events]);
  const latestEvent = orderedEvents[orderedEvents.length - 1];
  const latestRunId = latestEvent?.run_id;

  const currentRunEvents = useMemo(() => {
    if (!latestRunId) return [];
    return orderedEvents.filter((event) => event.run_id === latestRunId);
  }, [orderedEvents, latestRunId]);

  const latestStageEvent = [...currentRunEvents]
    .reverse()
    .find((event) => FSM_STATES.includes(event.stage));
  const currentState = latestStageEvent?.stage || 'IDLE';

  const incidentActive =
    currentState !== 'RESOLVED' &&
    currentState !== 'ESCALATED' &&
    currentRunEvents.length > 0;

  const status =
    currentState === 'RESOLVED'
      ? 'RESOLVED'
      : currentState === 'ESCALATED'
        ? 'ESCALATED'
        : incidentActive
          ? 'REMEDIATING'
          : 'OPERATIONAL';

  function stateReached(state) {
    return currentRunEvents.some((event) => event.stage === state);
  }

  function stateStatus(state) {
    const stateEvents = currentRunEvents.filter((event) => event.stage === state);
    if (!stateEvents.length) return 'pending';

    if (state === currentState) {
      const stateLatestEvent = stateEvents[stateEvents.length - 1];
      const terminalStatus = ['SUCCESS', 'RESOLVED', 'ERROR', 'ESCALATED'].includes(
        stateLatestEvent.status?.toUpperCase(),
      );
      return terminalStatus ? 'complete' : 'active';
    }

    if (stateReached(state)) return 'complete';
    return 'pending';
  }

  const remediationEvent = currentRunEvents.find(
    (event) =>
      event.event_type?.toLowerCase().includes('remedi') ||
      event.stage === 'REMEDIATE',
  );

  const policyEvent = currentRunEvents.find(
    (event) => event.stage === 'POLICY_CHECK',
  );

  const verifyEvent = currentRunEvents.find(
    (event) => event.stage === 'VERIFY',
  );

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <div className="main-wrapper">
        <Header connected={connected} status={status} />
        
        <div className="dashboard-content">
          <div className="page-header">
            <h1>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</h1>
            <p>Kubernetes SRE Control Center</p>
          </div>
          
          {loading ? (
            <div className="empty-state">
              <Activity className="status-dot pulse" size={32} />
              <div style={{ marginTop: '16px' }}>Connecting to telemetry stream...</div>
            </div>
          ) : (
            <>
              {activeTab === 'overview' && (
                <>
                  <div className="metrics-grid">
                    <StatCard 
                      title="Cluster Health" 
                      value="N/A" 
                      description="Awaiting telemetry" 
                      icon={Server} 
                    />
                    <StatCard 
                      title="Agent Status" 
                      value={status} 
                      description={currentState !== 'IDLE' ? `Stage: ${currentState}` : 'Monitoring Workloads'} 
                      icon={ShieldCheck} 
                      valueClass={status === 'OPERATIONAL' || status === 'RESOLVED' ? 'text-success' : 'text-agent'}
                    />
                    <StatCard 
                      title="Active Incidents" 
                      value={incidentActive ? '1' : '0'} 
                      description="Current Run Events" 
                      icon={AlertTriangle} 
                    />
                  </div>

                  <div className="dashboard-main-grid">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                      <AgentPanel 
                        currentRunEvents={currentRunEvents}
                        latestEvent={latestEvent}
                        status={status}
                        remediationEvent={remediationEvent}
                        verifyEvent={verifyEvent}
                      />
                      <WorkloadTable latestEvent={latestEvent} />
                    </div>
                    
                    <div>
                      <IncidentTimeline 
                        currentRunEvents={currentRunEvents}
                        currentState={currentState}
                        stateStatus={stateStatus}
                        formatTime={formatTime}
                      />
                    </div>
                  </div>
                  
                  <div className="dashboard-bottom-grid">
                    <div className="card">
                      <div className="card-header" style={{ marginBottom: 0 }}>
                        <div className="card-title">Event Ledger</div>
                        {latestRunId && <div className="badge badge-neutral">RUN {latestRunId}</div>}
                      </div>
                      
                      <div className="table-wrapper">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Time</th>
                              <th>Stage</th>
                              <th>Event</th>
                              <th>Status</th>
                              <th>Message</th>
                            </tr>
                          </thead>
                          <tbody>
                            {currentRunEvents.length === 0 ? (
                              <tr>
                                <td colSpan="5">
                                  <div className="empty-state" style={{ padding: '24px' }}>
                                    No events for current run.
                                  </div>
                                </td>
                              </tr>
                            ) : (
                              currentRunEvents.slice().reverse().map((event) => {
                                const st = event.status?.toLowerCase();
                                const isSuccess = ['success', 'resolved', 'approved', 'pass'].includes(st);
                                const isFail = ['failed', 'denied', 'error', 'escalated'].includes(st);
                                
                                return (
                                  <tr key={event.id}>
                                    <td style={{ fontFamily: 'monospace' }}>{formatTime(event.timestamp)}</td>
                                    <td><span className="badge badge-neutral">{event.stage}</span></td>
                                    <td className="td-strong">{event.event_type}</td>
                                    <td>
                                      {event.status && (
                                        <span className={`badge ${isSuccess ? 'badge-success' : isFail ? 'badge-critical' : 'badge-neutral'}`}>
                                          {event.status}
                                        </span>
                                      )}
                                    </td>
                                    <td>{event.message}</td>
                                  </tr>
                                );
                              })
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </>
              )}
              
              {activeTab !== 'overview' && (
                <div className="empty-state card">
                  <Activity size={32} />
                  <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Module</h2>
                  <p>This module is under construction.</p>
                  <button className="nav-item" onClick={() => setActiveTab('overview')} style={{ width: 'auto', background: 'var(--color-bg-surface-hover)' }}>
                    Return to Overview
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;