import { useState } from  'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { cleanFile } from '../services/api'
import '../styles/UploadPage.css'
import '../styles/CleanPage.css'

function CleanPage() {
    const location = useLocation()
    const navigate = useNavigate()

    // Get data passed from MappingPage
    const { uploadResult, clientId, fileType } = location.state || {}

    const [cleaning, setCleaning] = useState(false)
    const [cleanResult, setCleanResult] = useState(null)
    const [error, setError] = useState(null)

    // Run cleaning engine
    const handleClean = async () => {
        setCleaning(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('file_id', uploadResult.file_id)
            formData.append('client_id', clientId)
            formData.append('file_type', fileType || 'other')

            const response = await cleanFile(formData)
            setCleanResult(response.data)
        
        } catch (err) {
            setError(err.response?.data?.detail || 'Cleaning failed. Please try again.')
        } finally {
            setCleaning(false)
        }
    }

    // Get severity color
    const severityColor = (severity) => {
        switch (severity) {
            case 'high': return 'issue-high'
            case 'medium': return 'issue-medium'
            case 'info': return 'issue-info'
            default: return 'issue-medium'
        }
    }

    // Check if a row is flagged
    const flaggedRows = cleanResult
        ? new Set(cleanResult.validation_report.issues
            .filter(i => i.row_index !== 'N/A')
            .map(i => i.row_index))
        : new Set()

    if (!uploadResult) {
        return (
            <div className="page">
                <p className="error">No file found. Please go back and upload a file first</p>
                <button className="btn" onClick={() => navigate('/')}>Go Back</button>
            </div>
        )
    }
    return (
        <div className="page">
            {/* Header */}
            <div className="header">
                <h1 className="logo">Audit AI</h1>
                <p className="subtitle">AI Financial Intelligence System</p>
            </div>
            {/* File info and run button */}
            <div className="card">
                <h2 className="title">Data Cleaning Engine</h2>
                <div className="info-row">
                    <span className="info-label">File:</span>
                    <span>{uploadResult.filename}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Client:</span>
                    <span>{clientId}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Rows:</span>
                    <span>{uploadResult.rows}</span>
                </div>

                {error && <div className="error"> {error} </div>}

                <button
                    className="btn"
                    onClick={handleClean}
                    disabled={cleaning || cleanResult}
                >
                    {cleaning ? 'Cleaning...' : cleanResult ? 'Cleaning Complete' : 'Run Cleaning Engine'}
                </button>
            </div>

            {/* Validation report */}
            {cleanResult && (
                <>
                    <div className="card">
                        <h2 className="title">Validation Report</h2>

                        {/* Summary Stats */}
                        <div className="stats-grid">
                            <div className="stat-card">
                                <p className="stat-value">{cleanResult.validation_report.total_rows}</p>
                                <p className="stat-label">Total Rows</p>
                            </div>
                            <div className="stat-card stat-clean">
                                <p className="stat-value">{cleanResult.validation_report.clean_rows}</p>
                                <p className="stat-label">Cleaned Rows</p>
                            </div>
                            <div className="stat-card stat-flagged">
                                <p className="stat-value">{cleanResult.validation_report.flagged_rows}</p>
                                <p className="stat-label">Flagged Rows</p>
                            </div>
                            <div className="stat-card stat-high">
                                <p className="stat-value">{cleanResult.validation_report.high_issues}</p>
                                <p className="stat-label">High Issues</p>
                            </div>
                            <div className="stat-card stat-medium">
                                <p className="stat-value">{cleanResult.validation_report.medium_issues}</p>
                                <p className="stat-label">Medium Issues</p>
                            </div>
                        </div>

                        {/* Issues List */}
                        {cleanResult.validation_report.issues.length > 0 && (
                            <>
                                <h3 className="issues-title">Issues Found</h3>
                                <div className="issues-list">
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
                                                    Row {issue.row} - {issue.column}
                                                </span>
                                            </div>
                                            <p className="issue-message">{issue.issue}</p>
                                            {issue.original_value && issue.original_value !== '' && (
                                                <p className="issue-value">
                                                    Original value: <strong>{issue.original_value}</strong>
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                        {cleanResult.validation_report.issues.length === 0 && (
                            <div className="all-clean">
                              No issues found, data is clean and ready for analysis!
                            </div>  
                        )}
                    </div>

                    {/* Cleaned data table */}
                    <div className="card">
                        <h2 className="title">Cleaned Data</h2>
                        <p className="mapping-note">
                            Rows highlighted in red have issues, review before proceeding.

                        </p>
                        <div className="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        {Object.keys(cleanResult.cleaned_data[0] || {}).map(col => (
                                            <th key={col}>{col}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {cleanResult.cleaned_data.map((row, i) => (
                                        <tr
                                            key={i}
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

                        {/* Proceed button */}
                        <button
                            className="btn"
                            onClick={() => navigate('/data', { 
                                state: { cleanResult, clientId, uploadResult } 
                            })}
                        >
                            Proceed to Data
                        </button>
                    </div>
                </>
            )}
        </div>
    )
        
}

export default CleanPage








