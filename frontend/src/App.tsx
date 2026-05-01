import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { Dashboard } from "./pages/Dashboard";
import { NewScan } from "./pages/NewScan";
import { ScanProgress } from "./pages/ScanProgress";
import { Report } from "./pages/Report";
import { Templates } from "./pages/Templates";
import { Playground } from "./pages/Playground";
import { Compare } from "./pages/Compare";
import { Settings } from "./pages/Settings";
import { ScanResults } from "./pages/ScanResults";
import { About } from "./pages/About";
import { Adapters } from "./pages/Adapters";
import { JudgeCalibration } from "./pages/JudgeCalibration";
import { AutoTest } from "./pages/AutoTest";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/scan/new" element={<NewScan />} />
        <Route path="/scan/:taskId" element={<ScanProgress />} />
        <Route path="/report/:scanId" element={<Report />} />
        <Route path="/results/:scanId" element={<ScanResults />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/adapters" element={<Adapters />} />
        <Route path="/autotest" element={<AutoTest />} />
        <Route path="/judge-calibration" element={<JudgeCalibration />} />
        <Route path="/playground" element={<Playground />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </Layout>
  );
}
