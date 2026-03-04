// AP Invoice Triage + Coding Copilot – WebSocket chat client

let ws = null;
let transcript = "";
let currentFileContent = "";
let currentDisplayData = null;
let uploadedInvoiceBase64 = null;
let uploadedInvoiceType = null;
let uploadedInvoicePagesBase64 = null;
let uploadedInvoicePreviewUrl = null;
let lastSelectedPdfFile = null;
let lastSelectedFile = null;  // File object for upload (PDF or image)

function initWebSocket() {
    if (!WS_URL) {
        console.error("WebSocket URL not configured");
        appendMessage("SYSTEM", "Error: WebSocket URL not configured.");
        return;
    }
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        console.log("WebSocket connected");
        appendMessage("SYSTEM", "Connected. Upload an invoice and run AP triage.");
    };
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === "status") {
                document.getElementById("status-area").textContent = msg.content || "";
            } else if (msg.type === "step") {
                let step = {};
                try {
                    step = typeof msg.content === "string" ? JSON.parse(msg.content) : (msg.content || {});
                } catch (_) { step = {}; }
                appendLiveTriageStep(step);
            } else if (msg.type === "final") {
                document.getElementById("status-area").textContent = "";
                const hasLiveSteps = document.getElementById("live-triage-steps");
                if (msg.reasoning_stages && msg.reasoning_stages.length > 0 && !hasLiveSteps) {
                    appendReasoningStages(msg.reasoning_stages);
                } else if (msg.content && !hasLiveSteps) {
                    appendMessage("AGENT", msg.content || "");
                    transcript += "\nAGENT: " + (msg.content || "");
                }
                if (msg.confirmation_prompt) {
                    appendMessage("AGENT", msg.confirmation_prompt);
                    transcript += "\nAGENT: " + msg.confirmation_prompt;
                }
                if (msg.file_content) currentFileContent = msg.file_content;
                if (msg.display_data) currentDisplayData = msg.display_data;
                if (msg.display_data || msg.file_content) {
                    const preview = document.getElementById("file-preview");
                    preview.innerHTML = msg.display_data
                        ? renderDisplayData(msg.display_data)
                        : "<pre class='json-preview'>" + escapeHtml(msg.file_content || "") + "</pre>";
                    preview.classList.add("has-content");
                    const erpBtn = document.getElementById("erp-export-btn");
                    const draftBtn = document.getElementById("draft-email-btn");
                    if (erpBtn) erpBtn.disabled = false;
                    if (draftBtn) draftBtn.disabled = false;
                    if (msg.display_data) updateExtractionOverlay(msg.display_data);
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

function convertPdfToImageForExtraction(file) {
    return new Promise(function (resolve, reject) {
        if (typeof pdfjsLib === "undefined") {
            uploadedInvoiceBase64 = null;
            uploadedInvoiceType = null;
            uploadedInvoicePagesBase64 = null;
            console.warn("PDF.js not loaded; PDF extraction may fail.");
            resolve(false);
            return;
        }
        const fileReader = new FileReader();
        fileReader.onload = function () {
            const typedArray = new Uint8Array(fileReader.result);
            const loadTask = pdfjsLib.getDocument({ data: typedArray });
            (loadTask.promise || loadTask).then(function (pdf) {
                const numPages = pdf.numPages;
                const pagePromises = [];
                for (let i = 1; i <= numPages; i++) {
                    pagePromises.push(pdf.getPage(i));
                }
                return Promise.all(pagePromises);
            }).then(function (pages) {
                const renderPromises = pages.map(function (page) {
                    const scale = 2;
                    const viewport = page.getViewport({ scale: scale });
                    const canvas = document.createElement("canvas");
                    canvas.width = viewport.width;
                    canvas.height = viewport.height;
                    const ctx = canvas.getContext("2d");
                    const renderTask = page.render({ canvasContext: ctx, viewport: viewport });
                    const renderPromise = renderTask.promise || renderTask;
                    return renderPromise.then(function () {
                        return new Promise(function (res) {
                            canvas.toBlob(function (blob) {
                                if (!blob) { res(null); return; }
                                const r = new FileReader();
                                r.onload = function () {
                                    const dataUrl = r.result;
                                    if (typeof dataUrl === "string" && dataUrl.startsWith("data:")) {
                                        const p = dataUrl.split(",");
                                        res(p.length === 2 ? p[1] : null);
                                    } else { res(null); }
                                };
                                r.readAsDataURL(blob);
                            }, "image/png");
                        });
                    });
                });
                return Promise.all(renderPromises);
            }).then(function (base64Pages) {
                const valid = (base64Pages || []).filter(Boolean);
                if (valid.length === 0) {
                    resolve(false);
                    return;
                }
                uploadedInvoicePagesBase64 = valid;
                if (valid.length === 1) {
                    uploadedInvoiceBase64 = valid[0];
                    uploadedInvoiceType = "image/png";
                } else {
                    uploadedInvoiceBase64 = null;
                    uploadedInvoiceType = null;
                }
                resolve(true);
            }).catch(function (err) {
                console.error("PDF to image conversion failed:", err);
                uploadedInvoiceBase64 = null;
                uploadedInvoiceType = null;
                uploadedInvoicePagesBase64 = null;
                reject(err);
            });
        };
        fileReader.onerror = function () { reject(new Error("Failed to read PDF file")); };
        fileReader.readAsArrayBuffer(file);
    });
}

function updateExtractionOverlay(d) {
    const container = document.querySelector(".invoice-with-overlay");
    if (!container) return;
    const overlay = document.getElementById("extraction-overlay");
    if (!overlay || !d || !d.extracted_invoice) return;
    const inv = d.extracted_invoice || {};
    const fmt = (v) => v == null || v === "" ? "—" : String(v);
    overlay.innerHTML = `
        <div class="extract-zone zone-vendor" title="Vendor: ${escapeHtml(fmt(inv.vendor_name))}"><span class="zone-label">Vendor</span></div>
        <div class="extract-zone zone-invoice-no" title="Invoice #: ${escapeHtml(fmt(inv.invoice_no))}"><span class="zone-label">Invoice #</span></div>
        <div class="extract-zone zone-date" title="Date: ${escapeHtml(fmt(inv.invoice_date))}"><span class="zone-label">Date</span></div>
        <div class="extract-zone zone-line-items" title="Line items"><span class="zone-label">Line items</span></div>
        <div class="extract-zone zone-amount" title="Amount: $${Number(inv.amount || 0).toLocaleString()}"><span class="zone-label">Amount</span></div>
    `;
    overlay.classList.add("visible");
}

function clearRightPanelOutput() {
    const preview = document.getElementById("file-preview");
    const erpBtn = document.getElementById("erp-export-btn");
    const draftBtn = document.getElementById("draft-email-btn");
    if (preview) {
        preview.innerHTML = "<p class='placeholder-text'>Upload an invoice or run triage to see: extracted fields, PO match, receipt match, coding & routing with rationale.</p>";
        preview.classList.remove("has-content");
    }
    if (erpBtn) erpBtn.disabled = true;
    if (draftBtn) draftBtn.disabled = true;
    currentFileContent = "";
    currentDisplayData = null;
    const overlay = document.getElementById("extraction-overlay");
    if (overlay) overlay.classList.remove("visible");
}

function handleInvoiceUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (uploadedInvoicePreviewUrl) URL.revokeObjectURL(uploadedInvoicePreviewUrl);
    uploadedInvoiceBase64 = null;
    uploadedInvoiceType = null;
    uploadedInvoicePagesBase64 = null;
    uploadedInvoicePreviewUrl = null;
    lastSelectedPdfFile = null;
    lastSelectedFile = file;

    clearRightPanelOutput();

    const reader = new FileReader();
    reader.onload = () => {
        const result = reader.result;
        if (result && typeof result === "string" && result.startsWith("data:")) {
            const parts = result.split(",");
            if (parts.length === 2 && file.type !== "application/pdf") {
                uploadedInvoiceBase64 = parts[1];
                const mime = parts[0].match(/data:([^;]+)/);
                uploadedInvoiceType = mime ? mime[1] : file.type;
            }
        }
    };
    if (file.type !== "application/pdf") {
        reader.readAsDataURL(file);
    }

    if (file.type.startsWith("image/")) {
        uploadedInvoicePreviewUrl = URL.createObjectURL(file);
        const el = document.getElementById("invoice-preview");
        el.innerHTML = '<div class="invoice-with-overlay"><img src="' + uploadedInvoicePreviewUrl + '" alt="Uploaded invoice" class="invoice-image" /><div id="extraction-overlay" class="extraction-overlay"></div></div>';
        el.classList.add("has-content");
    } else if (file.type === "application/pdf") {
        lastSelectedPdfFile = file;
        uploadedInvoicePreviewUrl = URL.createObjectURL(file);
        const el = document.getElementById("invoice-preview");
        el.innerHTML = '<div class="invoice-with-overlay"><embed src="' + uploadedInvoicePreviewUrl + '" type="application/pdf" class="invoice-pdf" /><div id="extraction-overlay" class="extraction-overlay"></div></div>';
        el.classList.add("has-content");
    } else {
        reader.readAsDataURL(file);
    }
}

function getFormData() {
    const filePath = (document.getElementById("file-path")?.value || "invoices/INV-2026-001.txt").trim();
    const data = {
        file_path: filePath || "invoices/INV-2026-001.txt",
    };
    if (uploadedInvoicePagesBase64 && uploadedInvoicePagesBase64.length > 0) {
        data.invoice_pages_base64 = uploadedInvoicePagesBase64;
    } else if (uploadedInvoiceBase64 && uploadedInvoiceType) {
        data.invoice_file_base64 = uploadedInvoiceBase64;
        data.invoice_file_type = uploadedInvoiceType;
    }
    return data;
}

async function runTriage() {
    const triageBtn = document.getElementById("triage-btn");
    const origLabel = triageBtn ? triageBtn.textContent : "";
    let formData = getFormData();

    // When user has uploaded a file, upload to S3 first (avoids WebSocket payload limits)
    if (lastSelectedFile && typeof UPLOAD_URL !== "undefined" && UPLOAD_URL) {
        if (triageBtn) {
            triageBtn.disabled = true;
            triageBtn.textContent = "Uploading...";
        }
        try {
            const fd = new FormData();
            fd.append("invoice", lastSelectedFile);
            const resp = await fetch(UPLOAD_URL, { method: "POST", body: fd });
            const json = await resp.json();
            if (triageBtn) triageBtn.textContent = "Running AP triage...";
            if (json.error || !json.file_path) {
                appendMessage("SYSTEM", "Upload failed: " + (json.error || "Unknown error"));
                if (triageBtn) { triageBtn.disabled = false; triageBtn.textContent = origLabel; }
                return;
            }
            formData = { file_path: json.file_path };
        } catch (e) {
            appendMessage("SYSTEM", "Upload failed: " + (e && e.message ? e.message : ""));
            if (triageBtn) { triageBtn.disabled = false; triageBtn.textContent = origLabel; }
            return;
        }
    }

    if (triageBtn) triageBtn.textContent = origLabel;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        appendMessage("SYSTEM", "Not connected. Refresh the page to reconnect.");
        scrollChatIntoView();
        return;
    }
    const statusEl = document.getElementById("status-area");
    if (statusEl) statusEl.textContent = "Running AP triage...";

    clearRightPanelOutput();

    const hasUpload = (formData.invoice_pages_base64 && formData.invoice_pages_base64.length > 0) ||
        (formData.invoice_file_base64 && formData.invoice_file_type) ||
        (formData.file_path && formData.file_path.startsWith("invoices/uploads/"));
    const text = hasUpload
        ? "Run AP triage for uploaded invoice"
        : "Run AP triage for " + formData.file_path;
    transcript += "\nUSER: " + text;
    appendMessage("USER", text);

    const filename = lastSelectedFile?.name || (formData.file_path ? formData.file_path.split("/").pop() : null) || "invoice";
    appendTriageRunningMessage(filename);

    formData.invoice_filename = filename;
    ws.send(JSON.stringify({
        action: "message",
        text: text,
        conversation: transcript,
        form_data: formData,
    }));
    document.getElementById("triage-btn").disabled = true;
    setTimeout(() => { document.getElementById("triage-btn").disabled = false; }, 2000);
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
    const payload = { action: "message", text: text, conversation: transcript };
    if (currentDisplayData) payload.last_display_data = currentDisplayData;
    if (currentFileContent) payload.last_file_content = currentFileContent;
    ws.send(JSON.stringify(payload));
    appendMessage("USER", text);
    input.value = "";
}

