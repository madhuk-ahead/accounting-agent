// Press Release Drafting Assistant – WebSocket chat client

let ws = null;
let transcript = "";
let currentFileContent = "";

function initWebSocket() {
    if (!WS_URL) {
        console.error("WebSocket URL not configured");
        appendMessage("SYSTEM", "Error: WebSocket URL not configured.");
        return;
    }
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        console.log("WebSocket connected");
        appendMessage("SYSTEM", "Connected. Fill in the form and click Draft press release, or type a message to refine your draft.");
    };
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "status") {
                document.getElementById("status-area").textContent = msg.content || "";
            } else if (msg.type === "final") {
                document.getElementById("status-area").textContent = "";
                appendMessage("AGENT", msg.content || "");
                transcript += "\nAGENT: " + (msg.content || "");
                if (msg.file_content) {
                    currentFileContent = msg.file_content;
                    const preview = document.getElementById("file-preview");
                    preview.textContent = msg.file_content;
                    preview.classList.add("has-content");
                    document.getElementById("download-btn").disabled = false;
                }
            } else if (msg.type === "error") {
                document.getElementById("status-area").textContent = "";
                const errContent = msg.content || msg.message || (typeof msg.body === "string" ? msg.body : null);
                const fallback = msg.statusCode ? "Server error " + msg.statusCode + ". Check CloudWatch logs." : "Unknown error (check browser console)";
                appendMessage("SYSTEM", "Error: " + (errContent || fallback));
                if (!errContent) console.warn("Error message missing content:", msg);
            }
        } catch (e) {
            console.error("Parse error:", e);
        }
    };
    ws.onerror = () => appendMessage("SYSTEM", "Connection error. Refresh to reconnect.");
    ws.onclose = () => appendMessage("SYSTEM", "Connection closed. Refresh to reconnect.");
}

function getFormData() {
    return {
        rough_draft: (document.getElementById("rough-draft")?.value || "").trim(),
        key_topics: (document.getElementById("key-topics")?.value || "").trim(),
        tone: document.getElementById("tone")?.value || "professional",
        audience: (document.getElementById("audience")?.value || "").trim() || undefined,
        length: (document.getElementById("length")?.value || "").trim() || undefined,
        cta: (document.getElementById("cta")?.value || "").trim() || undefined,
        exclusions: (document.getElementById("exclusions")?.value || "").trim() || undefined,
    };
}

function hasAnyInput(formData) {
    return !!(formData.rough_draft || formData.key_topics || formData.audience || formData.length || formData.cta || formData.exclusions);
}

function draftPressRelease() {
    const formData = getFormData();
    if (!hasAnyInput(formData)) {
        appendMessage("SYSTEM", "Please provide at least a rough draft, key topics, or optional constraints (audience, length, CTA, exclusions).");
        scrollChatIntoView();
        return;
    }
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        appendMessage("SYSTEM", "Not connected. Refresh the page to reconnect.");
        scrollChatIntoView();
        return;
    }
    const statusEl = document.getElementById("status-area");
    if (statusEl) statusEl.textContent = "Drafting...";
    const text = formData.rough_draft ? "Draft a press release" : (formData.key_topics ? "Draft a press release from key topics" : "Draft a press release");
    transcript += "\nUSER: " + text;
    ws.send(JSON.stringify({
        action: "message",
        text: text,
        conversation: transcript,
        form_data: formData,
    }));
    appendMessage("USER", text);
    document.getElementById("draft-btn").disabled = true;
    setTimeout(() => { document.getElementById("draft-btn").disabled = false; }, 2000);
}

function sendMessage() {
    const input = document.getElementById("user-input");
    const text = (input && input.value.trim()) || "";
    if (!text) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        appendMessage("SYSTEM", "Not connected. Refresh the page.");
        return;
    }
    transcript += "\nUSER: " + text;
    ws.send(JSON.stringify({ action: "message", text: text, conversation: transcript }));
    appendMessage("USER", text);
    input.value = "";
}

function downloadPressRelease() {
    if (!currentFileContent) return;
    const blob = new Blob([currentFileContent], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "PressRelease.md";
    a.click();
    URL.revokeObjectURL(url);
}

function scrollChatIntoView() {
    const el = document.getElementById("chat-section");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function appendMessage(role, content) {
    const el = document.getElementById("chat-messages");
    if (!el) return;
    const div = document.createElement("div");
    div.className = "message " + role.toLowerCase();
    div.innerHTML = "<span class='label'>" + role + "</span> " + escapeHtml(content);
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    document.getElementById("draft-btn")?.addEventListener("click", draftPressRelease);
    document.getElementById("download-btn")?.addEventListener("click", downloadPressRelease);
    const input = document.getElementById("user-input");
    if (input) {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }
});
