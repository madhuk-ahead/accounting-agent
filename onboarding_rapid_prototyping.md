# Onboarding Walkthrough: Rapid Agent Prototyping (Template → Customize → Deploy)

This document is the **standard onboarding walkthrough** for projects where we rapidly prototype new agents by **migrating/updating an existing codebase** and **deploying to AWS** using the **existing orchestrator + infrastructure**.

> **Key constraints (confirmed):**
> - **Shared AWS account** (everyone deploys into the same account)
> - **Remote Terraform state** exists, but you can ignore the implementation details for now
> - **Keep everything in the VPC**
> - Deploy targets: **ECS Fargate + Lambda** (as defined in the template repo)
> - **Toy data only** stored in **DynamoDB + S3**
> - Each person creates their **own branch** of the template repo and builds their **own agent**

---

## Useful repos

### Primary repos
- Empty Agent Template (starting point):  
  https://github.com/kb-ahead/empty_agent_template.git
- Whiteboarding Agent (reference UX/demo patterns):  
  https://github.com/kb-ahead/whiteboarding_agent
- Shared infra patterns (reference):  
  https://github.com/kb-ahead/aheadailabs-infra.git

### Other related repos
- Data Auto Engineer:  
  https://github.com/RevoTeshaAH/data_auto_engineer.git
- SecUnit Agent:  
  https://github.com/kb-ahead/secunit_agent.git

### Project plan references (examples)
- Social Video Content Creation Agent Project Plan - Nick
- Contact Center Agent-Assist — Credit Policy Content Creation
- Drop-Ship Vendor Item Setup Copilot
- Customer Service for Logistics Agent
- Returns_Classifier_Agent
- Press Release Drafting Assistant

---

## What you’ll receive before kickoff

1. **AWS credentials** will be shared with you via chat prior to kickoff.
2. You will have access to:
   - the **template repo**
   - the **whiteboarding agent repo**
3. The Whiteboarding Agent is also accessible via:  
   https://aheadailabs.com/

---

## Golden workflow (do this for every new agent)

### Step 0 — Local prerequisites
Ensure you have:
- Git
- Docker (build/test container locally)
- Terraform
- AWS CLI
- A coding assistant (Cursor recommended but optional)

Validate AWS CLI is authenticated:
- `aws sts get-caller-identity`

> You will need to be signed into AWS CLI before any Terraform deploys.

---

### Step 1 — Clone the template repo and create your branch
1. Clone:
   - `empty_agent_template`
2. Create a **unique branch**:
   - Example: `user/<name>/<agent-name>` (e.g., `user/kurt/press-release-agent`)

**Why:** multiple people deploy into the **same AWS account**, so you need isolation via code branches + unique resource names.

---

### Step 2 — Define your agent “vibe” + scope (10 minutes)
Write a short agent spec (keep it simple):

- **Agent name**
- **Vibe / tone** (e.g., formal, playful, concise, etc.)
- **What it does** (3–5 bullets)
- **Inputs** (text/images/form)
- **Outputs** (required structure, citations, next action)
- **Tools** it needs
- **Toy data** needs (what goes in DynamoDB + S3)

> Recommendation: Use **toy/dummy data only** in DynamoDB + S3 so the demo is safe, repeatable, and deterministic.

---

### Step 3 — Talk to your coding assistant (Cursor or other)
Tell your coding assistant:

1. You want to **update the agent in this repo** to match the **vibe** and **spec**.
2. It should update:
   - **prompt structure**
   - the **tool(s)** the agent can call
   - the toy **DynamoDB + S3** data interfaces
3. **Before it writes a plan**, the assistant should ask you questions to close knowledge gaps.
4. Then it must write a step-by-step plan using this loop **for every step**:
   - **Investigate → Plan → Execute → Test → Clean up → Move on**

**Important:** keep the agent **inside the VPC** and avoid external calls. Use only toy data in DynamoDB and S3.

---

### Step 4 — Terraform uniqueness (avoid collisions in a shared account)
Because everyone deploys into a **shared AWS account**, your Terraform must use **unique names**.

Your assistant must:
- audit Terraform variables and resource names
- add or enforce a required `name_prefix` (or equivalent)
- ensure uniqueness across:
  - S3 bucket names
  - DynamoDB table names
  - ECS services / task definitions
  - Lambda functions
  - IAM roles/policies
  - CloudWatch log groups
  - ALB / target groups (if used)
  - API Gateway resources (if used)

**Recommended convention:**
- `name_prefix = "<owner>-<agent>-<env>"`  
  Example: `kboden-pressrelease-dev`

> Remote state exists, but **you can ignore details** here—just ensure **all names are unique**.

---

### Step 5 — Implement (prompts, tools, and toy data)
Typical change areas:

#### 5.1 Prompts
- system prompt (persona/vibe)
- task prompt templates
- formatting requirements (structured output, citations, next action)
- tool invocation instructions

#### 5.2 Tools (toy data only)
- tools should read from:
  - DynamoDB (structured records)
  - S3 (documents, JSON, PDFs, images)
- tools should return:
  - content + **source metadata** for citations
  - stable identifiers (`source_id`, `title`, `timestamp`, etc.)

#### 5.3 Seed toy data
- small DynamoDB seed set (10–50 items)
- small S3 seed set (3–20 files)
- include a reset/seed mechanism so demos are repeatable

---

### Step 6 — Deploy (Terraform)
High-level flow:
1. `terraform init`
2. `terraform plan` (verify names are unique)
3. `terraform apply`

Validate:
- service is healthy
- web UI is reachable
- agent produces expected structured output
- citations/sources show correctly
- demo is repeatable (seed/reset works)

> The template repo contains the authoritative deployment details for ECS Fargate + Lambda. Follow that repo’s instructions precisely.

---

## Demo + publishing expectations
For now, the goal is:
- everyone creates their own branch
- deploys their own agent into AWS
- verifies it is accessible via web

Later (optional), these agents can be routed through a CloudFront gateway to expose them on **aheadailabs.com**.

---

## Team norms (speed + safety)
- **Toy data only** (DynamoDB + S3)
- Keep runtime and dependencies **inside the VPC**
- No secrets committed to Git
- Build for **repeatable demos** (seed/reset)
- Use the standard assistant loop:
  - Investigate → Plan → Execute → Test → Clean up → Move on

---

## Troubleshooting (common)
- **Terraform collision / “already exists”**
  - Prefix not unique enough, or not applied everywhere.
- **Works locally but fails in AWS**
  - Missing env vars, IAM permissions, VPC endpoint assumptions, or container image mismatch.
- **No citations**
  - Tool outputs must include source metadata, and prompts must require citations.

---

## Appendix: Copy/paste “agent spec” template

**Agent name:**  
**Vibe / tone:**  
**Goal (1 sentence):**  
**Primary capabilities (3–5 bullets):**  
**Inputs:** (text/images/form)  
**Outputs:** (structured fields + citations + recommended next action)  
**Tools:** (list tools + Dynamo/S3 paths used)  
**Toy data model:** (Dynamo tables + S3 prefixes)  
**Demo scenario:** (happy path + 1 edge case)  
**Non-goals:**  

