import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { deleteAdapter, getAdapters, getSampleAdapters, installSampleAdapter } from "../api/adapters";
import type { Adapter, SampleAdapter } from "../types";
import { Adapters } from "./Adapters";

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast }) }));
vi.mock("../api/adapters", () => ({
  createAdapter: vi.fn(),
  deleteAdapter: vi.fn(),
  getAdapters: vi.fn(),
  getSampleAdapters: vi.fn(),
  installSampleAdapter: vi.fn(),
  testAdapter: vi.fn(),
  testAdapterProbe: vi.fn(),
  updateAdapter: vi.fn(),
}));

function adapter(id: string, name: string): Adapter {
  return {
    id, name, description: null, mode: "direct_http_adapter", transport: "http_json",
    base_url: `http://${name}.example.com`, auth_config: { type: "none" },
    invoke_config: { method: "POST", path: "/chat" },
    response_extract: { mode: "json_paths", text_path: "$.response" },
    probe_config: null, enabled: true, created_at: "2026-10-25T00:00:00Z", updated_at: "2026-10-25T00:00:00Z",
  } as Adapter;
}

const MAILBOT_SAMPLE: SampleAdapter = {
  key: "mailbot", name: "mailbot-agent", description: "MailBot", base_url: "http://localhost:8003",
  has_probe: true, installed_adapter_id: null, installed_enabled: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getSampleAdapters).mockResolvedValue([MAILBOT_SAMPLE]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("imports a sample adapter and opens it in the editor", async () => {
  const imported = adapter("adapter-mailbot", "mailbot-agent");
  vi.mocked(getAdapters).mockResolvedValueOnce([]).mockResolvedValue([imported]);
  vi.mocked(installSampleAdapter).mockResolvedValue({ adapter: imported, created: true });
  render(<Adapters />);

  fireEvent.click(await screen.findByRole("button", { name: "adapters.sampleImport" }));

  await waitFor(() => expect(installSampleAdapter).toHaveBeenCalledWith("mailbot"));
  await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "adapters.sampleImportSuccess"));
  expect(await screen.findByText("adapters.editAdapter: mailbot-agent")).toBeInTheDocument();
});

it("deletes the selected adapter after confirmation", async () => {
  const first = adapter("adapter-1", "first");
  const second = adapter("adapter-2", "second");
  vi.mocked(getAdapters).mockResolvedValueOnce([first, second]).mockResolvedValue([second]);
  vi.mocked(deleteAdapter).mockResolvedValue();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<Adapters />);

  fireEvent.click(await screen.findByRole("button", { name: "adapters.deleteAdapter" }));

  await waitFor(() => expect(deleteAdapter).toHaveBeenCalledWith("adapter-1"));
  await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "adapters.deleteSuccess"));
  expect(await screen.findByText("adapters.editAdapter: second")).toBeInTheDocument();
});

it("does nothing when the deletion is not confirmed", async () => {
  vi.mocked(getAdapters).mockResolvedValue([adapter("adapter-1", "first")]);
  vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<Adapters />);

  fireEvent.click(await screen.findByRole("button", { name: "adapters.deleteAdapter" }));

  expect(deleteAdapter).not.toHaveBeenCalled();
});

it("shows the server's reason when an adapter in use cannot be deleted", async () => {
  vi.mocked(getAdapters).mockResolvedValue([adapter("adapter-1", "first")]);
  vi.mocked(deleteAdapter).mockRejectedValue(new Error('{"error":"Adapter is used by 2 scan(s)"}'));
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<Adapters />);

  fireEvent.click(await screen.findByRole("button", { name: "adapters.deleteAdapter" }));

  await waitFor(() => expect(toast).toHaveBeenCalledWith(
    "error", 'adapters.failedToDelete: {"error":"Adapter is used by 2 scan(s)"}',
  ));
  expect(screen.getByText("adapters.editAdapter: first")).toBeInTheDocument();
});
