# AP Invoice Triage + Coding Copilot — Prompter Script

**Word-for-word script for the presenter.** Read the lines in quotes; follow [ACTION] and [PAUSE] cues. Total runtime about 5 minutes.

---

## Setup (before audience joins)

- Open the app: local **http://localhost:8000/app** or deployed **{your-alb-url}/agent/app**.
- Ensure seed data is loaded so S3 path `invoices/INV-2026-001.txt` works.
- Have the app on the main screen; chat and right panel visible.

---

## SECTION 1 — Introduction (about 30 seconds)

**[SHOW: Full app — left side (inputs + chat) and right panel.]**

**READ:**

"This is our AP Invoice Triage and Coding Copilot."

[PAUSE 1 beat.]

"It takes an invoice—you can upload one, use a sample, or point to a path in S3—and it extracts the key fields, runs a 3-way match against the PO and receipt, and suggests GL coding with a policy-based rationale."

[PAUSE 1 beat.]

"If that suggestion is wrong, the user can correct the GL code right here in the chat, in plain English. No re-running triage, no editing JSON. Then they can export an ERP packet or draft an approval email. I'll walk through that now."

[PAUSE 1 beat.]

---

## SECTION 2 — Run AP triage (about 1–2 minutes)

**[SHOW: Triage inputs — file path, sample button, upload, Run AP triage button.]**

**READ:**

"On the left you have triage inputs. I can type an S3 path—for example invoices slash INV-2026-001 dot txt—or I can use the sample invoice, or upload my own. I'll run triage using the path that's already there."

[ACTION: Leave path as `invoices/INV-2026-001.txt` (or enter your seeded path). Do not click yet.]

"Now I click Run AP triage."

[ACTION: Click **Run AP triage**.]

**[SHOW: Status area and chat.]**

**READ:**

"You'll see a status message while it runs."

[PAUSE until status appears.]

"The agent runs a LangGraph workflow under the hood: it ingests the invoice, validates and matches against the PO and receipt, assigns GL coding using policy snippets, and finalizes the packet."

[PAUSE until the right panel updates and chat shows the agent reply.]

"When it's done, the right panel fills in—extracted invoice, PO match, receipt match—and here you see the coding and routing suggestions. The chat asks, 'Anything else to change?' The ERP export and Draft email buttons are now enabled."

**[SHOW: Right panel — extracted fields, PO match, receipt match, coding and routing.]**

---

## SECTION 3 — Show GL coding and rationale (about 30 seconds)

**[SHOW: Coding & routing section — Account, Cost center, Entity, Approval path, Rationale.]**

**READ:**

"The AI suggests an account code and cost center based on vendor defaults and policy. For example, IT spend under five thousand typically goes to GL six-one-zero-five; marketing might go to six-two-zero-zero. Cost center might be IT-one-hundred or MKT-three-hundred."

[PAUSE 1 beat.]

"The rationale here cites the actual policy—Policy four-point-one, four-point-two—so we have an audit trail for why this coding was chosen."

[PAUSE 1 beat.]

---

## SECTION 4 — Correct the GL code when the AI is wrong (about 1–2 minutes)

**[SHOW: Chat input at bottom of left panel.]**

**READ:**

"Now, if the suggested GL code isn't right—wrong account or wrong cost center—the user doesn't have to start over. They can correct it in plain English in the chat."

[PAUSE 1 beat.]

"I'll type: Change GL code to six-one-zero-zero."

[ACTION: In the chat input, type exactly: **Change GL code to 6100**]

"Send."

[ACTION: Click **Send** or press Enter.]

**[SHOW: Chat response and right panel refresh.]**

**READ:**

"The agent confirms: Updated GL code to six-one-zero-zero. The right panel refreshes—you can see the Account field now shows six-one-zero-zero. And in the rationale, there's a note that says 'User override: GL code changed to 6100,' so the override is auditable."

[PAUSE 1 beat.]

"They can do the same for cost center. For example: Change cost center to MKT-two-hundred."

[ACTION: Optional. Type: **Change cost center to MKT-200** and Send. Point to updated Cost center and rationale.]

**READ:**

"So even when the AI suggestion isn't right, the user corrects the GL code or cost center in one message. The system applies it to both the display and the export, and records it in the rationale."

[PAUSE 1 beat.]

---

## SECTION 5 — Export and draft email (about 30 seconds)

**[SHOW: ERP export and Draft email buttons on the right panel.]**

**READ:**

"Once the coding is correct—including any corrections—they can hit ERP export to download a JSON packet for their ERP."

[ACTION: Click **ERP export**. If a file downloads, briefly show or mention it.]

"That file has the current GL coding, including the override we just made."

[PAUSE 1 beat.]

"Draft email opens their mail client with a pre-filled subject and body that includes the same coding and approval path—again, with any corrections the user made. So downstream systems and approvers always see the right GL."

[ACTION: Optional. Click **Draft email** to show the pre-filled email.]

---

## Closing (optional, about 15 seconds)

**READ:**

"That's the AP Invoice Triage and Coding Copilot: extract, match, suggest GL coding with policy rationale, let the user correct the GL code when the AI is wrong, then export or draft the approval email. Any questions?"

---

## Cue summary

| When you see / do this | Say this (exact) |
|------------------------|------------------|
| Start of demo | "This is our AP Invoice Triage and Coding Copilot." |
| Before Run AP triage | "Now I click Run AP triage." |
| While triage runs | "The agent runs a LangGraph workflow under the hood: it ingests the invoice, validates and matches against the PO and receipt, assigns GL coding using policy snippets, and finalizes the packet." |
| Showing coding | "The rationale here cites the actual policy—Policy four-point-one, four-point-two—so we have an audit trail for why this coding was chosen." |
| Before GL correction | "If the suggested GL code isn't right—wrong account or wrong cost center—the user doesn't have to start over. They can correct it in plain English in the chat." |
| Typing override | "I'll type: Change GL code to six-one-zero-zero." then "Send." |
| After override | "So even when the AI suggestion isn't right, the user corrects the GL code or cost center in one message. The system applies it to both the display and the export, and records it in the rationale." |
| Export | "That file has the current GL coding, including the override we just made." |
| End | "That's the AP Invoice Triage and Coding Copilot: extract, match, suggest GL coding with policy rationale, let the user correct the GL code when the AI is wrong, then export or draft the approval email. Any questions?" |

---

## Alternate lines (if using sample or upload)

**If using sample invoice instead of S3 path:**

- After "I'll run triage using the path that's already there" say instead: "I'll use the sample invoice instead." [Click **Use sample invoice**, then] "Now I click Run AP triage."

**If using upload:**

- After "or upload my own" say: "I've uploaded an invoice here." [Show file selected.] "Now I click Run AP triage."

---

## Troubleshooting (do not read aloud)

- **Not connected:** Refresh; check WebSocket URL.
- **Triage fails:** Confirm S3 path exists and seed script was run.
- **Override not applied:** Run triage first; type a clear phrase (e.g. "change GL code to 6100"); ensure last result is still in the right panel.

---

*Prompter script for AP Invoice Triage + Coding Copilot. Word-for-word for presenter; emphasizes user correction of GL code when the AI suggestion is not right.*
