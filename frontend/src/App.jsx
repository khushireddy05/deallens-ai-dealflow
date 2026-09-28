import { NavLink, Route, Routes } from "react-router-dom";
import OpportunitiesPage from "./pages/OpportunitiesPage.jsx";
import OpportunityDetailPage from "./pages/OpportunityDetailPage.jsx";
import SubmitPage from "./pages/SubmitPage.jsx";
import CompaniesPage from "./pages/CompaniesPage.jsx";
import FailuresPage from "./pages/FailuresPage.jsx";

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>DealLens</h1>
        <nav>
          <NavLink to="/" end>Opportunities</NavLink>
          <NavLink to="/submit">Submit pitch</NavLink>
          <NavLink to="/companies">Companies</NavLink>
          <NavLink to="/failures">Failures</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<OpportunitiesPage />} />
          <Route path="/opportunities/:id" element={<OpportunityDetailPage />} />
          <Route path="/submit" element={<SubmitPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/failures" element={<FailuresPage />} />
          <Route path="*" element={<p className="state">Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
