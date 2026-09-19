import React from 'react';

export function StatCard({ title, value, description, icon: Icon, valueClass = '' }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          {Icon && <Icon size={16} />}
          {title}
        </div>
      </div>
      <div>
        <div className={`stat-value ${valueClass}`}>{value}</div>
        <div className="stat-desc">{description}</div>
      </div>
    </div>
  );
}
