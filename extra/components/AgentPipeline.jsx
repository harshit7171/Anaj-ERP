import React from 'react';

const statusTone = {
  idle: { bg: 'rgba(148, 163, 184, 0.15)', color: '#475569', label: 'Idle' },
  running: { bg: 'rgba(59, 130, 246, 0.12)', color: '#1d4ed8', label: 'Running' },
  completed: { bg: 'rgba(16, 185, 129, 0.12)', color: '#047857', label: 'Completed' },
  failed: { bg: 'rgba(239, 68, 68, 0.12)', color: '#b91c1c', label: 'Failed' },
};

const AgentBox = ({ title, desc, status }) => {
  const tone = statusTone[status] || statusTone.idle;
  return (
    <div className="agent-box" style={{ borderColor: tone.bg }}>
      <div className="agent-box-head">
        <div className="agent-dot" style={{ background: tone.color }} />
        <div>
          <div className="agent-title">{title}</div>
          <div className="agent-desc">{desc}</div>
        </div>
      </div>
      <div className="agent-status" style={{ background: tone.bg, color: tone.color }}>
        {tone.label}
      </div>
    </div>
  );
};

const AgentPipeline = ({ status }) => {
  return (
    <div className="agent-pipeline">
      <AgentBox
        title="Identity Agent"
        desc="Verify identity documents and match key attributes"
        status={status.identity}
      />
      <AgentBox
        title="PEP Agent"
        desc="Screen against PEP/Political Exposed Person watchlists"
        status={status.pep}
      />
      <AgentBox
        title="Sanctions Agent"
        desc="Check global sanctions lists Canada Follow and adverse indicators "
        status={status.sanctions}
      />
      <AgentBox
        title="Adverse Media Agent"
        desc="Scan news/media for negative mentions or any criminal records"
        status={status.adverse}
      />
    </div>
  );
};

export default AgentPipeline;

