import { useState, useEffect, useRef } from "react";

const API_URL = "/api";
const CHAT_URL = `${API_URL}/chat`;
const SCREENSHOT_URL = "/api/screenshot/agentcore";

const DEVICES = [
  { name: "Desktop", width: 1440 },
  { name: "Tablet", width: 768 },
  { name: "Mobile", width: 375 },
];

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [html, setHtml] = useState("");
  const [version, setVersion] = useState(0);
  const [totalVersions, setTotalVersions] = useState(1);
  const [device, setDevice] = useState("Desktop");
  const [screenshotData, setScreenshotData] = useState(null);
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [previousHtml, setPreviousHtml] = useState("");
  const [versionsList, setVersionsList] = useState([]);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const merchantId = "demo-merchant";

  // Load initial storefront
  useEffect(() => {
    fetch(`${API_URL}/storefront/${merchantId}`)
      .then((r) => r.json())
      .then((data) => {
        setHtml(data.html);
        setVersion(data.version);
        setTotalVersions(data.totalVersions);
        setMessages([{ role: "system", text: "Welcome! Describe how you'd like to customize your storefront." }]);
      })
      .catch(() => {
        setMessages([{ role: "system", text: "Backend not running. Start it with: cd backend-shared && npm run dev" }]);
      });
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchantId, message: userMessage }),
      });

      const data = await res.json();

      if (res.ok) {
        // Handle structured responses
        if (data.type === "palette_options" && data.options) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: data.message, type: "palette_options", options: data.options },
          ]);
        } else if (data.type === "greeting" || data.type === "message") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: data.message },
          ]);
        } else if (data.type === "applied") {
          setPreviousHtml(html);
          setHtml(data.html);
          setVersion(data.version);
          setTotalVersions(data.totalVersions);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: data.message || `Done! Applied your changes. (v${data.version})` },
          ]);
        } else {
          // Fallback: treat as applied if html changed
          if (data.html && data.html !== html) {
            setPreviousHtml(html);
            setHtml(data.html);
            setVersion(data.version);
            setTotalVersions(data.totalVersions);
          }
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: data.message || `Done! (v${data.version})` },
          ]);
        }
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: `Error: ${data.error || "Something went wrong"}` },
        ]);
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

  async function handleUndo() {
    const res = await fetch(`${API_URL}/undo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId }),
    });
    const data = await res.json();
    setPreviousHtml(html);
    setHtml(data.html);
    setVersion(data.version);
    setTotalVersions(data.totalVersions);
  }

  async function handleRedo() {
    const res = await fetch(`${API_URL}/redo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId }),
    });
    const data = await res.json();
    setPreviousHtml(html);
    setHtml(data.html);
    setVersion(data.version);
    setTotalVersions(data.totalVersions);
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
    setMessages([{ role: "system", text: "Storefront reset to default." }]);
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

  async function handleScreenshot() {
    if (!html) return;
    setScreenshotLoading(true);

    try {
      const res = await fetch(SCREENSHOT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          html,
          viewport: { width: currentWidth(), height: 900 },
        }),
      });

      if (res.ok) {
        const contentType = res.headers.get("Content-Type");
        let blob;
        if (contentType && contentType.includes("image/png")) {
          blob = await res.blob();
        } else {
          // API Gateway may return base64 — decode it
          const data = await res.json();
          if (data.body) {
            const binary = atob(data.body);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            blob = new Blob([bytes], { type: "image/png" });
          }
        }
        if (blob) {
          const url = URL.createObjectURL(blob);
          const timeMs = res.headers.get("X-Screenshot-Time-Ms");
          setScreenshotData({ url, timeMs });
        } else {
          alert("Screenshot returned unexpected format.");
        }
      } else {
        alert("Screenshot failed.");
      }
    } catch {
      alert("Cannot connect to screenshot service.");
    } finally {
      setScreenshotLoading(false);
    }
  }

  function currentWidth() {
    return DEVICES.find((d) => d.name === device)?.width || 1440;
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function sendMessage(text) {
    if (!text.trim() || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchantId, message: text }),
    })
      .then((res) => res.json().then((data) => ({ res, data })))
      .then(({ res, data }) => {
        if (res.ok) {
          if (data.type === "palette_options" && data.options) {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: data.message, type: "palette_options", options: data.options },
            ]);
          } else if (data.type === "greeting" || data.type === "message") {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: data.message },
            ]);
          } else if (data.type === "applied") {
            setPreviousHtml(html);
            setHtml(data.html);
            setVersion(data.version);
            setTotalVersions(data.totalVersions);
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: data.message || `Done! Applied your changes.` },
            ]);
          } else {
            if (data.html && data.html !== html) {
              setPreviousHtml(html);
              setHtml(data.html);
              setVersion(data.version);
              setTotalVersions(data.totalVersions);
            }
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: data.message || "Done!" },
            ]);
          }
        } else {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: `Error: ${data.error || "Something went wrong"}` },
          ]);
        }
      })
      .catch((err) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: `Connection error: ${err.message}` },
        ]);
      })
      .finally(() => setLoading(false));
  }

  return (
    <div className="app">
      {/* Chat Panel */}
      <div className="chat-panel">
        <div className="chat-header">
          <h2>Storefront Customizer</h2>
          <div className="header-controls">
            <span className="version-info">
              v{version} / {totalVersions}
            </span>
          </div>
        </div>

        <div className="chat-actions">
          <button onClick={handleUndo} disabled={version <= 0}>
            ← Undo
          </button>
          <button onClick={handleRedo} disabled={version >= totalVersions - 1}>
            Redo →
          </button>
          <button onClick={handleReset}>Reset</button>
          <div className="versions-dropdown" style={{ position: "relative", display: "inline-block" }}>
            <button onClick={fetchVersions}>
              Versions ▾
            </button>
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
                  <div style={{ padding: "8px 12px", color: "#888", fontSize: 13 }}>No versions</div>
                ) : (
                  versionsList.map((v) => (
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
                      <span style={{ marginLeft: 8, color: "#888", fontSize: 11 }}>
                        {new Date(v.lastModified).toLocaleTimeString()}
                      </span>
                      {v.isCurrent && <span style={{ marginLeft: 8, color: "#28a745", fontSize: 11 }}>●</span>}
                    </button>
                  ))
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
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.text}
              {msg.type === "palette_options" && msg.options && (
                <div className="palette-options">
                  {msg.options.map((opt, j) => (
                    <button
                      key={j}
                      className="palette-card"
                      onClick={() => sendMessage(`I choose palette "${opt.name}"`)}
                      disabled={loading}
                    >
                      <div className="palette-name">{opt.name}</div>
                      <div className="palette-swatches">
                        {Object.entries(opt.colors).map(([key, color]) => (
                          <div
                            key={key}
                            className="swatch"
                            style={{ backgroundColor: color }}
                            title={`${key}: ${color}`}
                          />
                        ))}
                      </div>
                      <div className="palette-desc">{opt.description}</div>
                    </button>
                  ))}
                </div>
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

        <div className="chat-input-area">
          <input
            type="text"
            placeholder="Describe your changes..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button onClick={handleSend} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>

      {/* Preview Panel */}
      <div className="preview-panel">
        <div className="preview-toolbar">
          <div className="device-buttons">
            {DEVICES.map((d) => (
              <button
                key={d.name}
                className={device === d.name ? "active" : ""}
                onClick={() => setDevice(d.name)}
              >
                {d.name} ({d.width}px)
              </button>
            ))}
          </div>
          <div className="screenshot-controls">
            <button
              className={`compare-btn ${compareMode ? "active" : ""}`}
              onClick={() => setCompareMode(!compareMode)}
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
                <div className="preview-frame-wrapper" style={{ width: "100%" }}>
                  <iframe
                    srcDoc={previousHtml}
                    sandbox="allow-scripts"
                    title="Previous Version"
                  />
                </div>
              </div>
              <div className="compare-divider" />
              <div className="compare-pane">
                <div className="compare-label">Current</div>
                <div className="preview-frame-wrapper" style={{ width: "100%" }}>
                  <iframe
                    srcDoc={html}
                    sandbox="allow-scripts"
                    title="Current Version"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div
              className="preview-frame-wrapper"
              style={{ width: currentWidth() }}
            >
              <iframe
                srcDoc={html}
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
          <div
            className="screenshot-modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>
              Screenshot Preview{" "}
              {screenshotData.timeMs && (
                <span style={{ fontSize: 12, color: "#888", fontWeight: 400 }}>
                  ({screenshotData.timeMs}ms)
                </span>
              )}
            </h3>
            <img src={screenshotData.url} alt="Storefront screenshot" />
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <a
                href={screenshotData.url}
                download="storefront-preview.png"
                className="close-btn"
                style={{ textDecoration: "none", textAlign: "center" }}
              >
                Download
              </a>
              <button
                className="close-btn"
                onClick={() => setScreenshotData(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
