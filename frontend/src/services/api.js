// API Service calls for FastAPI backend

import axios from 'axios'

const API = axios.create({
    baseURL: 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json'
    }
})

// Upload a file for a client
export const uploadFile = (formData) => 
    API.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Save confirmed column mapping for a client
export const saveMapping = (formData) =>
    API.post('/save-mapping', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Detect columns for an uploaded file
export const detectColumns = (formData) =>
    API.post('/detect-columns', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })


// Get saved mapping for a client
export const getMapping = (clientId, fileType = 'general') =>
    API.get(`/get-mapping/${clientId}`, { params: { file_type: fileType } })

// Clean an uploaded file using confirmed mapping
export const cleanFile = (formData) =>
    API.post('/clean', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Acknowledge a flagged issue as correct as-is.
// Path corrected to match main.py's actual route: /clean/acknowledge-issue
export const acknowledgeIssue = (formData) =>
    API.post('/clean/acknowledge-issue', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Submit inline corrections made directly on the cleaning results screen.
// Path corrected to match main.py's actual route: /clean/submit-inline-corrections
export const submitInlineCorrections = (formData) =>
    API.post('/clean/submit-inline-corrections', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Upload a corrected Excel file (downloaded, edited, and re-uploaded by the auditor).
// Path corrected to match main.py's actual route: /clean/submit-corrected-excel
export const submitCorrectedExcel = (formData) =>
    API.post('/clean/submit-corrected-excel', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

// Get upload history for a client
export const getUploads = (clientId) =>
    API.get(`/uploads/${clientId}`)

export default API
