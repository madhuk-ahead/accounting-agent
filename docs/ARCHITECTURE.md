# AP Invoice Triage + Coding Copilot — Architecture

## 1. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Client["Client"]
        Browser["Browser"]
    end

    subgraph AWS["AWS Cloud"]
        subgraph Frontend["Frontend"]
            ECS["ECS Fargate"]
            ALB["ALB"]
        end

        subgraph WebSocket["API Gateway WebSocket"]
            Connect["$connect"]
            Disconnect["$disconnect"]
            Default["$default (chat)"]
        end

        subgraph Lambdas["Lambda Functions"]
            LambdaConnect["connect"]
            LambdaDisconnect["disconnect"]
            LambdaChat["chat"]
        end

        subgraph Data["Data Stores"]
            DynamoDB[("DynamoDB")]
            S3[("S3")]
            Secrets[("Secrets Manager")]
        end

        subgraph External["External"]
            OpenAI["OpenAI API"]
        end
    end

    Browser -->|"HTTP /app"| ALB
    ALB --> ECS
    Browser -->|"WebSocket wss://"| WebSocket
    WebSocket --> LambdaConnect
    WebSocket --> LambdaDisconnect
    WebSocket --> LambdaChat
    LambdaChat --> DynamoDB
    LambdaChat --> S3
    LambdaChat --> Secrets
    LambdaChat --> OpenAI
    LambdaConnect --> DynamoDB
    LambdaDisconnect --> DynamoDB
```

## 2. Infrastructure Component Detail

```mermaid
flowchart LR
    subgraph Compute["Compute"]
        ECS["ECS Fargate\nFastAPI + static\n1 CPU, 2 GB RAM"]
    end

    subgraph Networking["Networking"]
        VPC["VPC"]
        ALB["ALB :80\nPath prefix: /agent"]
        ECR["ECR"]
    end

    subgraph APIGW["API Gateway WebSocket"]
        Routes["Routes:\n$connect, $disconnect\n$default (chat)"]
    end

    subgraph LambdaStack["Lambda Stack"]
        L1["connect\n(session create)"]
        L2["disconnect\n(cleanup)"]
        L3["chat\n(LangGraph orchestrator\n512 MB, 300s)"]
    end

    subgraph Storage["Storage"]
        D1[("sessions")]
        D2[("vendor_master")]
        D3[("po_ledger")]
        D4[("receipts")]
        D5[("invoice_status")]
        S3_Prefixes["S3 prefixes:\ninvoices/\npolicies/\noutputs/"]
    end

    ECS --> ALB
    VPC --> ECS
    VPC --> ALB
    ECR -.->|"Image"| ECS
    APIGW --> L1
    APIGW --> L2
    APIGW --> L3
    L1 --> D1
    L2 --> D1
    L3 --> D1
    L3 --> D2
    L3 --> D3
    L3 --> D4
    L3 --> D5
    L3 --> S3_Prefixes
```

## 3. LangGraph Workflow (AP Orchestrator)

```mermaid
flowchart LR
    subgraph Workflow["AP Invoice Triage Workflow"]
        START((START))
        INGEST["ingest\n(Extract invoice fields\nvia LLM or mock)"]
        VALIDATE["validate_and_match\n(3-way match: Invoice/PO/Receipt\nDuplicate check)"]
        ASSIGN["assign_coding\n(GL coding with policy snippets)"]
        ROUTER{"router"}
        HANDLE["handle_exceptions\n(Exception handling)"]
        FINALIZE["finalize_packet\n(Generate ERP packet,\napproval artifacts)"]
        END((END))

        START --> INGEST
        INGEST --> VALIDATE
        VALIDATE --> ASSIGN
        ASSIGN --> ROUTER
        ROUTER -->|"has exceptions"| HANDLE
        ROUTER -->|"no exceptions"| FINALIZE
        HANDLE --> END
        FINALIZE --> END
    end
```

## 4. Application Layer Stack

```mermaid
flowchart TB
    subgraph FrontendLayer["Frontend Layer"]
        FastAPI["FastAPI app"]
        Jinja["Jinja templates"]
        Static["Static JS/CSS"]
    end

    subgraph CoreLayer["Core Layer"]
        Agent["AgentManager"]
        Config["Config (get_settings)"]
        State["APInvoiceState"]
        Tools["ap_invoice_tools"]
    end

    subgraph OrchestratorLayer["Orchestrator Layer"]
        Graph["ap_graph (LangGraph)"]
        Orchestrator["ap_invoice_orchestrator"]
        Factory["orchestrator_factory"]
    end

    subgraph LambdaLayer["Lambda Layer"]
        ConnectHandler["connect.py"]
        DisconnectHandler["disconnect.py"]
        ChatHandler["chat.py"]
    end

    FastAPI --> Agent
    Agent --> Orchestrator
    Orchestrator --> Graph
    Graph --> Tools
    Graph --> State
    ChatHandler --> Agent
    Factory --> Orchestrator
```

## 5. Data Flow (Chat Message Path)

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend
    participant APIGW as API Gateway
    participant Lambda as Lambda (chat)
    participant Agent as AgentManager
    participant Graph as LangGraph
    participant DynamoDB
    participant S3
    participant OpenAI

    Browser->>APIGW: WebSocket message (text, form_data)
    APIGW->>Lambda: Invoke with connection_id
    Lambda->>DynamoDB: Get session_id from connection_id
    Lambda->>Agent: run(conversation_id, user_text, form_data)
    Agent->>Graph: Execute workflow
    Graph->>S3: Read invoice, policies
    Graph->>DynamoDB: Read Vendors, POs, Receipts, InvoiceStatus
    Graph->>OpenAI: Extract / code (LLM)
    Graph-->>Agent: State + artifacts
    Agent-->>Lambda: Result (message, buttons, file_content)
    Lambda->>APIGW: post_to_connection (stream + final)
    APIGW->>Browser: WebSocket response
```

## 6. Local Development vs Production

```mermaid
flowchart TB
    subgraph Local["Local Development"]
        LocalBrowser["Browser :8000"]
        LocalFastAPI["uvicorn app.main"]
        LocalWS["/ws (direct WebSocket)"]
        LocalAgent["AgentManager"]
    end

    subgraph Prod["Production"]
        ProdBrowser["Browser"]
        ProdALB["ALB"]
        ProdECS["ECS (FastAPI)"]
        ProdAPIGW["API Gateway WebSocket"]
        ProdLambda["Lambda (chat)"]
        ProdAgent["AgentManager"]
    end

    LocalBrowser --> LocalFastAPI
    LocalBrowser --> LocalWS
    LocalWS --> LocalAgent

    ProdBrowser --> ProdALB
    ProdALB --> ProdECS
    ProdBrowser --> ProdAPIGW
    ProdAPIGW --> ProdLambda
    ProdLambda --> ProdAgent
```

---

## Key Configuration

| Variable | Purpose |
|----------|---------|
| `ORCHESTRATOR_TYPE` | `ap` or `langraph` (both use LangGraph workflow) |
| `AGENT_WS_URL` | WebSocket URL for frontend (prod: API Gateway; local: ws://localhost:8000/ws) |
| `S3_AP_BUCKET` | S3 bucket for invoices/, policies/, outputs/ |
| `OPENAI_API_KEY` | From env (local) or Secrets Manager (Lambda) |
