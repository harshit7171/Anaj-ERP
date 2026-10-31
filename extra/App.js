import React, { useState, useEffect, useCallback } from 'react';
import UploadSection from './components/UploadSection';
import ResultsDashboard from './components/ResultsDashboard';
import FormFill from './components/FormFill';
import LoginPage from './components/LoginPage';
import AgentPipeline from './components/AgentPipeline';
import { API_BASE_URL } from './config';
import './index.css';

const sampleAutofill = {
  customer_id: 'CUST-DEMO-007',
  name: 'Ava Thompson',
  dob: '1990-10-10',
  address: '22 King Street West, Toronto, ON',
  passport_number: 'PO998877',
  driving_licence: 'ON-445566',
  source_of_funds: 'Salary + Restricted Stock Units',
  occupation: 'Product Manager',
  annual_income: 175000,
};

function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [user, setUser] = useState(null);
  const [agentStatus, setAgentStatus] = useState({
    identity: 'idle',
    pep: 'idle',
    sanctions: 'idle',
    adverse: 'idle',
  });

  const pipelineResult = React.useRef('success');
  const pipelineTimers = React.useRef([]);

  const clearPipelineTimers = () => {
    pipelineTimers.current.forEach((t) => clearTimeout(t));
    pipelineTimers.current = [];
  };

  const fetchResults = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/results`);
      const data = await response.json();
      setResults(data.results || []);
    } catch (error) {
      console.error('Error fetching results:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResults();
    const interval = setInterval(fetchResults, 30000);
    return () => clearInterval(interval);
  }, [fetchResults]);

  const startPipelineSequence = () => {
    clearPipelineTimers();
    pipelineResult.current = 'success';
    setAgentStatus({
      identity: 'running',
      pep: 'idle',
      sanctions: 'idle',
      adverse: 'idle',
    });

    const t1 = setTimeout(() => {
      setAgentStatus({
        identity: 'completed',
        pep: 'running',
        sanctions: 'idle',
        adverse: 'idle',
      });
    }, 4000);

    const t2 = setTimeout(() => {
      setAgentStatus({
        identity: 'completed',
        pep: 'completed',
        sanctions: 'running',
        adverse: 'idle',
      });
    }, 8000);

    const t3 = setTimeout(() => {
      setAgentStatus({
        identity: 'completed',
        pep: 'completed',
        sanctions: 'completed',
        adverse: 'running',
      });
    }, 12000);

    const t4 = setTimeout(async () => {
      const finalStatus = pipelineResult.current === 'success' ? 'completed' : 'failed';
      setAgentStatus({
        identity: finalStatus,
        pep: finalStatus,
        sanctions: finalStatus,
        adverse: finalStatus,
      });
      if (pipelineResult.current === 'success') {
        await fetchResults();
      }
    }, 16000);

    pipelineTimers.current = [t1, t2, t3, t4];
  };

  const markPipelineResult = (ok) => {
    pipelineResult.current = ok ? 'success' : 'failed';
  };

  if (!loggedIn) {
    return (
      <div className="app-shell">
        <LoginPage
          onLogin={(u) => {
            setUser(u);
            setLoggedIn(true);
          }}
        />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-hero">
        <div>
          <p className="eyebrow">EQ Bank Compliance · Customer Screening</p>
          <h1>Customer Screening Portal</h1>
          <p className="subtext">
          Automates customer risk screening by analyzing identity, PEP, sanctions, and adverse media data to flag high-risk cases for review with full audit traceability.
          </p>
          {user && (
            <div className="pill" style={{ marginTop: 10 }}>
              Signed in as {user.email} · {user.role}
            </div>
          )}
        </div>
        <div className="hero-actions">
          {['upload', 'form', 'autofill', 'results'].map((tab) => (
            <button
              key={tab}
              className={`chip ${activeTab === tab ? 'chip-active' : ''}`}
              onClick={() => {
                setActiveTab(tab);
                if (tab === 'results') fetchResults();
              }}
            >
              {tab === 'upload' && 'Upload'}
              {tab === 'form' && 'Form Fill'}
              {tab === 'autofill' && 'Autofill Demo'}
              {tab === 'results' && 'Results'}
            </button>
          ))}
        </div>
      </header>

      <main className="content-grid">
        <section className="panel">
          <AgentPipeline status={agentStatus} />

          {activeTab === 'upload' && (
            <UploadSection
              onProcessingStart={startPipelineSequence}
              onProcessingEnd={markPipelineResult}
            />
          )}

          {activeTab === 'form' && (
            <FormFill
              title="Manual form"
              description="Blank form to mirror the API payload"
              initialData={{
                customer_id: '',
                name: '',
                dob: '',
                address: '',
                passport_number: '',
                driving_licence: '',
                source_of_funds: '',
                occupation: '',
                annual_income: '',
              }}
              onProcessingStart={startPipelineSequence}
              onProcessingEnd={markPipelineResult}
            />
          )}

          {activeTab === 'autofill' && (
            <FormFill
              title="Autofill demo"
              description="Pre-filled demo data for quick walk-through"
              initialData={sampleAutofill}
              onProcessingStart={startPipelineSequence}
              onProcessingEnd={markPipelineResult}
            />
          )}

          {activeTab === 'results' && (
            <ResultsDashboard
              results={results}
              loading={loading}
              onRefresh={fetchResults}
            />
          )}
        </section>
      </main>
    </div>
  );
}

export default App;


