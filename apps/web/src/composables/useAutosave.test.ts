// 文件说明：Vue 组合式逻辑：useAutosave.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAutosave } from "./useAutosave";

describe("useAutosave", () => {
  afterEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("debounces saves and clears the draft after success", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue(undefined);
    const autosave = useAutosave({
      key: () => "draft:stop-1",
      save,
      delay: 400,
    });

    autosave.schedule({ time: "09:00" });
    autosave.schedule({ time: "09:30" });
    expect(window.localStorage.getItem("draft:stop-1")).toContain("09:30");

    await vi.advanceTimersByTimeAsync(400);

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith({ time: "09:30" });
    expect(window.localStorage.getItem("draft:stop-1")).toBeNull();
    expect(autosave.status.value).toBe("saved");
  });

  it("keeps the local draft when saving fails", async () => {
    vi.useFakeTimers();
    const failure = new Error("offline");
    const autosave = useAutosave({
      key: () => "draft:stop-2",
      save: vi.fn().mockRejectedValue(failure),
      delay: 300,
    });

    autosave.schedule({ time: "14:00", duration: 90 });
    await vi.advanceTimersByTimeAsync(300);

    expect(autosave.status.value).toBe("error");
    expect(autosave.error.value).toBe(failure);
    expect(autosave.restoreDraft()).toEqual({
      time: "14:00",
      duration: 90,
    });
    expect(window.localStorage.getItem("draft:stop-2")).not.toBeNull();
  });

  it("can discard a local draft explicitly", () => {
    const autosave = useAutosave({
      key: () => "draft:stop-3",
      save: vi.fn(),
    });

    autosave.schedule({ time: "10:00" });
    autosave.discardDraft();

    expect(autosave.status.value).toBe("idle");
    expect(autosave.restoreDraft()).toBeNull();
  });
});
