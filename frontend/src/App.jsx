import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import MappingPage from './pages/MappingPage'
import CleanPage from './pages/CleanPage'
import AnalysisPage from './pages/AnalysisPage'
import CorrectedResultsPage from './pages/CorrectedResultsPage'
import './App.css'


function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/mapping" element={<MappingPage />} />
        <Route path="/clean" element={<CleanPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/corrected-results" element={<CorrectedResultsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App






