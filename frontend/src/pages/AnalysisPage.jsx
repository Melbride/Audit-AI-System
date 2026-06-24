import { useLocation, useNavigate } from 'react-router-dom'
import '../styles/UploadPage.css'
import '../styles/CleanPage.css'

function AnalysisPage() {
    const location = useLocation()
    const navigate = useNavigate()
    const { cleanResult, clientId, uploadResult } = location.state || {}

    if (!cleanResult) {
        return (
            <div className="page">
                <p className="error">No cleaned file found. Finish cleaning before analysis.</p>
                <button className="btn" onClick={() => navigate('/upload')}>Go Back</button>
            </div>
        )
    }

    return (
        <div className="page">
            <div className="header">
                <h1 className="logo">Audit AI</h1>
                <p className="subtitle">AI Financial Intelligence System</p>
            </div>

            <div className="card">
                <h2 className="title">Analysis Ready</h2>
                <div className="all-clean">
                    Cleaning decisions are complete. This file is unlocked for analysis.
                </div>
                <div className="info-row">
                    <span className="info-label">File:</span>
                    <span>{uploadResult?.filename || cleanResult.file_id}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Client:</span>
                    <span>{clientId}</span>
                </div>
                <div className="info-row">
                    <span className="info-label">Rows:</span>
                    <span>{cleanResult.validation_report.total_rows}</span>
                </div>
            </div>

            <div className="card">
                <h2 className="title">Cleaned Data Preview</h2>
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
                            {cleanResult.cleaned_data.slice(0, 25).map((row, i) => (
                                <tr key={i}>
                                    <td>{i + 2}</td>
                                    {Object.values(row).map((val, j) => (
                                        <td key={j}>{val}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    )
}

export default AnalysisPage
