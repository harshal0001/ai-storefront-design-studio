/**
 * Design Studio shell — chat panel + mobile storefront preview iframe.
 *
 * Talks to the deployed ``/api`` routes. Syncs zone tour state via
 * ``useZoneTourSync``; applies ``section_focus`` highlights from API payloads.
 * Version undo/redo uses ``/api/versions``; publish/reset per merchantId.
 */
import { useState, useEffect, useRef } from "react";
import { MarkdownText } from "./components/MarkdownText";
import { ZoneTourChatBlocks } from "./components/ZoneTourChatBlocks";
import { useZoneTourSync } from "./hooks/useZoneTourSync";
import { buildZoneTourChatMessage, messageHasTourOptions } from "./utils/zoneChatIntro";

const API_URL = "/api";
const CHAT_URL = `${API_URL}/chat`;
const SCREENSHOT_URL = "/api/screenshot";
const DEFAULT_MERCHANT_ID = "demo-merchant";
const MERCHANT_STORAGE_KEY = "designStudioMerchantId";
const SESSION_STORAGE_KEY = "designStudioSessionId";
const MOBILE_WIDTH = 390;

/** Parse JSON and throw with API ``detail`` when ``response.ok`` is false. */
async function parseJsonResponse(res) {
  const data = await res.json();
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d?.msg ?? String(d)).join("; ")
          : data?.message;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return data;
}

function formatVersionTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

function getInitialMerchantId() {
  // TODO(auth): replace client-supplied merchantId with the verified JWT claim.
  try {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("merchantId")?.trim();
    if (fromUrl) {
      window.localStorage.setItem(MERCHANT_STORAGE_KEY, fromUrl);
      return fromUrl;
    }
    return window.localStorage.getItem(MERCHANT_STORAGE_KEY) || DEFAULT_MERCHANT_ID;
  } catch {
    return DEFAULT_MERCHANT_ID;
  }
}

