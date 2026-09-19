import React from 'react';
import { Bell, User } from 'lucide-react';

export function Header({ connected, status }) {
  return (
    <header className="top-header">
      <div className="header-title">
        Control Center
      </div>
      
      <div className="header-actions">
        <div className="status-badge">
          <span className={`status-dot ${connected ? (status === 'REMEDIATING' ? 'pulse online' : 'online') : 'offline'}`} />
          {connected ? 'CLUSTER CONNECTED' : 'DISCONNECTED'}
        </div>
        
        <button className="nav-item" style={{ padding: '8px', width: 'auto' }}>
          <Bell size={18} />
        </button>
        <button className="nav-item" style={{ padding: '8px', width: 'auto' }}>
          <User size={18} />
        </button>
      </div>
    </header>
  );
}
