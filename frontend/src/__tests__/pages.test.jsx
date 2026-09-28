import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    listOpportunities: vi.fn(),
    getOpportunity: vi.fn(),
    submitPitch: vi.fn(),
    setStatus: vi.fn(),
    retry: vi.fn(),
    listFailures: vi.fn(),
    listCompanies: vi.fn(),
    samples: vi.fn(),
  },
}));

import { api } from "../api.js";
import FailuresPage from "../pages/FailuresPage.jsx";
import OpportunitiesPage from "../pages/OpportunitiesPage.jsx";
import OpportunityDetailPage from "../pages/OpportunityDetailPage.jsx";
import SubmitPage from "../pages/SubmitPage.jsx";

const row = (overrides = {}) => ({
  id: 1,
  company_name: "ABC AI",
  company_domain: "abc-ai.example",
  location: "Berlin",
  funding_stage: "seed",
  verdict: "pass",
  status: "new",
  processing_state: "completed",
  failed_step: null,
  error: null,
  source: "email",
  sender: "john@abc-ai.example",
  subject: "Hello",
  received_at: "2026-09-20T10:00:00Z",
  ...overrides,
});

const detail = (overrides = {}) => ({
  ...row(),
  raw_body: "We are ABC AI",
  extracted: { company_name: "ABC AI", country: "Germany", founders: ["John"] },
  enrichment: null,
  screening_reasons: ["AI-related (mentions 'ai')"],
  criteria_matched: ["ai"],
  company: { id: 1, needs_review: false },
  logs: [{ id: 1, step: "received", status: "ok", message: null, created_at: "2026-09-20T10:00:00Z" }],
  ...overrides,
});

const inRouter = (ui, path = "/") => render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);

beforeEach(() => vi.resetAllMocks());

describe("OpportunitiesPage", () => {
  it("shows rows with verdict and status", async () => {
    api.listOpportunities.mockResolvedValue([row(), row({ id: 2, company_name: "Bakehaus", verdict: "fail" })]);
    inRouter(<OpportunitiesPage />);
    expect(await screen.findByText("ABC AI")).toBeInTheDocument();
    expect(screen.getByText("Bakehaus")).toBeInTheDocument();
    const table = within(screen.getByRole("table"));
    expect(table.getByText("Pass")).toBeInTheDocument();
    expect(table.getByText("Fail")).toBeInTheDocument();
  });

  it("refetches with the chosen verdict filter", async () => {
    api.listOpportunities.mockResolvedValue([]);
    inRouter(<OpportunitiesPage />);
    await screen.findByText(/No opportunities match/);
    await userEvent.selectOptions(screen.getByLabelText("Verdict"), "fail");
    await waitFor(() =>
      expect(api.listOpportunities).toHaveBeenLastCalledWith({ verdict: "fail", status: "", q: "" }),
    );
  });

  it("shows an error with a retry button when the API is down", async () => {
    api.listOpportunities.mockRejectedValueOnce(new Error("Cannot reach the API"));
    api.listOpportunities.mockResolvedValue([row()]);
    inRouter(<OpportunitiesPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the API");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("ABC AI")).toBeInTheDocument();
  });
});

describe("OpportunityDetailPage", () => {
  const renderDetail = () =>
    inRouter(
      <Routes><Route path="/opportunities/:id" element={<OpportunityDetailPage />} /></Routes>,
      "/opportunities/1",
    );

  it("shows screening reasons, extracted fields, timeline and the raw pitch", async () => {
    api.getOpportunity.mockResolvedValue(detail());
    renderDetail();
    expect(await screen.findByText("AI-related (mentions 'ai')")).toBeInTheDocument();
    expect(screen.getByText("Germany")).toBeInTheDocument();
    expect(screen.getByText("received")).toBeInTheDocument();
    expect(screen.getByText("We are ABC AI")).toBeInTheDocument();
  });

  it("changing the status calls the API and reloads", async () => {
    api.getOpportunity.mockResolvedValueOnce(detail()).mockResolvedValue(detail({ status: "rejected" }));
    api.setStatus.mockResolvedValue(detail({ status: "rejected" }));
    renderDetail();
    await userEvent.click(await screen.findByRole("button", { name: "Rejected" }));
    expect(api.setStatus).toHaveBeenCalledWith(1, "rejected");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Rejected" })).toHaveAttribute("aria-pressed", "true"),
    );
  });

  it("offers a retry for failed items", async () => {
    api.getOpportunity.mockResolvedValue(
      detail({ processing_state: "failed", verdict: null, failed_step: "extracted", error: "boom", screening_reasons: [] }),
    );
    api.retry.mockResolvedValue(detail());
    renderDetail();
    expect(await screen.findByText("Processing failed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(api.retry).toHaveBeenCalledWith(1);
  });

  it("renders untrusted pitch text as plain text, not HTML", async () => {
    api.getOpportunity.mockResolvedValue(detail({ raw_body: "<img src=x onerror=alert(1)>" }));
    const { container } = renderDetail();
    await screen.findByText("<img src=x onerror=alert(1)>");
    expect(container.querySelector("img")).toBeNull();
  });
});

describe("SubmitPage", () => {
  const samples = [
    { id: "clean", label: "Clean pitch", pitch: { source: "email", sender: "a@b.c", subject: "Hi", body: "We are ABC AI" } },
  ];

  it("loads a sample into the form", async () => {
    api.samples.mockResolvedValue(samples);
    inRouter(<SubmitPage />);
    await screen.findByRole("option", { name: "Clean pitch" });
    await userEvent.selectOptions(screen.getByLabelText("Load sample"), "clean");
    expect(screen.getByLabelText("Message")).toHaveValue("We are ABC AI");
    expect(screen.getByLabelText("Subject")).toHaveValue("Hi");
  });

  it("tells the user when the pitch was already processed", async () => {
    api.samples.mockResolvedValue(samples);
    api.submitPitch.mockResolvedValue({ created: false, opportunity: detail() });
    inRouter(<SubmitPage />);
    await userEvent.type(screen.getByLabelText("Message"), "We are ABC AI");
    await userEvent.click(screen.getByRole("button", { name: "Process" }));
    expect(await screen.findByText(/Already processed/)).toBeInTheDocument();
  });

  it("shows why processing failed and where to find it", async () => {
    api.samples.mockResolvedValue([]);
    api.submitPitch.mockResolvedValue({
      created: true,
      opportunity: detail({ processing_state: "failed", verdict: null, failed_step: "extracted", error: "OPENAI_API_KEY is not set" }),
    });
    inRouter(<SubmitPage />);
    await userEvent.type(screen.getByLabelText("Message"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Process" }));
    expect(await screen.findByText(/OPENAI_API_KEY is not set/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Failures" })).toBeInTheDocument();
  });

  it("cannot submit an empty message", async () => {
    api.samples.mockResolvedValue([]);
    inRouter(<SubmitPage />);
    expect(screen.getByRole("button", { name: "Process" })).toBeDisabled();
  });
});

describe("FailuresPage", () => {
  it("lists failures and retries one", async () => {
    const failed = row({ processing_state: "failed", verdict: null, failed_step: "extracted", error: "bad output" });
    api.listFailures.mockResolvedValueOnce([failed]).mockResolvedValue([]);
    api.retry.mockResolvedValue(detail());
    inRouter(<FailuresPage />);
    expect(await screen.findByText("bad output")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry #1" }));
    expect(api.retry).toHaveBeenCalledWith(1);
    expect(await screen.findByText("No failed items.")).toBeInTheDocument();
  });
});
