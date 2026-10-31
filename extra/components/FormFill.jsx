import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const defaultTemplate = {
  customer_id: '',
  name: '',
  dob: '',
  address: '',
  passport_number: '',
  driving_licence: '',
  source_of_funds: '',
  occupation: '',
  annual_income: '',
};

const sampleTemplate = {
  customer_id: 'CUST-001',
  name: 'John Smith',
  dob: '1985-05-15',
  address: '123 Main Street, Toronto, ON',
  passport_number: 'AB123456',
  driving_licence: 'ON-998877',
  source_of_funds: 'Employment - Software Engineer',
  occupation: 'Software Engineer',
  annual_income: 120000,
};

const FormFill = ({ title, description, initialData = defaultTemplate, onProcessingStart, onProcessingEnd }) => {
  const [form, setForm] = useState(initialData);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setForm(initialData);
  }, [initialData]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleAutofill = () => {
    setForm(sampleTemplate);
    setMessage({ type: 'success', text: 'Sample data pre-filled. Review and submit.' });
  };

  const handleClear = () => {
    setForm(defaultTemplate);
    setMessage(null);
  };

  const handleSubmit = async () => {
    if (!form.customer_id || !form.name) {
      setMessage({ type: 'error', text: 'Customer ID and Name are required.' });
      return;
    }

    if (onProcessingStart) onProcessingStart();

    setLoading(true);
    setMessage(null);
    try {
      const payload = {
        customer_id: form.customer_id,
        customer_data: {
          name: form.name,
          dob: form.dob,
          address: form.address,
          passport_number: form.passport_number,
          driving_licence: form.driving_licence,
          source_of_funds: form.source_of_funds,
          occupation: form.occupation,
          annual_income: Number(form.annual_income) || form.annual_income,
        },
      };

      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const formData = new FormData();
      formData.append('file', blob, `${form.customer_id || 'form-entry'}.json`);

      await axios.post(`${API_BASE_URL}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setMessage({ type: 'success', text: 'Submitted for screening' });
      if (onProcessingEnd) onProcessingEnd(true);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Submission failed. Please try again.',
      });
      if (onProcessingEnd) onProcessingEnd(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p className="eyebrow" style={{ color: '#5b6678' }}>{title}</p>
          <h2 style={{ marginBottom: 6 }}>{description}</h2>
          <p style={{ color: '#5b6678', margin: 0 }}>Build JSON once, submit to the same /api/upload endpoint.</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="button button-warning" onClick={handleAutofill} type="button">
            Autofill sample
          </button>
          <button className="button" onClick={handleClear} type="button">
            Clear
          </button>
        </div>
      </div>

      {message && (
        <div className={message.type === 'error' ? 'error' : 'success'} style={{ marginTop: 12 }}>
          {message.text}
        </div>
      )}

      <div className="form-grid" style={{ marginTop: 16 }}>
        <div className="form-group">
          <label>Customer ID*</label>
          <input
            className="input"
            value={form.customer_id}
            onChange={(e) => handleChange('customer_id', e.target.value)}
            placeholder="CUST-123"
          />
        </div>
        <div className="form-group">
          <label>Name*</label>
          <input
            className="input"
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="Jane Doe"
          />
        </div>
        <div className="form-group">
          <label>Date of Birth</label>
          <input
            className="input"
            type="date"
            value={form.dob}
            onChange={(e) => handleChange('dob', e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Address</label>
          <input
            className="input"
            value={form.address}
            onChange={(e) => handleChange('address', e.target.value)}
            placeholder="123 Main Street, City, Country"
          />
        </div>
        <div className="form-group">
          <label>Passport Number</label>
          <input
            className="input"
            value={form.passport_number}
            onChange={(e) => handleChange('passport_number', e.target.value)}
            placeholder="AB123456"
          />
        </div>
        <div className="form-group">
          <label>Driving Licence</label>
          <input
            className="input"
            value={form.driving_licence}
            onChange={(e) => handleChange('driving_licence', e.target.value)}
            placeholder="ON-998877"
          />
        </div>
        <div className="form-group">
          <label>Source of Funds</label>
          <input
            className="input"
            value={form.source_of_funds}
            onChange={(e) => handleChange('source_of_funds', e.target.value)}
            placeholder="Employment - Software Engineer"
          />
        </div>
        <div className="form-group">
          <label>Occupation</label>
          <input
            className="input"
            value={form.occupation}
            onChange={(e) => handleChange('occupation', e.target.value)}
            placeholder="Software Engineer"
          />
        </div>
        <div className="form-group">
          <label>Annual Income</label>
          <input
            className="input"
            type="number"
            value={form.annual_income}
            onChange={(e) => handleChange('annual_income', e.target.value)}
            placeholder="120000"
          />
        </div>
      </div>

      <div className="preview-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p className="eyebrow" style={{ margin: 0 }}>Preview payload</p>
          <div className="pill">POST /api/upload</div>
        </div>
        <pre className="code-block">
{JSON.stringify({
  customer_id: form.customer_id || 'CUST-XXX',
  customer_data: {
    name: form.name || 'Name',
    dob: form.dob || 'YYYY-MM-DD',
    address: form.address || 'Address',
    passport_number: form.passport_number || 'Passport',
    driving_licence: form.driving_licence || 'Licence',
    source_of_funds: form.source_of_funds || 'Source',
    occupation: form.occupation || 'Occupation',
    annual_income: form.annual_income || 'Income'
  }
}, null, 2)}
        </pre>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="button button-success" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Submitting...' : 'Submit to Screening'}
        </button>
      </div>
    </div>
  );
};

export default FormFill;

