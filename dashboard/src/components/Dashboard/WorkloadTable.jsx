import React from 'react';
import { Box, ServerCrash } from 'lucide-react';

export function WorkloadTable({ latestEvent }) {
  // We do not have live workload telemetry from the backend.
  // We only display the empty state or an error if there's an active incident without full cluster state.
  
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Box size={16} />
          Kubernetes Workloads
        </div>
      </div>
      
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Workload</th>
              <th>Status</th>
              <th>Ready</th>
              <th>Restarts</th>
              <th>CPU</th>
              <th>Memory</th>
              <th>Age</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan="7">
                <div className="empty-state" style={{ padding: '32px 0' }}>
                  <ServerCrash size={32} />
                  <div style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>Awaiting Workload Telemetry</div>
                  <div style={{ fontSize: '13px', maxWidth: '300px' }}>
                    The backend is not currently broadcasting complete cluster state. Only incident-specific telemetry is recorded.
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
