import { useEffect, useMemo, useState } from 'react'
import { supabase } from './supabase'
import './App.css'

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
]

function sortEvents(eventList) {
  return [...eventList].sort((left, right) => {
    const timestampDifference =
      new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()

    if (timestampDifference !== 0) return timestampDifference
    return String(left.id).localeCompare(String(right.id))
  })
}

function App() {
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)

  async function loadEvents() {
    const { data, error } = await supabase
      .from('incident_events')
      .select('*')
      .order('timestamp', { ascending: true })

    if (error) {
      console.error('Failed to load events:', error)
      setConnected(false)
      setLoading(false)
      return
    }

    setEvents((current) => {
      const merged = new Map(current.map((event) => [event.id, event]))
      for (const event of data || []) merged.set(event.id, event)
      return sortEvents([...merged.values()])
    })
    setConnected(true)
    setLoading(false)
  }

  useEffect(() => {
    loadEvents()

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
          console.log('Realtime INSERT payload:', payload)
          setEvents((current) => {
            if (current.some((event) => event.id === payload.new.id)) {
              return current
            }

            return sortEvents([...current, payload.new])
          })
        },
      )
      .subscribe((status, error) => {
        console.log('Realtime status:', status)

        if (status === 'SUBSCRIBED') {
          setConnected(true)
        } else if (
          status === 'CHANNEL_ERROR' ||
          status === 'TIMED_OUT' ||
          status === 'CLOSED'
        ) {
          setConnected(false)
          console.error(`Realtime ${status}:`, error || 'No error details')
        }
      })

    return () => {
      console.log('Realtime channel cleanup')
      supabase.removeChannel(channel)
    }
  }, [])

  const orderedEvents = useMemo(() => sortEvents(events), [events])
  const latestEvent = orderedEvents[orderedEvents.length - 1]

  const latestRunId = latestEvent?.run_id

  const currentRunEvents = useMemo(() => {
    if (!latestRunId) return []
    return orderedEvents.filter((event) => event.run_id === latestRunId)
  }, [orderedEvents, latestRunId])

  const latestStageEvent = [...currentRunEvents]
    .reverse()
    .find((event) => FSM_STATES.includes(event.stage))
  const currentState = latestStageEvent?.stage || 'IDLE'

  const incidentActive =
    currentState !== 'RESOLVED' &&
    currentState !== 'ESCALATED' &&
    currentRunEvents.length > 0

  const status =
    currentState === 'RESOLVED'
      ? 'RESOLVED'
      : currentState === 'ESCALATED'
        ? 'ESCALATED'
        : incidentActive
          ? 'REMEDIATING'
          : 'OPERATIONAL'

  function stateReached(state) {
    return currentRunEvents.some((event) => event.stage === state)
  }

  function stateStatus(state) {
    const stateEvents = currentRunEvents.filter((event) => event.stage === state)
    if (!stateEvents.length) return 'pending'

    if (state === currentState) {
      const latestStateEvent = stateEvents[stateEvents.length - 1]
      const terminalStatus = ['SUCCESS', 'RESOLVED', 'ERROR', 'ESCALATED'].includes(
        latestStateEvent.status?.toUpperCase(),
      )
      return terminalStatus ? 'complete' : 'active'
    }

    if (stateReached(state)) return 'complete'
    return 'pending'
  }

  const remediationEvent = currentRunEvents.find(
    (event) =>
      event.event_type?.toLowerCase().includes('remedi') ||
      event.stage === 'REMEDIATE',
  )

  const policyEvent = currentRunEvents.find(
    (event) => event.stage === 'POLICY_CHECK',
  )

  const hitlEvent = currentRunEvents.find(
    (event) => event.stage === 'HITL',
  )

  const verifyEvent = currentRunEvents.find(
    (event) => event.stage === 'VERIFY',
  )

  function formatTime(timestamp) {
    if (!timestamp) return '—'

    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  function metadataValue(event, keys) {
    if (!event?.metadata) return null

    for (const key of keys) {
      if (event.metadata[key] !== undefined) {
        return event.metadata[key]
      }
    }

    return null
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <div className="brand">
            <span className="brand-mark">SH</span>
            SAFEHEAL
          </div>
          <div className="subtitle">
            POLICY-CONTROLLED KUBERNETES SELF-HEALING AGENT
          </div>
        </div>

        <div className="system-status">
          <span className={`status-dot ${connected ? 'online' : 'offline'}`} />
          <span>{connected ? 'SYSTEM CONNECTED' : 'DISCONNECTED'}</span>
        </div>
      </header>

      <main>
        <section className="hero-grid">
          <div className="hero-card">
            <div className="eyebrow">SYSTEM STATUS</div>
            <div className="hero-status">{status}</div>
            <p>
              SafeHeal observes Kubernetes incidents, proposes bounded
              remediation, validates policy, and verifies recovery.
            </p>
          </div>

          <div className="metric-card">
            <span>FSM STATE</span>
            <strong>{currentState}</strong>
          </div>

          <div className="metric-card">
            <span>EVENTS</span>
            <strong>{currentRunEvents.length}</strong>
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">INCIDENT CONTROL</div>
              <h2>CURRENT INCIDENT</h2>
            </div>
            {latestRunId && (
              <code className="run-id">
                RUN {latestRunId}
              </code>
            )}
          </div>

          {loading ? (
            <div className="empty">Loading incident data...</div>
          ) : !latestRunId ? (
            <div className="empty">
              No SafeHeal incidents recorded yet.
            </div>
          ) : (
            <div className="incident-grid">
              <div className="incident-main">
                <span className="label">LATEST EVENT</span>
                <h3>{latestEvent?.event_type || 'UNKNOWN'}</h3>
                <p>{latestEvent?.message || 'No message available.'}</p>
              </div>

              <div className="detail">
                <span className="label">POD</span>
                <strong>
                  {metadataValue(latestEvent, ['pod_name', 'pod']) || '—'}
                </strong>
              </div>

              <div className="detail">
                <span className="label">OPERATION</span>
                <strong>
                  {metadataValue(remediationEvent, [
                    'operation',
                    'action',
                  ]) || '—'}
                </strong>
              </div>

              <div className="detail">
                <span className="label">VERIFICATION</span>
                <strong>
                  {verifyEvent?.status || 'PENDING'}
                </strong>
              </div>
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">STATE MACHINE</div>
              <h2>LIVE FSM TIMELINE</h2>
            </div>
          </div>

          <div className="timeline">
            {FSM_STATES.map((state, index) => {
              const stateClass = stateStatus(state)

              return (
                <div className="timeline-item" key={state}>
                  <div className={`timeline-marker ${stateClass}`}>
                    {stateClass === 'complete' ? '✓' : index + 1}
                  </div>

                  <div className="timeline-content">
                    <strong>{state}</strong>

                    <span>
                      {stateClass === 'complete'
                        ? formatTime(
                            currentRunEvents.find(
                              (event) => event.stage === state,
                            )?.timestamp,
                          )
                        : stateClass === 'active'
                          ? 'IN PROGRESS'
                          : 'PENDING'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        <section className="ledger-section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">AUDIT TRAIL</div>
              <h2>ACTION / POLICY LEDGER</h2>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>TIME</th>
                  <th>STAGE</th>
                  <th>EVENT</th>
                  <th>STATUS</th>
                  <th>MESSAGE</th>
                </tr>
              </thead>

              <tbody>
                {currentRunEvents
                  .slice()
                  .reverse()
                  .map((event) => (
                    <tr key={event.id}>
                      <td className="mono">{formatTime(event.timestamp)}</td>
                      <td>
                        <span className="stage">{event.stage}</span>
                      </td>
                      <td className="mono">{event.event_type}</td>
                      <td>
                        <span
                          className={`result result-${event.status?.toLowerCase()}`}
                        >
                          {event.status}
                        </span>
                      </td>
                      <td>{event.message}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="summary-grid">
          <div className="summary-card">
            <span className="label">POLICY</span>
            <strong>{policyEvent?.status || 'PENDING'}</strong>
          </div>

          <div className="summary-card">
            <span className="label">HUMAN APPROVAL</span>
            <strong>{hitlEvent?.status || 'PENDING'}</strong>
          </div>

          <div className="summary-card">
            <span className="label">REMEDIATION</span>
            <strong>{remediationEvent?.status || 'PENDING'}</strong>
          </div>

          <div className="summary-card">
            <span className="label">VERIFICATION</span>
            <strong>{verifyEvent?.status || 'PENDING'}</strong>
          </div>
        </section>
      </main>

      <footer>
        SAFEHEAL / KUBERNETES SELF-HEALING AGENT
        <span>READ-ONLY OBSERVABILITY</span>
      </footer>
    </div>
  )
}

export default App