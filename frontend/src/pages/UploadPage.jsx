import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFile } from '../services/api'
import '../styles/UploadPage.css'
import axios from 'axios'

// Page for uploading financial documents, selecting client, and previewing file contents
function UploadPage() {
    const navigate = useNavigate()

    const [file, setFile] = useState(null)
    const [dragging, setDragging] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [uploadResult, setUploadResult] = useState(null)
    const [error, setError] = useState('')
    const [clients, setClients] = useState([])
    const [clientSearch, setClientSearch] = useState('')
    const [selectedClient, setSelectedClient] = useState(null)
    const [showDropdown, setShowDropdown] = useState(false)
    // Load clients on component mount
    useEffect(() => {
        axios.get('http://localhost:8000/clients')
            .then((res) => setClients(res.data))
            .catch((err) => console.error('Could not load clients', err))
    }, [])

    // Drag and drop handlers
    const handleDragOver = (e) => {
        e.preventDefault()
        setDragging(true)
    }
    // When dragging leaves the dropzone, reset dragging state
    const handleDragLeave = () => {
        setDragging(false)
    }
    // When a file is dropped, prevent default behavior and set the file state
    const handleDrop = (e) => {
        e.preventDefault()
        setDragging(false)
        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile) setFile(droppedFile)
    }
    // When a file is selected through the file input, set the file state
    const handleFileChange = (e) => {
        setFile(e.target.files[0])
    }
    // Handle the upload button click
    const handleUpload = async () => {
        if (!selectedClient) {
            setError('Please select a client.')
            return
        }

        if (!file) {
            setError('Please select a file to upload.')
            return
        }

        setError(null)
        setUploading(true)
        // Create FormData and append file and client_id, then call the uploadFile API function
        try {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('client_id', selectedClient.client_id)

            const response = await uploadFile(formData)
            setUploadResult(response.data)
        } catch (err) {
            setError(err.response?.data?.detail || 'Upload failed. Please try again.')
        } finally {
            setUploading(false)
        }
    }
    // When "Detect Columns" button is clicked, navigate to the mapping page with upload result and client ID in state
    const handleDetectColumns = () => {
        navigate('/mapping', {
            state: {
                uploadResult,
                clientId: selectedClient?.client_id
            }
        })
    }
    // Render the upload page with client selection, drag-and-drop file upload, and file preview
    return (
        <div className="page">
            <div className="header">
                <h1 className="logo">Audit AI</h1>
                <p className="subtitle">AI Financial Intelligence System</p>
            </div>

            <div className="card">
                <h2 className="title">Upload Financial Documents</h2>

                {/* Client searchable dropdown list */}
                <div className="field client-field">
                    <label className="label">Client</label>
                    <input
                        className="input"
                        type="text"
                        placeholder="Search for a client..."
                        value={clientSearch}
                        onChange={(e) => {
                            setClientSearch(e.target.value)
                            setSelectedClient(null)
                            setShowDropdown(true)
                        }}
                        onFocus={() => setShowDropdown(true)}
                        onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                    />

                    {/* Dropdown list of existing clients */}
                    {showDropdown && (
                        <div className="client-dropdown">
                            {/* Filtered existing clients based on search input, clicking an option sets the selected client and updates the search input */}
                            {clients
                                .filter(c => c.company_name.toLowerCase()
                                    .includes(clientSearch.toLowerCase()))
                                .map(c => (
                                    <div
                                        key={c.client_id}
                                        className="client-option"
                                        onMouseDown={() => {
                                            setSelectedClient(c)
                                            setClientSearch(c.company_name)
                                            setShowDropdown(false)
                                        }}
                                    >
                                        {c.company_name}
                                    </div>
                                ))
                            }

                            {/* No results message if search input doesn't match any clients, and prompt to create client if search input is not empty  */}
                            {clients.filter(c => c.company_name.toLowerCase()
                                .includes(clientSearch.toLowerCase())).length === 0 &&
                                clientSearch.trim() && (
                                    <div className="client-dropdown-message">
                                        No clients found. Ask an admin to create this client first.
                                    </div>
                                )}
                            {/* If search input is empty, show message based on whether there are any clients in the system */}
                            {!clientSearch.trim() && clients.length === 0 && (
                                <div className="client-dropdown-message">
                                    No clients available.
                                </div>
                            )}
                            {/* If search input is empty but there are clients in the system, prompt user to start typing to search */}
                            {!clientSearch.trim() && clients.length > 0 && (
                                <div className="client-dropdown-message">
                                    Start typing to search existing clients.
                                </div>
                            )}
                        </div>
                    )}

                    {/* Selected client confirmation */}
                    {selectedClient && (
                        <p className="selected-client">
                            Selected: {selectedClient.company_name} (ID: {selectedClient.client_id})
                        </p>
                    )}
                </div>
                {/* Drag-and-drop file upload area with click-to-browse functionality */}
                <div
                    className={`dropzone ${dragging ? 'dragging' : 'idle'}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('file-input').click()}
                >
                    {/* Hidden file input for click-to-browse, accepts specified file types and calls handleFileChange on file selection */}
                    <input
                        id="file-input"
                        className="file-input"
                        type="file"
                        accept=".xlsx,.xls,.csv,.pdf,.docx"
                        onChange={handleFileChange}
                    />
                    {/* Show file name if a file is selected, otherwise show drag-and-drop instructions */}
                    {file ? (
                        <p className="file-name">File selected: {file.name}</p>
                    ) : (
                        <>
                            <p className="drop-text">Drag & drop a file here</p>
                            <p className="drop-subtext">or click to browse</p>
                        </>
                    )}
                </div>

                <p className="formats">
                    Supported formats: Excel (.xlsx, .xls), CSV, PDF, DOCX - Max 50MB
                </p>

                {error && <div className="error">Warning: {error}</div>}
                <button className="btn" onClick={handleUpload} disabled={uploading}>
                    {uploading ? 'Uploading...' : 'Upload File'}
                </button>
            </div>
            {/* If upload result is available, show file preview and "Detect Columns" button */}
            {uploadResult && (
                <div className="preview-card">
                    <h2 className="title">File Preview</h2>

                    <div className="preview-summary">
                        <div className="summary-item">
                            <span className="summary-label">Filename:</span>
                            <span className="summary-value">{uploadResult.filename}</span>
                        </div>

                    <div className="summary-item">
                        <span className="summary-label">Rows:</span>
                        <span className="summary-value">{uploadResult.rows}</span>
                    </div>

                    <div className="summary-item">
                        <span className="summary-label">Columns:</span>
                        <span className="summary-value">{uploadResult.columns?.length || 0}</span>
                    </div>
                </div>
                    {/* Table preview of the uploaded file, showing column headers and first few rows of data */}
                    <div className="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    {uploadResult.columns?.map((col) => (
                                        <th key={col}>{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {uploadResult.preview?.map((row, index) => (
                                    <tr key={index}>
                                        {uploadResult.columns?.map((col) => (
                                            <td key={col}>{row[col]}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <button className="btn" onClick={handleDetectColumns}>
                        Detect Columns
                    </button>
                </div>
            )}
        </div>
    )
}
export default UploadPage
