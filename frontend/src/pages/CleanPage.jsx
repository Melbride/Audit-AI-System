import { useState, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { cleanFile, submitCorrectedExcel } from '../services/api'
import '../styles/UploadPage.css'
import '../styles/CleanPage.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function CleanPage() {
    const location = useLocation()
    const navigate = useNavigate()

    const { uploadResult, clientId, fileType } = location.state || {}

    const [currentUpload, setCurrentUpload] = useState(uploadResult)
    const [cleaning, setCleaning] = useState(false)
    const [cleanResult, setCleanResult] = useState(null)
    const [error, setError] = useState(null)
    const [downloaded, setDownloaded] = useState(false)
    const [uploadingCorrected, setUploadingCorrected] = useState(false)
    const correctedFileInputRef = useRef(null)

    // Run cleaning engine
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
        } catch (err) {
            setError(err.response?.data?.detail || 'Cleaning failed. Please try again.')
        } finally {
            setCleaning(false)
        }
    }

    // Download full workbook with highlighted issues
    const handleDownloadExcel = () => {
        if (!cleanResult) return
        const url = `${API_BASE}/clean/export-cleaned/${cleanResult.file_id}?client_id=${encodeURIComponent(clientId)}&file_type=${encodeURIComponent(fileType || 'other')}`
        window.open(url, '_blank')
        setDownloaded(true)

    }

    // Upload corrected file and navigate to corrected results page
    const handleUploadCorrectedFile = async (e) => {
        const selectedFile = e.target.files[0]
        if (!selectedFile || !cleanResult) return

        setUploadingCorrected(true)
        setError(null)
        try {
            const formData = new FormData()
            formData.append('file', selectedFile)
            formData.append('file_id', cleanResult.file_id)
            formData.append('client_id', clientId)
            formData.append('file_type', fileType || 'other')
            formData.append('corrected_by', 'Auditor')

            const response = await submitCorrectedExcel(formData)
            navigate('/corrected-results', {
                state: {
                    cleanResult: response.data,
                    uploadResult: currentUpload,
                    clientId,
                    fileType: fileType || 'other'
                }
            })
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                'Could not process the corrected file. Please make sure you uploaded the file exactly as it was downloaded.'
            )
        } finally {
            setUploadingCorrected(false)
            if (correctedFileInputRef.current) {
                correctedFileInputRef.current.value = ''
            }
        }
    }

    const report = cleanResult?.validation_report
    const allRows = cleanResult?.cleaned_data || []
    const previewRows = allRows.slice(0, 5)
    const totalRows = allRows.length

    // Flagged row indices for highlighting
    const flaggedRows = cleanResult
        ? new Set(
            (report?.issues || [])
                .filter(i => i.row_index !== 'N/A')
                .map(i => Number(i.row_index))
          )
        : new Set()

    if (!uploadResult) {
        return (
            <div className="page">
                <p className="error">No file found. Please go back and upload a file first.</p>
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

            {/* File info + run button */}
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

                {error && <div className="error">⚠ {error}</div>}

                {!cleanResult ? (
                    <button className="btn" onClick={handleClean} disabled={cleaning}>
                        {cleaning ? 'Cleaning...' : 'Run Cleaning Engine'}
                    </button>
                ) : (
                    <div className="clean-complete">✔ Cleaning Complete</div>
                )}
            </div>

            {cleanResult && (
                <>
                    {/* Validation report — stats only */}
                    <div className="card">
                        <h2 className="title">Validation Report</h2>

                        <div className="stats-grid">
                            <div className="stat-card">
                                <p className="stat-value">{report?.total_rows}</p>
                                <p className="stat-label">Total Rows</p>
                            </div>
                            <div className="stat-card stat-clean">
                                <p className="stat-value">{report?.clean_rows}</p>
                                <p className="stat-label">Clean Rows</p>
                            </div>
                            <div className="stat-card stat-flagged">
                                <p className="stat-value">{report?.flagged_rows}</p>
                                <p className="stat-label">Flagged Rows</p>
                            </div>
                            <div className="stat-card stat-high">
                                <p className="stat-value">{report?.high_issues}</p>
                                <p className="stat-label">High Issues</p>
                            </div>
                            <div className="stat-card stat-medium">
                                <p className="stat-value">{report?.medium_issues}</p>
                                <p className="stat-label">Medium Issues</p>
                            </div>
                        </div>

                        {/* Simple issues summary */}
                        {report?.total_issues > 0 ? (
                            <div className="issues-summary">
                                <p>
                                    <strong>{report.total_issues} issue{report.total_issues > 1 ? 's' : ''} found</strong> — download the workbook below to see all issues highlighted and fix them in Excel, then upload the corrected file back.
                                </p>
                            </div>
                        ) : (
                            <div className="all-clean">
                                ✔ No issues found — data is clean and ready for analysis.
                            </div>
                        )}
                    </div>

                    {/* Cleaned data preview */}
                    <div className="card">
                        <h2 className="title">Cleaned Data Preview</h2>
                        <p className="mapping-note">
                            Showing first 5 of {totalRows} rows. Rows highlighted in red have issues.
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

                        {/* Action buttons */}
                        <div className="action-buttons">
                            <button
                                className="btn btn-secondary"
                                onClick={handleDownloadExcel}
                            >
                                Download Full Workbook
                            </button>

                            {downloaded && (
                                <>
                                    <p className="mapping-note" style={{ color: 'var(--secondary)', fontWeight: '600' }}>
                                        ✔ Workbook downloaded — fix the highlighted issues in Excel then upload it back below.
                                    </p>
                                    <button
                                        className="btn btn-inline"
                                        onClick={() => correctedFileInputRef.current?.click()}
                                        disabled={uploadingCorrected}
                                    >
                                        {uploadingCorrected ? 'Processing...' : 'Upload Corrected File'}
                                    </button>
                                    <input
                                        type="file"
                                        accept=".xlsx"
                                        ref={correctedFileInputRef}
                                        style={{ display: 'none' }}
                                        onChange={handleUploadCorrectedFile}
                                    />
                                </>
                            )}

                            <button
                                className="btn btn-proceed"
                                disabled={!cleanResult.can_proceed}
                                onClick={() =>
                                    navigate('/analysis', {
                                        state: { cleanResult, clientId, uploadResult: currentUpload },
                                    })
                                }
                            >
                                Proceed to Analysis →
                            </button>
                        </div>

                        {!cleanResult.can_proceed && (
                            <p className="mapping-note" style={{ marginTop: '8px', color: 'var(--danger)' }}>
                                ⚠ Fix all issues before proceeding to analysis.
                            </p>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}

export default CleanPage