function downloadPacket() {
    if (!currentFileContent) return;
    const blob = new Blob([currentFileContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "erp_export.json";
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

function appendTriageRunningMessage(filename) {
    const el = document.getElementById("chat-messages");
    if (!el) return;
    const wrap = document.createElement("div");
    wrap.className = "message agent reasoning-stages triage-running";
    wrap.innerHTML = "<span class='label'>AGENT</span> <p class='triage-intro'>Triage agent is running for <strong>" + escapeHtml(filename) + "</strong>.</p><div id='live-triage-steps' class='stages-list'></div>";
    el.appendChild(wrap);
    el.scrollTop = el.scrollHeight;
}

function appendReasoningStages(stages) {
    const el = document.getElementById("chat-messages");
    if (!el) return;
    const wrap = document.createElement("div");
    wrap.className = "message agent reasoning-stages";
    let html = "<span class='label'>AGENT</span> <div class='stages-list'>";
    for (const s of stages) {
        html += "<div class='stage-item'><span class='stage-step'>" + escapeHtml(String(s.step || "")) + "</span><span class='stage-label'>" + escapeHtml(s.label || "") + "</span><span class='stage-detail'>" + escapeHtml(s.detail || "") + "</span></div>";
    }
    html += "</div>";
    wrap.innerHTML = html;
    el.appendChild(wrap);
    el.scrollTop = el.scrollHeight;
}

function appendLiveTriageStep(step) {
    const container = document.getElementById("live-triage-steps");
    if (!container) return;
    const div = document.createElement("div");
    div.className = "stage-item";
    div.innerHTML = "<span class='stage-step'>" + escapeHtml(String(step.step || "")) + "</span><span class='stage-label'>" + escapeHtml(step.label || "") + "</span><span class='stage-detail'>" + escapeHtml(step.detail || "") + "</span>";
    container.appendChild(div);
    const chatEl = document.getElementById("chat-messages");
    if (chatEl) chatEl.scrollTop = chatEl.scrollHeight;
}

function escapeHtml(s) {
    if (s == null || s === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
}

function renderDisplayData(d) {
    if (!d) return "";
    const inv = d.extracted_invoice || {};
    const po = d.po_match || {};
    const rec = d.receipt_match || {};
    const gl = d.coding_and_routing || {};
    const flags = d.flags || [];

    const fmt = (v) => v == null || v === "" ? "—" : String(v);
    const lineCount = (inv.line_items || []).length;

    const poTick = po.found ? "✓" : "✗";
    const recTick = rec.received ? "✓" : "✗";
    const poId = escapeHtml(fmt(po.po_id));
    const recId = escapeHtml(fmt(rec.receipt_id));
    const recDate = escapeHtml(fmt(rec.received_date));
    const flagsStr = flags.length ? flags.map((f) => escapeHtml(f)).join(", ") : "None";

    return `
        <div class="display-row display-row-extracted">
            <span class="row-label">Extracted:</span>
            <span>${escapeHtml(fmt(inv.vendor_name))}</span>
            <span class="sep">|</span>
            <span>#${escapeHtml(fmt(inv.invoice_no))}</span>
            <span class="sep">|</span>
            <span>${escapeHtml(fmt(inv.invoice_date))}</span>
            <span class="sep">|</span>
            <span>$${Number(inv.amount || 0).toLocaleString()} ${escapeHtml(inv.currency || "")}</span>
            <span class="sep">|</span>
            <span>${lineCount} line items</span>
        </div>
        <div class="display-row display-row-ticks">
            <span class="row-label">Match:</span>
            <span class="tick ${po.found ? "tick-ok" : "tick-fail"}">PO ${poTick}</span>
            <span>${poId}</span>
            <span class="sep">|</span>
            <span class="tick ${rec.received ? "tick-ok" : "tick-fail"}">Receipt ${recTick}</span>
            <span>${recId}</span>
            <span>${recDate}</span>
            <span class="sep">|</span>
            <span class="flags ${flags.length ? "flags-warn" : ""}">Red flags: ${flagsStr}</span>
        </div>
        <div class="display-section display-section-coding highlighted">
            <h3>Coding & routing suggestions</h3>
            <div class="coding-grid">
                <p><strong>Account:</strong> ${escapeHtml(fmt(gl.account_code))}</p>
                <p><strong>Cost center:</strong> ${escapeHtml(fmt(gl.cost_center))}</p>
                <p><strong>Entity:</strong> ${escapeHtml(fmt(gl.entity))}</p>
                <p><strong>Approval path:</strong> ${escapeHtml(fmt(gl.approval_path))}</p>
            </div>
            <p class="coding-next"><strong>Next actions:</strong> ${Array.isArray(gl.next_actions) ? escapeHtml(gl.next_actions.join(" → ")) : "—"}</p>
            <p class="coding-rationale"><strong>Rationale:</strong> ${escapeHtml(fmt(gl.rationale))}</p>
        </div>
    `;
}

function draftEmailForApproval() {
    if (!currentFileContent) return;
    try {
        const data = JSON.parse(currentFileContent);
        const inv = data.invoice || {};
        const gl = data.gl_coding || {};
        const subject = encodeURIComponent(`Invoice ${inv.invoice_no || "pending"} – approval request`);
        const body = encodeURIComponent(
            `Please approve the following invoice for payment.\n\n` +
            `Vendor: ${inv.vendor_name || "N/A"}\n` +
            `Invoice #: ${inv.invoice_no || "N/A"}\n` +
            `Amount: $${Number(inv.amount || 0).toLocaleString()}\n\n` +
            `GL coding: ${gl.account_code || "N/A"} / ${gl.cost_center || "N/A"}\n` +
            `Approval path: ${gl.approval_path || "N/A"}\n`
        );
        window.open("mailto:?subject=" + subject + "&body=" + body);
    } catch (e) {
        window.open("mailto:?subject=Invoice%20approval%20request&body=Please%20review%20the%20attached%20invoice.");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    document.getElementById("invoice-file")?.addEventListener("change", handleInvoiceUpload);
    document.getElementById("triage-btn")?.addEventListener("click", runTriage);
    document.getElementById("erp-export-btn")?.addEventListener("click", downloadPacket);
    document.getElementById("draft-email-btn")?.addEventListener("click", draftEmailForApproval);
    const input = document.getElementById("user-input");
    if (input) {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }
});
