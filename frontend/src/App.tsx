import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ParentChat } from "./pages/ParentChat";
import { OperatorDashboard } from "./pages/OperatorDashboard";
import { Onboarding } from "./pages/Onboarding";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ParentChat />} />
        <Route path="/operator" element={<OperatorDashboard />} />
        <Route path="/onboarding" element={<Onboarding />} />
      </Routes>
    </BrowserRouter>
  );
}
