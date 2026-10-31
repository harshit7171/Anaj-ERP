import React, { useMemo, useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const ResultsDashboard = ({ results, loading, onRefresh }) => {
  const [filter, setFilter] = useState('all');
  const [selectedResult, setSelectedResult] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingResult, setEditingResult] = useState(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    status: 'verified',
    notes: '',
    reviewer: '',
  });
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState(null);

  const getStatusBadge = (status) => {
    const statusClass = `status-badge status-${status === 'verified' ? 'verified' : status === 'rejected' ? 'rejected' : 'pending'}`;
    return <span className={statusClass}>{status || 'pending'}</span>;
  };

  const filteredResults = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return results.filter((result) => {
      const matchesFilter = filter === 'all' || result.status === filter;
      const matchesSearch =
        term === '' ||
        result.customer_id?.toLowerCase().includes(term) ||
        result.customer_data?.name?.toLowerCase().includes(term);
      return matchesFilter && matchesSearch;
    });
  }, [results, filter, searchTerm]);

  const handleViewDetails = async (customerId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/result/${customerId}`);
      setSelectedResult(response.data);
    } catch (error) {
      console.error('Error fetching details:', error);
    }
  };

  const handleDownloadReport = async (customerId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/download/${customerId}`);
      
      // Create downloadable JSON file
      const dataStr = JSON.stringify(response.data, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `screening_report_${customerId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading report:', error);
    }
  };

  const handleOpenEdit = async (customerId) => {
    setEditError(null);
    setEditLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/result/${customerId}`);
      const data = response.data;
      setEditingResult(data);
      setEditForm({
        status: data.status || 'pending_review',
        notes: data.manual_review?.notes || '',
        reviewer: data.manual_review?.reviewer || '',
      });
      setEditModalOpen(true);
    } catch (error) {
      setEditError(error.response?.data?.detail || 'Unable to open edit panel');
    } finally {
      setEditLoading(false);
    }
  };

  const handleSubmitEdit = async () => {
    if (!editingResult) return;
    if (!editForm.reviewer.trim()) {
      setEditError('Reviewer (specialist) is required');
      return;
    }

    setEditLoading(true);
    setEditError(null);
    try {
      const payload = {
        status: editForm.status,
        notes: editForm.notes,
        reviewer: editForm.reviewer.trim(),
      };
      const response = await axios.put(
        `${API_BASE_URL}/api/result/${editingResult.customer_id}`,
        payload
      );
      const updated = response.data.result;
      setEditingResult(updated);
      if (selectedResult?.customer_id === updated.customer_id) {
        setSelectedResult(updated);
      }
      setEditModalOpen(false);
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      setEditError(error.response?.data?.detail || 'Failed to save edits');
    } finally {
      setEditLoading(false);
    }
  };

  const handleCloseEdit = () => {
    setEditModalOpen(false);
    setEditingResult(null);
    setEditError(null);
  };

  const renderSkeletonRows = () => (
    <tbody>
      {[...Array(4)].map((_, idx) => (
        <tr key={idx}>
          <td><div className="skeleton" style={{ width: '120px', height: '12px' }} /></td>
          <td><div className="skeleton" style={{ width: '180px', height: '12px' }} /></td>
          <td><div className="skeleton" style={{ width: '90px', height: '12px' }} /></td>
          <td><div className="skeleton" style={{ width: '150px', height: '12px' }} /></td>
          <td><div className="skeleton" style={{ width: '140px', height: '12px' }} /></td>
        </tr>
      ))}
    </tbody>
  );

  return (
    <div>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <p className="eyebrow" style={{ color: '#5b6678' }}>Results</p>
            <h2 style={{ marginBottom: 4 }}>Screening Dashboard</h2>
            <p style={{ color: '#5b6678', margin: 0 }}>Search, filter, and edit flagged customers with human intervention.</p>
          </div>
          <button className="button" onClick={onRefresh} disabled={loading}>
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="input"
            placeholder="Search by Customer ID or Name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ maxWidth: '300px' }}
          />
          <select
            className="input"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{ maxWidth: '200px' }}
          >
            <option value="all">All Status</option>
            <option value="verified">Verified</option>
            <option value="rejected">Rejected</option>
            <option value="pending_review">Pending Review</option>
          </select>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Customer ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Screening Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            {loading ? (
              renderSkeletonRows()
            ) : filteredResults.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan="5">
                    <div className="loading">No results found</div>
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {filteredResults.map((result, index) => (
                  <tr key={index}>
                    <td>{result.customer_id || 'N/A'}</td>
                    <td>{result.customer_data?.name || 'N/A'}</td>
                    <td>{getStatusBadge(result.status)}</td>
                    <td>
                      {result.screening_date
                        ? new Date(result.screening_date).toLocaleString()
                        : 'N/A'}
                    </td>
                    <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button
                        className="button"
                        onClick={() => handleViewDetails(result.customer_id)}
                        style={{ fontSize: '12px', padding: '6px 10px', marginRight: 0 }}
                      >
                        View
                      </button>
                      <button
                        className="button button-warning"
                        onClick={() => handleOpenEdit(result.customer_id)}
                        style={{ fontSize: '12px', padding: '6px 10px', marginRight: 0 }}
                        disabled={editLoading}
                      >
                        Edit
                      </button>
                      <button
                        className="button button-success"
                        onClick={() => handleDownloadReport(result.customer_id)}
                        style={{ fontSize: '12px', padding: '6px 10px', marginRight: 0 }}
                      >
                        Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        </div>

        <div style={{ marginTop: '20px', fontSize: '14px', color: '#666' }}>
          Showing {filteredResults.length} of {results.length} results
        </div>
      </div>

      {editModalOpen && editingResult && (
        <div className="modal-overlay">
          <div className="modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ marginBottom: '6px' }}>Compliance Analyst Review</h3>
                <p style={{ fontSize: '13px', color: '#555' }}>
                  Only flagged results can be edited. Provide your specialist details and decision.
                </p>
              </div>
              <button className="button" onClick={handleCloseEdit} disabled={editLoading}>
                Close
              </button>
            </div>

            {editError && (
              <div className="error" style={{ marginTop: '12px' }}>
                {editError}
              </div>
            )}

            <div style={{ marginTop: '15px' }}>
              <div style={{ marginBottom: '10px' }}>
                <strong>Customer:</strong> {editingResult.customer_data?.name || 'N/A'} ({editingResult.customer_id})
              </div>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 240px' }}>
                  <label style={{ fontSize: '13px', color: '#555' }}>Analyst Name</label>
                  <input
                    className="input"
                    type="text"
                    placeholder="Name / ID"
                    value={editForm.reviewer}
                    onChange={(e) => setEditForm({ ...editForm, reviewer: e.target.value })}
                  />
                </div>
                <div style={{ flex: '1 1 200px' }}>
                  <label style={{ fontSize: '13px', color: '#555' }}>Decision</label>
                  <select
                    className="input"
                    value={editForm.status}
                    onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                  >
                    <option value="verified">Approve (verified)</option>
                    <option value="pending_review">Keep pending review</option>
                    <option value="rejected">Reject</option>
                  </select>
                </div>
              </div>

              <div style={{ marginTop: '10px' }}>
                <label style={{ fontSize: '13px', color: '#555' }}>Notes for audit trail</label>
                <textarea
                  className="input"
                  rows="4"
                  placeholder="Why are you overriding/confirming this flagged case?"
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                />
              </div>
            </div>

            <div className="modal-actions">
              <button
                className="button button-success"
                onClick={handleSubmitEdit}
                disabled={editLoading || !editForm.reviewer.trim()}
              >
                {editLoading ? 'Saving...' : 'Save specialist decision'}
              </button>
              <button className="button" onClick={handleCloseEdit} disabled={editLoading}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedResult && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Result Details</h2>
            <button className="button" onClick={() => setSelectedResult(null)}>
              Close
            </button>
          </div>

          <div style={{ marginTop: '20px' }}>
            <h3>Customer Information</h3>
            <pre style={{ background: '#f8f9fa', padding: '15px', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(selectedResult.customer_data, null, 2)}
            </pre>

            <h3 style={{ marginTop: '20px' }}>Screening Results</h3>
            <div style={{ marginTop: '10px' }}>
              {Object.entries(selectedResult.results || {}).map(([key, value]) => (
                <div key={key} style={{ marginBottom: '15px', padding: '10px', background: '#f8f9fa', borderRadius: '4px' }}>
                  <strong>{key.replace('_', ' ').toUpperCase()}:</strong>
                  <pre style={{ marginTop: '5px', fontSize: '12px' }}>
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </div>
              ))}
            </div>

            {selectedResult.aml_flags && selectedResult.aml_flags.length > 0 && (
              <div style={{ marginTop: '20px' }}>
                <h3>AML Flags</h3>
                <ul>
                  {selectedResult.aml_flags.map((flag, index) => (
                    <li key={index} style={{ color: '#e74c3c' }}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}

            {selectedResult.sar_report_needed && (
              <div style={{ marginTop: '20px', padding: '15px', background: '#fff3cd', borderRadius: '4px' }}>
                <strong>⚠️ SAR Report Required</strong>
              </div>
            )}

            {selectedResult.manual_review && (
              <div style={{ marginTop: '20px', padding: '15px', background: '#eef4ff', borderRadius: '4px' }}>
                <h3>Manual Review</h3>
                <p style={{ marginTop: '8px', fontSize: '14px' }}>
                  <strong>Reviewer:</strong> {selectedResult.manual_review.reviewer || 'N/A'}
                </p>
                <p style={{ fontSize: '14px' }}>
                  <strong>Reviewed at:</strong> {selectedResult.manual_review.reviewed_at
                    ? new Date(selectedResult.manual_review.reviewed_at).toLocaleString()
                    : 'N/A'}
                </p>
                {selectedResult.manual_review.notes && (
                  <p style={{ fontSize: '14px', marginTop: '6px' }}>
                    <strong>Notes:</strong> {selectedResult.manual_review.notes}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsDashboard;


