// WebSocket chat client for agent template

let ws = null;
let transcript = "";

function initWebSocket() {
    if (!WS_URL) {
        console.error("WebSocket URL not configured");
        appendMessage("SYSTEM", "Error: WebSocket URL not configured.");
        return;
    }
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        console.log("WebSocket connected");
        appendMessage("SYSTEM", "Connected. Ask about the weather or say “recall the weather record”.");
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
    const input = document.getElementById("user-input");
    if (input) {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }
});
