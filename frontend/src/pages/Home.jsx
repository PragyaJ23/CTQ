import { Link } from "react-router-dom";
import Logo from "../components/Logo.jsx";

const WORKFLOW = ["Patient Data", "Trial Retrieval", "Similarity Matching", "Eligibility Analysis", "Explanation"];

export default function Home() {
  return (
    <div>
      <section className="hero">
        <div className="hero-title-row">
          <Logo variant="light" />
          <h1>Clinical Trial <span className="hero-accent">Qualifier</span></h1>
        </div>
        <p className="subtitle">
          AI-powered clinical trial matching and eligibility analysis for Indian patients — enter a
          patient profile and get clear, explained verdicts against real CTRI trials.
        </p>

        <div className="btn-row hero-actions">
          <Link to="/matcher" className="btn large hero-primary">
            Find Clinical Trials
          </Link>
          <Link to="/evaluation" className="btn large hero-ghost">
            Evaluate Model
          </Link>
        </div>

        <div className="flow">
          {WORKFLOW.map((step, i) => (
            <span key={step} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              {i > 0 && <span className="flow-arrow">→</span>}
              <span className="flow-step">{step}</span>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
