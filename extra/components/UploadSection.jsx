import React, { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const UploadSection = ({ onProcessingStart, onProcessingEnd }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState('');
  const [previewType, setPreviewType] = useState('');

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setMessage(null);
      buildPreview(selectedFile);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setMessage(null);
      buildPreview(droppedFile);
    }
  };

  const buildPreview = (selectedFile) => {
    if (!selectedFile) return;
    setPreview('');
    setPreviewType('');

    const isPdf = selectedFile.name.toLowerCase().endsWith('.pdf');
    if (isPdf) {
      setPreview('PDF selected. Preview not available, ready to upload.');
      setPreviewType('note');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result || '';
      const snippet = text.slice(0, 1200);
      setPreview(snippet);
      setPreviewType(selectedFile.name.toLowerCase().endsWith('.csv') ? 'csv' : 'json');
    };
    reader.readAsText(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setMessage({ type: 'error', text: 'Please select a file' });
      return;
    }

    if (onProcessingStart) onProcessingStart();

    setUploading(true);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(
        `${API_BASE_URL}/api/upload`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      setMessage({
        type: 'success',
        text: `File uploaded successfully! Customer ID: ${response.data.customer_id || 'N/A'}`,
      });

      setFile(null);
      setPreview('');
      setPreviewType('');
      
      // Reset file input
      const fileInput = document.querySelector('input[type="file"]');
      if (fileInput) fileInput.value = '';

      if (onProcessingEnd) onProcessingEnd(true);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Upload failed. Please try again.',
      });
      if (onProcessingEnd) onProcessingEnd(false);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card">
      <h2>Upload Customer Screening File</h2>
      <p style={{ marginBottom: '20px', color: '#666' }}>
        Upload a JSON, CSV, or PDF file containing customer data for screening
      </p>

      {message && (
        <div className={message.type === 'error' ? 'error' : 'success'}>
          {message.text}
        </div>
      )}

      <div
        className={`file-upload ${isDragging ? 'dragover' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".json,.csv,.pdf"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="file-input"
        />
        <label htmlFor="file-input" style={{ cursor: 'pointer' }}>
          {file ? (
            <div>
              <p>Selected: {file.name}</p>
              <p style={{ fontSize: '12px', color: '#666' }}>
                {(file.size / 1024).toFixed(2)} KB
              </p>
            </div>
          ) : (
            <div>
              <p>📁 Drag and drop a file here, or click to select</p>
              <p style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
                Supported formats: JSON, CSV, PDF
              </p>
            </div>
          )}
        </label>
      </div>

      {file && (
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="preview-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <p className="eyebrow" style={{ margin: 0 }}>File preview</p>
              <div className="pill">{previewType === 'csv' ? 'CSV' : previewType === 'note' ? 'PDF' : 'JSON'}</div>
            </div>
            <pre className="code-block">
              {preview || 'Loading preview...'}
            </pre>
          </div>
          <div>
            <button
              className="button button-success"
              onClick={handleUpload}
              disabled={uploading}
            >
              {uploading ? 'Uploading...' : 'Upload & Process'}
            </button>
            <button
              className="button"
              onClick={() => {
                setFile(null);
                setPreview('');
                setPreviewType('');
                setMessage(null);
                const fileInput = document.querySelector('input[type="file"]');
                if (fileInput) fileInput.value = '';
              }}
              disabled={uploading}
            >
              Clear
            </button>
          </div>
        </div>
      )}

    </div>
  );
};

export default UploadSection;


