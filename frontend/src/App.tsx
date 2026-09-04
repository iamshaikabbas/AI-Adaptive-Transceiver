import { useState } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import Overview from "./pages/Overview";
import DigitalTwinPage from "./pages/DigitalTwinPage";
import CustomEvaluation from "./pages/CustomEvaluation";
import EvalPlatform from "./pages/EvalPlatform";
import Analysis from "./pages/Analysis";
import About from "./pages/About";
import { useSimulation } from "./hooks/useSimulation";

export default function App() {
  const [page, setPage] = useState("overview");
  const sim = useSimulation();

  const renderPage = () => {
    switch (page) {
      case "overview":
        return <Overview />;
      case "digital-twin":
        return <DigitalTwinPage />;
      case "custom-eval":
        return <CustomEvaluation />;
      case "evals-platform":
        return <EvalPlatform />;
      case "analysis":
        return <Analysis />;
      case "about":
        return <About />;
      default:
        return <Overview />;
    }
  };

  return (
    <div className="min-h-screen bg-surface text-text-primary flex flex-col">
      <Header connection={sim.connectionStatus} simStatus={sim.simStatus} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar active={page} onNavigate={setPage} />
        <main className="flex-1 overflow-y-auto bg-surface-alt">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
