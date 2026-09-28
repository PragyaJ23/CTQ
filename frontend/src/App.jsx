import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Home from "./pages/Home.jsx";
import Matcher from "./pages/Matcher.jsx";
import Results from "./pages/Results.jsx";
import Evaluation from "./pages/Evaluation.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/matcher" element={<Matcher />} />
        <Route path="/results" element={<Results />} />
        <Route path="/evaluation" element={<Evaluation />} />
      </Routes>
    </Layout>
  );
}