function getOrCreateSessionId() {
  try {
    const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) return existing;
    const generated = crypto.randomUUID();
    window.localStorage.setItem(SESSION_STORAGE_KEY, generated);
    return generated;
  } catch {
    return `session-${Date.now()}`;
  }
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [html, setHtml] = useState("");
  const [version, setVersion] = useState(0);
  const [totalVersions, setTotalVersions] = useState(1);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previousPreviewUrl, setPreviousPreviewUrl] = useState("");
  const [screenshotData, setScreenshotData] = useState(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [previousHtml, setPreviousHtml] = useState("");
  const [versionsList, setVersionsList] = useState([]);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const { zoneTour, syncZoneTourFromApi, clearZoneTour } = useZoneTourSync();
  const [sections, setSections] = useState([]);
  const [focusSection, setFocusSection] = useState(null);
  const [focusElement, setFocusElement] = useState(null);
  const [detectedFocus, setDetectedFocus] = useState(null);
  const [attachment, setAttachment] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const [merchantId] = useState(getInitialMerchantId);
  const [sessionId] = useState(getOrCreateSessionId);

  async function fetchStorefront(signal) {
    const res = await fetch(`${API_URL}/storefront/${merchantId}`, { signal });
    return parseJsonResponse(res);
  }

  async function refreshStorefront(signal) {
    const data = await fetchStorefront(signal);
    applyApiData(data);
    return data;
  }

  function fetchZoneTour(signal) {
    return fetch(`${API_URL}/storefront/${merchantId}`, { signal })
      .then((r) => parseJsonResponse(r))
      .then((data) => {
        syncZoneTourFromApi(data);
        return data;
      })
      .catch((err) => {
        if (err?.name === "AbortError") throw err;
        clearZoneTour();
      });
  }

  function applyApiData(data) {
    if (data.html) {
      if (html && data.html !== html) setPreviousHtml(html);
      setHtml(data.html);
      setPreviewKey(data.previewTs ?? Date.now());
    }
    if (data.version !== undefined) setVersion(data.version);
    if (data.totalVersions !== undefined) setTotalVersions(data.totalVersions);
    if (data.canUndo !== undefined) setCanUndo(data.canUndo);
    if (data.canRedo !== undefined) setCanRedo(data.canRedo);
    if (data.sections?.length) setSections(data.sections);
    if (data.section_focus) {
      if (data.section_focus.source === "text") {
        setDetectedFocus(data.section_focus);
      } else {
        setFocusSection({
          zone: data.section_focus.zone,
          sectionId: data.section_focus.sectionId,
          label: data.section_focus.label,
          source: data.section_focus.source,
        });
        setFocusElement(
          data.section_focus.elementId
            ? {
                id: data.section_focus.elementId,
                label: data.section_focus.elementLabel,
                displayLabel: data.section_focus.displayLabel,
              }
            : null,
        );
        setDetectedFocus(null);
      }
    }
    syncZoneTourFromApi(data);
  }

  function buildAssistantMessage(data) {
    const msgObj = { role: "assistant", text: data.message, type: data.type };
    if (data.vibe_options) msgObj.vibe_options = data.vibe_options;
    if (data.theme_packages) msgObj.theme_packages = data.theme_packages;
    if (data.color_options?.length) msgObj.color_options = data.color_options;
    if (data.zone_options?.length) msgObj.zone_options = data.zone_options;
    if (data.zone_tour) msgObj.zone_tour = data.zone_tour;
    return msgObj;
  }

  const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/webp,image/gif";
  const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024; // 5 MB

  function handleAttachmentChange(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("Please attach an image file.");
      return;
    }
    if (file.size > MAX_ATTACHMENT_BYTES) {
      alert("Attachment is too large (max 5 MB).");
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    setAttachment({ file, name: file.name, type: file.type, size: file.size, previewUrl });
  }

  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result;
        const comma = result.indexOf(",");
        resolve(comma >= 0 ? result.slice(comma + 1) : result);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  function clearAttachment() {
    if (attachment?.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    setAttachment(null);
  }

  // Load initial storefront and get greeting from agent
  useEffect(() => {
    const ac = new AbortController();
    let active = true;

    (async () => {
      try {
        const storefrontData = await fetchStorefront(ac.signal);
        if (!active) return;
        applyApiData(storefrontData);
        await fetchZoneTour(ac.signal);
        if (!active) return;

        const greetRes = await fetch(CHAT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ merchantId, sessionId, message: "" }),
          signal: ac.signal,
        });
        const greetData = await parseJsonResponse(greetRes);
        if (!active) return;
        if (!greetData.message) return;

        const msgs = [buildAssistantMessage(greetData)];
        if (storefrontData?.zone_tour?.active) {
          applyApiData(storefrontData);
          msgs.push(buildZoneTourChatMessage(storefrontData));
        }
        setMessages(msgs);
      } catch (err) {
        if (!active || err.name === "AbortError") return;
        setMessages([
          {
            role: "system",
            text: err.message || "Backend not running. Start with: uv run design-server",
          },
        ]);
      }
    })();

    return () => {
      active = false;
      ac.abort();
    };
  }, []);

  useEffect(() => {
    const host = messagesEndRef.current?.parentElement;
    if (!host) return;
    host.scrollTo({ top: host.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // Blob URL forces iframe to re-execute the full HTML (including injected theme
  // JS) on every preview update. We revoke the *previous* URL only after setting
  // the new one so the iframe never briefly points at a revoked blob.
  const prevBlobRef = useRef("");
  useEffect(() => {
    if (!html) {
      if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current);
      prevBlobRef.current = "";
      setPreviewUrl("");
      return;
    }
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);
    // Revoke the old URL *after* the new one is live
    if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current);
    prevBlobRef.current = url;
  }, [html, previewKey]);

  useEffect(() => {
    return () => {
      if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current);
    };
  }, []);

  useEffect(() => {
    if (!previousHtml) {
      setPreviousPreviewUrl("");
      return undefined;
    }
    const blob = new Blob([previousHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    setPreviousPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [previousHtml]);

  // Z5 info-only: show offers script when tour lands on Z5
  useEffect(() => {
    if (!zoneTour?.info_only || !zoneTour?.z5_message) return;
    setMessages((prev) => {
      if (prev.some((m) => m.role === "assistant" && m.zone_tour?.info_only)) {
        return prev;
      }
      return [
        ...prev,
        {
          role: "assistant",
          text: zoneTour.z5_message,
          type: "zone_tour",
          zone_tour: zoneTour,
        },
      ];
    });
  }, [zoneTour?.current_zone, zoneTour?.info_only, zoneTour?.z5_message]);

  function handleSend() {
    if ((!input.trim() && !attachment) || loading) return;
    postChatMessage(input.trim(), attachment);
  }

  async function handleUndo() {
    if (!canUndo) return;
    try {
      const res = await fetch(`${API_URL}/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchantId }),
      });
      const data = await res.json();
      if (res.ok) applyApiData(data);
    } catch (err) {
      console.error("Undo failed", err);
    }
  }

  async function handleRedo() {
    if (!canRedo) return;
    try {
      const res = await fetch(`${API_URL}/redo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchantId }),
      });
      const data = await res.json();
      if (res.ok) applyApiData(data);
    } catch (err) {
      console.error("Redo failed", err);
    }
  }

  async function handleReset() {
    const res = await fetch(`${API_URL}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId }),
    });
    const data = await res.json();
    setHtml(data.html);
    setVersion(data.version);
    setTotalVersions(data.totalVersions);
    // Get fresh greeting after reset
    const greetRes = await fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId, sessionId, message: "" }),
    });
    const greetData = await greetRes.json();
    clearZoneTour();
    setMessages([
      { role: "assistant", text: greetData.message || "Storefront reset. Let's start fresh!" },
    ]);
  }

  async function fetchVersions() {
    try {
      const res = await fetch(`${API_URL}/versions/${merchantId}`);
      const data = await res.json();
      setVersionsList(data.versions || []);
      setVersionsOpen(true);
    } catch {
      setVersionsList([]);
    }
  }

  async function handleRestore(versionId) {
    setVersionsOpen(false);
    const res = await fetch(`${API_URL}/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId, versionId }),
    });
    const data = await res.json();
    setPreviousHtml(html);
    setHtml(data.html);
    setVersion(data.version);
    setTotalVersions(data.totalVersions);
    setMessages((prev) => [...prev, { role: "system", text: "Restored to selected version." }]);
  }

  function openPublish() {
    setPublishResult(null);
    setPublishOpen(true);
  }

  function closePublish() {
    if (publishing) return;
    setPublishOpen(false);
    setPublishResult(null);
  }

  async function handlePublish() {
    setPublishing(true);
    try {
      const res = await fetch(`${API_URL}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchantId }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        if (data.html) setHtml(data.html);
        setPublishResult({ ok: true, ...data });
      } else {
        const friendly =
          res.status === 400
            ? "No changes to publish yet — make an edit first."
            : res.status === 503
              ? "Publishing isn't available right now (storage not configured)."
              : data.detail || "Publish failed.";
        setPublishResult({ ok: false, message: friendly });
      }
    } catch {
      setPublishResult({ ok: false, message: "Publish failed — please try again." });
    } finally {
      setPublishing(false);
    }
  }

  async function handleScreenshot() {
    if (!html) return;
    setScreenshotLoading(true);

    try {
      const res = await fetch(SCREENSHOT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchantId,
          viewport: { width: MOBILE_WIDTH, height: 900 },
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setScreenshotData({
          url: data.url,
          timeMs: data.timeMs,
          expiresIn: data.expiresIn,
          shareUrl: data.expiresIn ? data.url : null,
        });
      } else {
        alert("Screenshot failed.");
      }
    } catch {
      alert("Cannot connect to screenshot service.");
    } finally {
      setScreenshotLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function refreshPreviewFocus(zone, elementId) {
    const params = new URLSearchParams();
    if (zone) params.set("focusZone", zone);
    if (elementId) params.set("focusElementId", elementId);
    const q = params.toString() ? `?${params}` : "";
    try {
      const res = await fetch(`${API_URL}/storefront/${merchantId}${q}`);
      const data = await res.json();
      applyApiData(data);
    } catch {
      /* preview highlight is best-effort */
    }
  }

  function applyFocusTarget(sec, el, source = "chip") {
    setFocusSection({
      zone: sec.zone,
      sectionId: sec.id,
      label: sec.label,
      source,
    });
    setFocusElement(
      el
        ? {
            id: el.id,
            label: el.label,
            displayLabel: `${el.label} · ${sec.label}`,
          }
        : null,
    );
    setDetectedFocus(null);
    refreshPreviewFocus(sec.zone, el?.id ?? null);
  }

  function selectFocusSection(sec, source = "chip") {
    applyFocusTarget(sec, null, source);
  }

  function selectFocusElement(sec, el, source = "chip") {
    applyFocusTarget(sec, el, source);
  }

  function clearFocusSection() {
    setFocusSection(null);
    setFocusElement(null);
    setDetectedFocus(null);
    refreshPreviewFocus(null, null);
  }

  const activeSection = focusSection ? sections.find((s) => s.id === focusSection.sectionId) : null;

  function focusDisplayLabel() {
    if (focusElement?.displayLabel) return focusElement.displayLabel;
    if (focusSection?.label) return focusSection.label;
    if (detectedFocus?.displayLabel) return detectedFocus.displayLabel;
    if (detectedFocus?.elementLabel) {
      return `${detectedFocus.elementLabel} · ${detectedFocus.label}`;
    }
    if (detectedFocus?.label) return detectedFocus.label;
    return null;
  }

  useEffect(() => {
    function onPreviewMessage(event) {
      const d = event.data;
      if (d?.type !== "sf-focus-target" && d?.type !== "sf-focus-section") return;
      const match = sections.find((s) => s.id === d.sectionId || s.zone === d.zone);
      const sec = match || {
        id: d.sectionId || d.zone,
        zone: d.zone,
        label: d.label || d.sectionId || d.zone,
        chipLabel: d.label || d.sectionId || d.zone,
        elements: [],
      };
      if (d.elementId) {
        const el = sec.elements?.find((e) => e.id === d.elementId) || {
          id: d.elementId,
          label: d.label || d.elementId,
          chipLabel: d.label || d.elementId,
        };
        applyFocusTarget(sec, el, "preview");
      } else {
        applyFocusTarget(sec, null, "preview");
      }
    }
    window.addEventListener("message", onPreviewMessage);
    return () => window.removeEventListener("message", onPreviewMessage);
  }, [sections]);

  function focusPlaceholder() {
    if (zoneTour?.active) {
      return "Describe what you want, or pick an option in the chat above…";
    }
    const label = focusDisplayLabel();
    if (label) return `Describe changes to ${label}…`;
    return "Pick a zone, then an element — or click directly in the preview…";
  }

  async function postChatMessage(text, sentAttachment = null) {
    if ((!text.trim() && !sentAttachment) || loading) return;
    setInput("");
    if (sentAttachment) setAttachment(null);
    const display = focusDisplayLabel();
    const userMeta = display ? { focusLabel: display } : null;
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: text.trim(),
        ...(userMeta || {}),
        attachment: sentAttachment
          ? {
              name: sentAttachment.name,
              type: sentAttachment.type,
              size: sentAttachment.size,
              previewUrl: sentAttachment.previewUrl,
            }
          : undefined,
      },
    ]);
    setLoading(true);
    try {
      const body = {
        merchantId,
        sessionId,
        message: text.trim(),
        focusZone: focusSection?.zone ?? null,
        focusSectionId: focusSection?.sectionId ?? null,
        focusElementId: focusElement?.id ?? null,
      };
      if (sentAttachment) {
        body.image = await readFileAsBase64(sentAttachment.file);
        body.imageType = sentAttachment.type;
      }
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        applyApiData(data);
        setMessages((prev) => [...prev, buildAssistantMessage(data)]);
        refreshStorefront().catch((err) => {
          console.warn("Preview refresh failed", err);
        });
      } else {
        const detail = data.detail ?? data.error;
        const errText = Array.isArray(detail)
          ? detail.map((x) => x.msg || x).join("; ")
          : detail || "Something went wrong";
        setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${errText}` }]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Connection error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function sendMessage(text) {
    postChatMessage(text);
  }

  const lastTourOptionsMsgIdx = messages.reduce(
    (found, m, i) => (messageHasTourOptions(m) ? i : found),
    -1,
  );
  const displayVersion = version + 1;

  return (
    <div className="app">
      {/* Chat Panel */}
      <div className={`chat-panel${zoneTour?.active ? " chat-panel--tour" : ""}`}>
        <div className="chat-header">
          <h2>✨ Design Studio</h2>
          <div className="header-controls">
            <span className="version-info">
              v{displayVersion} / {totalVersions}
            </span>
          </div>
        </div>

        <div className="chat-actions">
          <button onClick={handleUndo} disabled={!canUndo}>
            ← Undo
          </button>
          <button onClick={handleRedo} disabled={!canRedo}>
            Redo →
          </button>
          <button onClick={handleReset}>Reset</button>
          <div
            className="versions-dropdown"
            style={{ position: "relative", display: "inline-block" }}
          >
            <button onClick={fetchVersions}>Versions ▾</button>
            {versionsOpen && (
              <div
                className="versions-menu"
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  zIndex: 100,
                  background: "#fff",
                  border: "1px solid #ddd",
                  borderRadius: 6,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                  minWidth: 220,
                  marginTop: 4,
                }}
              >
                {versionsList.length === 0 ? (
                  <div style={{ padding: "8px 12px", color: "#888", fontSize: 13 }}>
                    No versions
                  </div>
                ) : (
                  versionsList.map((v) => {
                    const timeLabel = formatVersionTime(v.lastModified);
                    return (
                      <button
                        key={v.versionId}
                        onClick={() => handleRestore(v.versionId)}
                        disabled={v.isCurrent}
                        style={{
                          display: "block",
                          width: "100%",
                          textAlign: "left",
                          padding: "8px 12px",
                          border: "none",
                          background: v.isCurrent ? "#f0f0f0" : "transparent",
                          cursor: v.isCurrent ? "default" : "pointer",
                          fontSize: 13,
                          borderBottom: "1px solid #eee",
                        }}
                      >
                        <strong>{v.label}</strong>
                        {timeLabel && (
                          <span style={{ marginLeft: 8, color: "#888", fontSize: 11 }}>
                            {timeLabel}
                          </span>
                        )}
                        {v.isCurrent && (
                          <span style={{ marginLeft: 8, color: "#28a745", fontSize: 11 }}>●</span>
                        )}
                      </button>
                    );
                  })
                )}
                <button
                  onClick={() => setVersionsOpen(false)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "center",
                    padding: "6px",
                    border: "none",
                    background: "#f8f8f8",
                    cursor: "pointer",
                    fontSize: 12,
                    color: "#666",
                    borderRadius: "0 0 6px 6px",
                  }}
                >
                  Close
                </button>
              </div>
            )}
          </div>
          <button
            className="publish-btn"
            onClick={openPublish}
            style={{
              marginLeft: "auto",
              background: "#0d9488",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              padding: "6px 16px",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Publish
          </button>
        </div>

        {publishOpen && (
          <div
            className="publish-overlay"
            onClick={closePublish}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
            }}
          >
            <div
              className="publish-modal"
              onClick={(e) => e.stopPropagation()}
              style={{
                background: "#fff",
                borderRadius: 10,
                padding: "24px 28px",
                maxWidth: 420,
                width: "90%",
                boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
              }}
            >
              {!publishResult ? (
                <>
                  <h3 style={{ marginTop: 0 }}>Publish to your live storefront?</h3>
                  <p style={{ color: "#555", fontSize: 14 }}>
                    Your current design will go live for visitors. You can roll back within 7 days.
                  </p>
                  <div
                    style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}
                  >
                    <button onClick={closePublish} disabled={publishing}>
                      Cancel
                    </button>
                    <button
                      onClick={handlePublish}
                      disabled={publishing}
                      style={{
                        background: "#0d9488",
                        color: "#fff",
                        border: "none",
                        borderRadius: 6,
                        padding: "6px 16px",
                        fontWeight: 600,
                      }}
                    >
                      {publishing ? "Publishing…" : "Publish"}
                    </button>
                  </div>
                </>
              ) : publishResult.ok ? (
                <>
                  <h3 style={{ marginTop: 0, color: "#0d9488" }}>✓ Published!</h3>
                  {publishResult.changeSummary && (
                    <p style={{ fontSize: 14 }}>
                      <strong>What changed:</strong> {publishResult.changeSummary}
                    </p>
                  )}
                  {publishResult.rollbackUntil && (
                    <p style={{ color: "#555", fontSize: 13 }}>
                      You can roll back until{" "}
                      {new Date(publishResult.rollbackUntil).toLocaleDateString()}.
                    </p>
                  )}
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
                    <button onClick={closePublish}>Done</button>
                  </div>
                </>
              ) : (
                <>
                  <h3 style={{ marginTop: 0, color: "#c0392b" }}>Couldn&apos;t publish</h3>
                  <p style={{ fontSize: 14 }}>{publishResult.message}</p>
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
                    <button onClick={closePublish}>Close</button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {zoneTour?.active && (
          <div className="zone-tour-bar zone-tour-bar--compact">
            <div className="zone-tour-header">
              <span className="zone-tour-label">
                Customise by area — {zoneTour.editable_completed}/{zoneTour.editable_total}
              </span>
              {zoneTour.current_zone_name && (
                <span className="zone-tour-current">{zoneTour.current_zone_name}</span>
              )}
            </div>
            <div className="zone-tour-steps">
              {zoneTour.steps?.map((step) => (
                <span
                  key={step.code}
                  className={[
                    "zone-step-pill",
                    step.current ? "current" : "",
                    step.done ? "done" : "",
                    step.skipped ? "skipped" : "",
                    step.info_only ? "info-only" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  title={step.code}
                >
                  {step.name}
                </span>
              ))}
            </div>
            <div className="zone-tour-actions">
              {zoneTour.can_skip && (
                <button
                  type="button"
                  className="zone-skip-btn"
                  onClick={() => sendMessage("Skip this zone")}
                  disabled={loading}
                >
                  Skip this area
                </button>
              )}
              <button
                type="button"
                className="zone-exit-btn"
                onClick={() => sendMessage("Exit zone customization")}
                disabled={loading}
                title="Leave the guided zone tour and return to free-form chat"
              >
                Exit customization
              </button>
            </div>
          </div>
        )}

        <div className="chat-panel-body">
          <div className="chat-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                {msg.role === "user" && msg.focusLabel && (
                  <div className="message-focus-tag">→ {msg.focusLabel}</div>
                )}
                {msg.role === "user" && msg.detectedFocus && (
                  <div className="message-focus-tag message-focus-tag--detected">
                    Detected: {msg.detectedFocus}
                  </div>
                )}
                {msg.attachment && (
                  <div className="message-attachment">
                    {msg.attachment.previewUrl ? (
                      <img
                        src={msg.attachment.previewUrl}
                        alt={msg.attachment.name}
                        className="message-attachment-image"
                      />
                    ) : (
                      <div className="message-attachment-file">
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                        <span className="message-attachment-name">{msg.attachment.name}</span>
                      </div>
                    )}
                  </div>
                )}
                {msg.text && (
                  <div className="message-text">
                    {msg.text.split("\n\n").map((para, pi) => (
                      <p key={pi} className="message-text__para">
                        <MarkdownText text={para} />
                      </p>
                    ))}
                  </div>
                )}

                {messageHasTourOptions(msg) &&
                  (!zoneTour?.active || i === lastTourOptionsMsgIdx) && (
                    <ZoneTourChatBlocks
                      zoneTour={zoneTour?.active ? zoneTour : msg.zone_tour}
                      colorOptions={i === lastTourOptionsMsgIdx ? msg.color_options || [] : []}
                      zoneOptions={i === lastTourOptionsMsgIdx ? msg.zone_options || [] : []}
                      vibeOptions={i === lastTourOptionsMsgIdx ? msg.vibe_options || [] : []}
                      themePackages={i === lastTourOptionsMsgIdx ? msg.theme_packages || [] : []}
                      onPickOption={sendMessage}
                      onExitTour={() => sendMessage("Exit zone customization")}
                      onGotIt={() => sendMessage("Got it, continue the tour")}
                      onSkipStep={() => sendMessage("Skip this step")}
                      loading={loading}
                    />
                  )}
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <span className="loading" /> Customizing...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {!zoneTour?.active && sections.length > 0 && (
          <div className="section-focus-bar">
            <div className="section-focus-label">1. Zone · 2. Element (or click the preview)</div>
            <div className="section-focus-chips">
              {sections.map((sec) => (
                <button
                  key={sec.id}
                  type="button"
                  className={`section-focus-chip section-focus-chip--zone${
                    focusSection?.sectionId === sec.id ? " is-active" : ""
                  }`}
                  onClick={() => selectFocusSection(sec, "chip")}
                  disabled={loading}
                  title={sec.label}
                >
                  {sec.chipLabel}
                </button>
              ))}
            </div>
            {activeSection?.elements?.length > 0 && (
              <>
                <div className="section-focus-label section-focus-label--sub">
                  Elements in {activeSection.chipLabel}
                </div>
                <div className="section-focus-chips section-focus-chips--elements">
                  {activeSection.elements.map((el) => (
                    <button
                      key={el.id}
                      type="button"
                      className={`section-focus-chip section-focus-chip--element${
                        focusElement?.id === el.id ? " is-active" : ""
                      }`}
                      onClick={() => selectFocusElement(activeSection, el, "chip")}
                      disabled={loading}
                      title={el.label}
                    >
                      {el.chipLabel}
                    </button>
                  ))}
                </div>
              </>
            )}
            {(focusSection || focusElement) && (
              <div className="section-focus-active">
                <span>
                  Editing: <strong>{focusDisplayLabel()}</strong>
                </span>
                <button type="button" className="section-focus-clear" onClick={clearFocusSection}>
                  Clear
                </button>
              </div>
            )}
            {detectedFocus && !focusSection && (
              <div className="section-focus-detected">Detected: {focusDisplayLabel()}</div>
            )}
          </div>
        )}

        <div className="chat-input-area">
          {attachment && (
            <div className="attachment-preview">
              {attachment.previewUrl ? (
                <img src={attachment.previewUrl} alt={attachment.name} />
              ) : (
                <svg
                  className="attachment-icon"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              )}
              <span className="attachment-name" title={attachment.name}>
                {attachment.name}
              </span>
              <button
                type="button"
                className="attachment-remove"
                onClick={clearAttachment}
                aria-label="Remove attachment"
              >
                ×
              </button>
            </div>
          )}
          <div className="chat-input-row">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={handleAttachmentChange}
              style={{ display: "none" }}
            />
            <button
              type="button"
              className="attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              aria-label="Attach image"
              title="Attach a photo or logo"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6z" />
              </svg>
            </button>
            <input
              type="text"
              placeholder={focusPlaceholder()}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button onClick={handleSend} disabled={loading || (!input.trim() && !attachment)}>
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Preview Panel */}
      <div className="preview-panel">
        <div className="preview-toolbar">
          <div className="device-buttons">
            <span style={{ color: "#888", fontSize: 12 }}>Mobile Preview (390px)</span>
          </div>
          <div className="screenshot-controls">
            <button
              className={`compare-btn ${compareMode ? "active" : ""}`}
              onClick={() => setCompareMode(!compareMode)}
              disabled={!previousHtml}
            >
              {compareMode ? "Single" : "⇄ Compare"}
            </button>
            <button
              className="screenshot-btn"
              onClick={handleScreenshot}
              disabled={screenshotLoading}
            >
              {screenshotLoading ? "Capturing..." : "📸 Screenshot"}
            </button>
          </div>
        </div>

        <div className="preview-container">
          {compareMode && previousHtml ? (
            <div className="compare-view">
              <div className="compare-pane">
                <div className="compare-label">Previous</div>
                <div className="preview-frame-wrapper" style={{ width: 390 }}>
                  <iframe
                    src={previousPreviewUrl || undefined}
                    srcDoc={previousPreviewUrl ? undefined : previousHtml}
                    sandbox="allow-scripts"
                    title="Previous Version"
                  />
                </div>
              </div>
              <div className="compare-divider" />
              <div className="compare-pane">
                <div className="compare-label">Current</div>
                <div className="preview-frame-wrapper" style={{ width: 390 }}>
                  <iframe
                    src={previewUrl || undefined}
                    srcDoc={previewUrl ? undefined : html}
                    sandbox="allow-scripts"
                    title="Current Version"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="preview-frame-wrapper" style={{ width: 390 }}>
              <iframe
                src={previewUrl || undefined}
                srcDoc={previewUrl ? undefined : html}
                sandbox="allow-scripts"
                title="Storefront Preview"
              />
            </div>
          )}
        </div>
      </div>

      {/* Screenshot Modal */}
      {screenshotData && (
        <div className="screenshot-modal" onClick={() => setScreenshotData(null)}>
          <div className="screenshot-modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>
              Screenshot Preview{" "}
              {screenshotData.timeMs && (
                <span style={{ fontSize: 12, color: "#888", fontWeight: 400 }}>
                  ({screenshotData.timeMs}ms)
                </span>
              )}
            </h3>
            <img src={screenshotData.url} alt="Storefront screenshot" />
            {screenshotData.expiresIn && (
              <p style={{ fontSize: 12, color: "#888", margin: "8px 0 0" }}>
                Share link expires in {Math.round(screenshotData.expiresIn / 60)} min
              </p>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button
                className="close-btn"
                onClick={async (e) => {
                  e.stopPropagation();
                  try {
                    const res = await fetch(screenshotData.url, { mode: "cors" });
                    const blob = await res.blob();
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(blob);
                    a.download = "storefront-preview.png";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(a.href);
                  } catch {
                    window.open(screenshotData.url, "_blank");
                  }
                }}
              >
                Download
              </button>
              <button
                className="close-btn"
                onClick={() => {
                  navigator.clipboard.writeText(screenshotData.url);
                  alert("Share link copied!");
                }}
              >
                Copy link
              </button>
              <button className="close-btn" onClick={() => setScreenshotData(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
