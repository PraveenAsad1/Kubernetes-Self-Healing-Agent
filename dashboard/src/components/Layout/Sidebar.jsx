import React from 'react';
import { 
  LayoutDashboard, 
  Server, 
  Box, 
  AlertTriangle, 
  Activity, 
  Cpu,
  Settings 
} from 'lucide-react';

const navItems = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'cluster', label: 'Cluster', icon: Server },
  { id: 'workloads', label: 'Workloads', icon: Box },
  { id: 'incidents', label: 'Incidents', icon: AlertTriangle },
  { id: 'agent', label: 'Agent', icon: Cpu },
  { id: 'events', label: 'Events', icon: Activity },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function Sidebar({ activeTab, setActiveTab }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">SH</div>
        SAFEHEAL
      </div>
      
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div>Kubernetes Self-Healing Agent</div>
        <div style={{ marginTop: '4px', opacity: 0.6 }}>v1.0.0-beta</div>
      </div>
    </aside>
  );
}
