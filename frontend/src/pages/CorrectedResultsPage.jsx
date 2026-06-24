import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'
import '../styles/CorrectedResultsPage.css'

function CorrectedResultsPage() {
    const location = useLocation()
    const navigate = useNavigate()

    const { cleanResult, uploadResult, clientId, fileType } = location.state || {}

    const [currentResult, setCurrentResult] = useState(cleanResult)
    const [pendingEdits, setPendingEdits] = useState({})
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)

    if (!cleanResult || !uploadResult) {
        return (
            <div className="page">
                <p className="error">No results found. Please go back and run cleaning first.</p>
                <button className="btn" onClick={() => navigate('/')}>Go Back</button>
            </div>
        )
    }

    const report = currentResult.validation_report
    const allRows = currentResult.cleaned_data || []
    const columns = allRows.length > 0 ? Object.keys(allRows[0]) : []

    // Get flagged row indices — must be defined BEFORE flaggedRowsData
    const flaggedRowIndices = new Set(
        report.issues
            .filter(i => i.row_index !== 'N/A' && i.row_index !== null)
            .map(i => parseInt(i.row_index))
    )

    // Only show flagged rows — clean rows don't need editing
    const flaggedRowsData = allRows
        .map((row, rowIndex) => ({ row, rowIndex }))
        .filter(({ rowIndex }) => flaggedRowIndices.has(rowIndex))

    const editCount = Object.keys(pendingEdits).length

    // Handle inline cell edit
    const handleCellEdit = (rowIndex, col, originalValue, newValue) => {
        const key = `${rowIndex}__${col}`
        setPendingEdits(prev => ({
            ...prev,
            [key]: {
                row_index: rowIndex,
                column: col,
                original_value: originalValue,
                corrected_value: newValue
            }
        }))
    }

    // Save all corrections
    const handleSaveCorrections = async () => {
        const corrections = Object.values(pendingEdits)
        if (corrections.length === 0) {
            setError('No changes made yet. Edit cells in the table before saving.')
            return
        }

        setSaving(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('file_id', uploadResult.file_id)
            formData.append('client_id', String(clientId))
            formData.append('file_type', fileType || 'general')
            formData.append('corrections', JSON.stringify(corrections))
            formData.append('corrected_by', 'Auditor')

            const response = await axios.post(
                'http://localhost:8000/clean/submit-inline-corrections',
                formData
            )

            setCurrentResult(response.data)
            setPendingEdits({})
        } catch (err) {
            setError(err.response?.data?.detail || 'Could not save corrections. Please try again.')
        } finally {
            setSaving(false)
        }
    }

    const severityClass = (severity) => {
        switch (severity) {
            case 'high':   return 'issue-high'
            case 'medium': return 'issue-medium'
            case 'info':   return 'issue-info'
            default:       return 'issue-medium'
        }
    }

    return (
        <div className="page">

            {/* Header */}
            <div className="header">
                <h1 className="logo">AuditIQ</h1>
                <p className="subtitle">AI Financial Intelligence System</p>
            </div>

            {/* Back button */}
            <button className="btn btn-back" onClick={() => navigate(-1)}>
                ← Back to Cleaning
            </button>

            {/* Validation report */}
            <div className="card">
                <h2 className="title">Updated Validation Report</h2>

                <div className="stats-grid">
                    <div className="stat-card">
                        <p className="stat-value">{report.total_rows}</p>
                        <p className="stat-label">Total Rows</p>
                    </div>
                    <div className="stat-card stat-clean">
                        <p className="stat-value">{report.clean_rows}</p>
                        <p className="stat-label">Clean Rows</p>
                    </div>
                    <div className="stat-card stat-flagged">
                        <p className="stat-value">{report.flagged_rows}</p>
                        <p className="stat-label">Flagged Rows</p>
                    </div>
                    <div className="stat-card stat-high">
                        <p className="stat-value">{report.high_issues}</p>
                        <p className="stat-label">High Issues</p>
                    </div>
                    <div className="stat-card stat-medium">
                        <p className="stat-value">{report.medium_issues}</p>
                        <p className="stat-label">Medium Issues</p>
                    </div>
                </div>

                {/* Issues list */}
                {report.issues.length > 0 ? (
                    <>
                        <h3 className="issues-title">Remaining Issues</h3>
                        <div className="issues-list">
                            {report.issues.map((issue, i) => (
                                <div key={i} className={`issue-row ${severityClass(issue.severity)}`}>
                                    <div className="issue-meta">
                                        <span className="issue-badge">{issue.severity.toUpperCase()}</span>
                                        <span className="issue-location">Row {issue.row} — {issue.column}</span>
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
                ) : (
                    <div className="all-clean">
                        ✔ No issues remaining — data is clean and ready for analysis.
                    </div>
                )}
            </div>

            {/* Editable flagged rows table */}
            <div className="card">
                <h2 className="title">Correct Remaining Issues</h2>
                <p className="mapping-note">
                    Showing {flaggedRowsData.length} flagged row{flaggedRowsData.length !== 1 ? 's' : ''} out of {allRows.length} total.
                    Click any cell to edit it directly. Save when done.
                </p>

                {editCount > 0 && (
                    <div className="edit-counter">
                        ✏ {editCount} unsaved edit{editCount > 1 ? 's' : ''} — click Save Corrections to apply
                    </div>
                )}

                {error && <div className="error">⚠ {error}</div>}

                {flaggedRowsData.length === 0 ? (
                    <div className="all-clean">
                        ✔ No flagged rows to edit.
                    </div>
                ) : (
                    <div className="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    {columns.map(col => (
                                        <th key={col}>{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {flaggedRowsData.map(({ row, rowIndex }) => (
                                    <tr key={rowIndex} className="row-flagged">
                                        <td className="row-number">{rowIndex + 2}</td>
                                        {columns.map(col => {
                                            const editKey = `${rowIndex}__${col}`
                                            const isEdited = !!pendingEdits[editKey]
                                            const displayValue = isEdited
                                                ? pendingEdits[editKey].corrected_value
                                                : (row[col] ?? '')

                                            return (
                                                <td
                                                    key={col}
                                                    className={isEdited ? 'cell-edited' : ''}
                                                    contentEditable
                                                    suppressContentEditableWarning
                                                    onBlur={(e) => {
                                                        const newValue = e.target.innerText.trim()
                                                        if (newValue !== String(row[col] ?? '')) {
                                                            handleCellEdit(rowIndex, col, row[col] ?? '', newValue)
                                                        }
                                                    }}
                                                >
                                                    {displayValue}
                                                </td>
                                            )
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Save corrections button */}
                <button
                    className="btn"
                    onClick={handleSaveCorrections}
                    disabled={saving || editCount === 0}
                    style={{ marginTop: '16px' }}
                >
                    {saving ? 'Saving...' : `Save Corrections${editCount > 0 ? ` (${editCount})` : ''}`}
                </button>

                {/* Proceed button */}
                <div style={{ marginTop: '12px' }}>
                    {report.high_issues > 0 ? (
                        <div>
                            <div className="error" style={{ marginBottom: '12px' }}>
                                ⚠ Please fix all {report.high_issues} high severity issues before proceeding.
                            </div>
                            <button className="btn" disabled style={{ opacity: 0.5 }}>
                                Proceed to Analysis (Fix High Issues First)
                            </button>
                        </div>
                    ) : (
                        <div>
                            <div className="all-clean" style={{ marginBottom: '12px' }}>
                                ✔ No high severity issues — data is ready for analysis.
                            </div>
                            <button
                                className="btn"
                                style={{ background: 'var(--success)' }}
                                onClick={() => navigate('/analysis', {
                                    state: { cleanResult: currentResult, clientId, uploadResult }
                                })}
                            >
                                Proceed to Analysis →
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default CorrectedResultsPage