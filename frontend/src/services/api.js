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

export const acknowledgeIssue = (formData) =>
    API.post('/clean/acknowledge', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

export const submitInlineCorrections = (formData) =>
    API.post('/clean/inline-corrections', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

export const submitCorrectedFile = (formData) =>
    API.post('/clean/submit-corrected-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })

export const correctionExportUrl = (fileId, clientId, fileType = 'general') =>
    `${API.defaults.baseURL}/clean/export-corrections/${fileId}?client_id=${encodeURIComponent(clientId)}&file_type=${encodeURIComponent(fileType)}`

// Get upload history for a client
export const getUploads = (clientId) =>
    API.get(`/uploads/${clientId}`)

export default API
