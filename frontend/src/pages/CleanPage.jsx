import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
    acknowledgeIssue,
    cleanFile,
    submitInlineCorrections,
} from '../services/api'
import '../styles/UploadPage.css'
import '../styles/CleanPage.css'

// Used to hit the real Excel endpoint
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// function to CleanPage component
function CleanPage() {
    const location = useLocation()
    const navigate = useNavigate()

    const { uploadResult, clientId, fileType } = location.state || {}

    const INLINE_LIMIT = 10

    const [currentUpload, setCurrentUpload] = useState(uploadResult)
    const [cleaning, setCleaning] = useState(false)
    const [cleanResult, setCleanResult] = useState(null)
    const [error, setError] = useState(null)
    const [pendingEdits, setPendingEdits] = useState({})
    const [submitting, setSubmitting] = useState(false)

    const issueCount = cleanResult?.validation_report?.issues?.length || 0
    const useInlineCorrections = issueCount > 0 && issueCount <= INLINE_LIMIT

    // Function to handle the cleaning process
    const handleClean = async () => {
        setCleaning(true)
        setError(null)
        try {
            const formData = new FormData()
            formData.append('file_id', currentUpload.file_id)
            formData.append('client_id', clientId)
            formData.append('file_type', fileType || 'other')
            const response = await cleanFile(formData)
            setCleanResult(response.data)
            setPendingEdits({})
        } catch (err) {
            setError(err.response?.data?.detail || 'Cleaning failed. Please try again.')
        } finally {
            setCleaning(false)
        }
    }

    // Helper to determine CSS class based on issue severity
    const severityColor = (severity) => {
        switch (severity) {
            case 'high':   return 'issue-high'
            case 'medium': return 'issue-medium'
            case 'info':   return 'issue-info'
            default:       return 'issue-medium'
        }
    }

    // Refresh clean result and current upload info after acknowledging or correcting an issue
    const refreshFromResponse = (data) => {
        setCleanResult(data)
        setPendingEdits({})
        if (data.file_id && data.file_id !== currentUpload.file_id) {
            setCurrentUpload(prev => ({
                ...prev,
                file_id: data.file_id,
                rows: data.validation_report?.total_rows,
            }))
        }
    }

    // Acknowledge an issue as correct without changing the data
    const handleAcknowledge = async (issue) => {
        setSubmitting(true)
        setError(null)
        try {
            const formData = new FormData()
            formData.append('file_id', cleanResult.file_id)
            formData.append('client_id', clientId)
            formData.append('file_type', fileType || 'other')
            formData.append('issue', JSON.stringify(issue))
            formData.append('acknowledged_by', 'Auditor')
            const response = await acknowledgeIssue(formData)
            refreshFromResponse(response.data)
        } catch (err) {
            setError(err.response?.data?.detail || 'Could not acknowledge issue.')
        } finally {
            setSubmitting(false)
        }
    }

    // Download, hits the real Excel endpoint which returns a presigned URL for the cleaned file in S3
    const handleDownloadExcel = () => {
        if (!cleanResult) return
        const url = `${API_BASE}/clean/export-cleaned/${cleanResult.file_id}?client_id=${encodeURIComponent(clientId)}&file_type=${encodeURIComponent(fileType || 'other')}`
        window.open(url, '_blank')
    }

    // Determine if an issue is eligible for inline correction, must have specific row/column and not be a "missing value" issue without an original value
    const editableIssue = (issue) =>
        issue.row_index !== 'N/A' && issue.column !== 'all columns'
    const editKey = (issue) => issue.issue_id

    // Handle inline corrections input changes, store in pendingEdits state keyed by issue_id
    const handleEditChange = (issue, value) => {
        setPendingEdits(prev => ({
            ...prev,
            [editKey(issue)]: {
                row_index: issue.row_index,
                column: issue.column,
                original_value: issue.original_value || '',
                corrected_value: value,
            },
        }))
    }

    // Submit all inline corrections to backend, then re-run cleaning with corrections applied
    const handleSubmitInlineCorrections = async () => {
        const corrections = Object.values(pendingEdits).filter(
            item => item.corrected_value !== undefined
        )
        if (corrections.length === 0) {
            setError('Enter at least one corrected value before submitting.')
            return
        }
        setSubmitting(true)
        setError(null)
        try {
            const formData = new FormData()
            formData.append('file_id', cleanResult.file_id)
            formData.append('client_id', clientId)
            formData.append('file_type', fileType || 'other')
            formData.append('corrections', JSON.stringify(corrections))
            formData.append('corrected_by', 'Auditor')
            const response = await submitInlineCorrections(formData)
            refreshFromResponse(response.data)
        } catch (err) {
            setError(err.response?.data?.detail || 'Could not save corrections.')
        } finally {
            setSubmitting(false)
        }
    }

    // Coerce row_index to number so Set lookup works
    const flaggedRows = cleanResult
        ? new Set(
            (cleanResult.validation_report?.issues || [])
                .filter(i => i.row_index !== 'N/A')
                .map(i => Number(i.row_index))   // 
          )
        : new Set()
    
    // For data preview, show first 5 rows only with a note about total rows and flagged row highlighting
    const allRows   = cleanResult?.cleaned_data || []
    const previewRows = allRows.slice(0, 5)          
    const totalRows   = allRows.length
    
    // If no upload result in state, user likely navigated here directly, show error and prompt to go back
    if (!uploadResult) {
        return (
            <div className="page">
                <p className="error">No file found. Please go back and upload a file first.</p>
                <button className="btn" onClick={() => navigate('/')}>Go Back</button>
            </div>
        )
    }
     
    {/* Main render of the CleanPage component, shows file info, cleaning button, validation report with issues and inline correction options, and cleaned data preview with download option */}
    return (
        <div className="page">

            {/* Header */}
            <div className="header">
                <h1 className="logo">Audit AI</h1>
                <p className="subtitle">AI Financial Intelligence System</p>
            </div>

            {/* File info */}
            <div className="card">
                <h2 className="title">Data Cleaning Engine</h2>
                <div className="info-row">
                    <span className="info-label">File:</span>
                    <span>{currentUpload?.filename}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Client:</span>
                    <span>{clientId}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Rows:</span>
                    <span>{currentUpload?.rows}</span>
                </div>

                {error && <div className="error">{error}</div>}

                <button
                    className="btn"
                    onClick={handleClean}
                    disabled={cleaning || !!cleanResult}
                >
                    {cleaning ? 'Cleaning...' : cleanResult ? 'Cleaning Complete' : 'Run Cleaning Engine'}
                </button>
            </div>

            {cleanResult && (
                <>
                    {/* Validation report */}
                    <div className="card">
                        <h2 className="title">Validation Report</h2>

                        <div className="stats-grid">
                            <div className="stat-card">
                                <p className="stat-value">{cleanResult.validation_report?.total_rows}</p>
                                <p className="stat-label">Total Rows</p>
                            </div>
                            <div className="stat-card stat-clean">
                                <p className="stat-value">{cleanResult.validation_report?.clean_rows}</p>
                                <p className="stat-label">Clean Rows</p>
                            </div>
                            <div className="stat-card stat-flagged">
                                <p className="stat-value">{cleanResult.validation_report?.flagged_rows}</p>
                                <p className="stat-label">Flagged Rows</p>
                            </div>
                            <div className="stat-card stat-high">
                                <p className="stat-value">{cleanResult.validation_report?.high_issues}</p>
                                <p className="stat-label">High Issues</p>
                            </div>
                            <div className="stat-card stat-medium">
                                <p className="stat-value">{cleanResult.validation_report?.medium_issues}</p>
                                <p className="stat-label">Medium Issues</p>
                            </div>
                        </div>

                        {issueCount > 0 && (
                            <div className="issues-list">
                                <h3 className="issues-title">Issues Found</h3>
                                {cleanResult.validation_report.issues.map((issue, i) => (
                                    <div
                                        key={i}
                                        className={`issue-row ${severityColor(issue.severity)}`}
                                    >
                                        <div className="issue-meta">
                                            <span className="issue-badge">
                                                {issue.severity.toUpperCase()}
                                            </span>
                                            <span className="issue-location">
                                                Row {issue.row} — {issue.column}
                                            </span>
                                        </div>
                                        <p className="issue-message">{issue.issue}</p>
                                        {issue.original_value && issue.original_value !== '' && (
                                            <p className="issue-value">
                                                Original value: <strong>{issue.original_value}</strong>
                                            </p>
                                        )}
                                        <div className="issue-actions">
                                            <button
                                                className="small-btn"
                                                onClick={() => handleAcknowledge(issue)}
                                                disabled={submitting}
                                            >
                                                Acknowledge as Correct
                                            </button>
                                            {useInlineCorrections && editableIssue(issue) && (
                                                <input
                                                    className="correction-input"
                                                    type="text"
                                                    placeholder="Corrected value"
                                                    value={pendingEdits[editKey(issue)]?.corrected_value || ''}
                                                    onChange={e => handleEditChange(issue, e.target.value)}
                                                />
                                            )}
                                        </div>
                                    </div>
                                ))}

                                {useInlineCorrections && (
                                    <button
                                        className="btn"
                                        onClick={handleSubmitInlineCorrections}
                                        disabled={submitting || Object.keys(pendingEdits).length === 0}
                                    >
                                        {submitting ? 'Re-cleaning...' : 'Save Corrections & Re-clean'}
                                    </button>
                                )}
                            </div>
                        )}

                        {issueCount === 0 && (
                            <div className="all-clean">
                                All issues resolved. Data is ready for analysis.
                            </div>
                        )}
                    </div>

                    {/* Cleaned data preview, first 5 rows only */}
                    <div className="card">
                        <h2 className="title">Cleaned Data</h2>
                        <p className="mapping-note">
                            Showing first 5 of {totalRows} rows.
                            Rows highlighted in red have issues — download the full workbook to review.
                        </p>

                        <div className="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        {Object.keys(allRows[0] || {}).map(col => (
                                            <th key={col}>{col}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {previewRows.map((row, i) => (
                                        <tr
                                            key={i}
                                            // i is 0-based index matching row_index from API
                                            className={flaggedRows.has(i) ? 'row-flagged' : ''}
                                        >
                                            <td>{i + 2}</td>
                                            {Object.values(row).map((val, j) => (
                                                <td key={j}>{val}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Download full Excel workbook */}
                        <button
                            className="btn btn-secondary"
                            onClick={handleDownloadExcel}
                        >
                            Download Full Workbook (.xlsx)
                        </button>

                        {/* Proceed to analysis */}
                        <button
                            className="btn"
                            disabled={!cleanResult.can_proceed}
                            onClick={() =>
                                navigate('/analysis', {
                                    state: { cleanResult, clientId, uploadResult: currentUpload },
                                })
                            }
                        >
                            Proceed to Analysis
                        </button>
                    </div>
                </>
            )}
        </div>
    )
}
export default CleanPage


