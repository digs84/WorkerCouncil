# Worker Council Assistant — Architecture Diagram

## System Architecture Overview

```mermaid
graph TB
    subgraph "End User Devices"
        A["📱 User Browser / Mobile App"]
        A1["📲 Installed as PWA"]
    end

    subgraph "Network"
        B["🌐 HTTPS"]
    end

    subgraph "Render.com (Free Tier)"
        C["🐳 Docker Container"]
        C1["⚙️ FastAPI Server<br/>(app/main.py)"]
        C2["🔄 LLM Router<br/>(app/llm_router.py)"]
        C3["📚 Retrieval Engine<br/>(app/retrieval.py)"]
        C4["🌍 Language Detector<br/>(app/i18n.py)"]
        C5["💾 Law Data<br/>(data/betrvg.json)"]
    end

    subgraph "Free LLM Providers (Failover)"
        D1["🚀 Groq API<br/>(30 req/min)"]
        D2["🔮 Google Gemini<br/>(Daily Quota)"]
        D3["🎲 OpenRouter<br/>(:free models)"]
    end

    subgraph "External Sources"
        E["📖 gesetze-im-internet.de<br/>(Official German Law)"]
    end

    A -->|User asks question| B
    A1 -->|Installed via| B
    B -->|HTTP/HTTPS| C
    
    C --> C1
    C1 -->|Orchestrates| C2
    C1 -->|Looks up sections| C3
    C1 -->|Detects language| C4
    
    C1 -->|Data| C5
    C3 -->|Searches| C5
    
    C1 -->|Hop 1| D1
    D1 -->|Rate limited?| D2
    D2 -->|Rate limited?| D3
    D3 -->|All exhausted?| C3
    C3 -->|Fallback: Keyword search| C5
    
    C1 -->|Returns answer| B
    B -->|JSON response| A
    
    E -.->|Historical reference| C5
    E -.->|Links in UI| A

    style A fill:#4ade80
    style A1 fill:#4ade80
    style C fill:#2563eb
    style D1 fill:#f59e0b
    style D2 fill:#f59e0b
    style D3 fill:#f59e0b
    style E fill:#8b5cf6
```

---

## Request/Response Flow

```mermaid
sequenceDiagram
    actor User
    participant App as PWA (index.html)
    participant API as FastAPI Backend
    participant Router as LLM Router
    participant Groq as Groq API
    participant Gemini as Gemini API
    participant Retrieval as Retrieval Engine

    User->>App: 🎙️ Asks question in German or English
    App->>API: POST /api/chat { question }
    
    API->>API: 🌍 Detect language (German or English?)
    
    API->>Retrieval: 1️⃣ Selector Phase: Find relevant § sections
    Retrieval->>API: Table of contents (BetrVG + BDSG)
    
    API->>Router: Call LLM #1: "Which sections are relevant?"
    Router->>Groq: Try Groq (fast, free tier)
    
    alt Groq Success
        Groq-->>Router: JSON [ {law: "BetrVG", section: "§87"}, ... ]
        Router-->>API: ✅ Got sections
    else Groq Rate Limited (429)
        Groq-->>Router: ❌ 429 Too Many Requests
        Router->>Gemini: Try Gemini (fallback)
        Gemini-->>Router: JSON array of sections
        Router-->>API: ✅ Gemini succeeded
    end
    
    API->>Retrieval: 2️⃣ Fetch full German text for those sections
    Retrieval-->>API: Full § text from data/betrvg.json
    
    API->>Router: Call LLM #2: "Answer the question (in same language as asked)"
    Router->>Groq: Try Groq
    Groq-->>Router: 📝 Full answer (German or English) + follow-ups
    Router-->>API: ✅ Answer received
    
    API->>API: Parse follow-ups, compute confidence, summarize sources
    API-->>App: { answer, sources, confidence, followups, metadata }
    
    App->>App: 💾 Cache recent question in LocalStorage
    App->>User: Display answer + source excerpt toggle + follow-up chips
    
    User->>App: 📎 Optional: Click "Source Excerpts"
    App->>App: Show official German text inline (already cached)
    
    User->>App: 🔗 Optional: Ask follow-up question
    App->>API: POST /api/chat { followup_question }
    API-->>App: (Same flow repeats)
```

---

## Data Flow: Question → Answer

```mermaid
graph LR
    A["User Question<br/>German or English"] --> B["Language Detect<br/>app/i18n.py"]
    
    B -->|German| C["Keep in German"]
    B -->|English| C
    
    C --> D["Selector Prompt<br/>to LLM"]
    D --> E["LLM Returns:<br/>- law name<br/>- § number"]
    
    E --> F["Retrieval Engine<br/>app/retrieval.py"]
    F --> G["Load from<br/>data/betrvg.json"]
    
    G --> H["Answerer Prompt<br/>to LLM<br/>+ Context"]
    H --> I["LLM Generates<br/>Answer<br/>in Same Language"]
    
    I --> J["Parse Metadata<br/>- Citations<br/>- Follow-ups<br/>- Confidence"]
    
    J --> K["Return to Frontend<br/>JSON Response"]
    K --> L["User Sees:<br/>- Answer Text<br/>- § Citations<br/>- Follow-ups<br/>- Source Toggle"]
    
    style A fill:#4ade80
    style B fill:#60a5fa
    style C fill:#60a5fa
    style D fill:#f59e0b
    style E fill:#f59e0b
    style F fill:#8b5cf6
    style G fill:#8b5cf6
    style H fill:#f59e0b
    style I fill:#f59e0b
    style J fill:#ec4899
    style K fill:#06b6d4
    style L fill:#4ade80
```

---

## Frontend Architecture (PWA)

```mermaid
graph TB
    A["index.html<br/>(Single-Page App)"]
    
    A --> B["Static Assets"]
    B --> B1["manifest.json<br/>(PWA metadata)"]
    B --> B2["sw.js<br/>(Service Worker)"]
    B --> B3["icons/"]
    B3 --> B3a["icon-192.png"]
    B3 --> B3b["icon-512.png"]
    B3 --> B3c["apple-touch-icon.png"]
    
    A --> C["JavaScript Logic"]
    C --> C1["Initialize App"]
    C --> C2["Register Service Worker"]
    C --> C3["Handle PWA Install Prompt"]
    C --> C4["Send Questions to /api/chat"]
    C --> C5["Display Answers + Metadata"]
    
    B2 --> D["Service Worker"]
    D --> D1["Cache Strategy"]
    D1 --> D1a["HTML: Network First"]
    D1 --> D1b["CSS/JS: Cache First"]
    D1 --> D1c["Images: Cache First"]
    
    D --> D2["Background Sync"]
    D2 --> D2a["Queue questions if offline"]
    D2 --> D2b["Sync when online"]
    
    D --> D3["Check for Updates"]
    D3 --> D3a["Call reg.update() on load"]
    D3 --> D3b["Refresh if new version"]
    
    A --> E["Local Storage"]
    E --> E1["Recent Questions"]
    E2["Device-local only"]
    E --> E1
    E --> E2
    
    A --> F["UI Components"]
    F --> F1["Hero Section<br/>(Landing Page)"]
    F --> F2["Chat Bubbles<br/>(User + Bot)"]
    F --> F3["Source Excerpt Toggle"]
    F --> F4["Follow-up Chips"]
    F --> F5["Recent Panel"]
    F --> F6["Sources Panel"]
    F --> F7["Install Banner"]
    
    style A fill:#4ade80
    style B fill:#60a5fa
    style C fill:#60a5fa
    style D fill:#f59e0b
    style E fill:#8b5cf6
    style F fill:#ec4899
```

---

## LLM Provider Failover Logic

```mermaid
graph TD
    A["Question arrives<br/>at /api/chat"] --> B["Read LLM_HOP_ORDER<br/>from .env or config.py"]
    
    B --> C["Load Hop List<br/>e.g., ['groq', 'gemini', 'openrouter']"]
    
    C --> D["Call Selector LLM<br/>(find relevant sections)"]
    
    D --> E{Try Hop #1:<br/>Groq}
    
    E -->|✅ Success| F["Return sections<br/>to backend"]
    E -->|❌ 429| G{Retry Count<br/>< 3?}
    E -->|❌ 401| H{API key<br/>valid?}
    E -->|❌ 500| I{Groq<br/>down?}
    
    G -->|Yes| E
    G -->|No| J["Move to Hop #2:<br/>Gemini"]
    
    H -->|No| K["Log error:<br/>Invalid API key"]
    H -->|Yes| J
    
    I -->|Likely| J
    
    J --> L{Try Hop #2:<br/>Gemini}
    L -->|✅ Success| F
    L -->|❌| M["Move to Hop #3:<br/>OpenRouter"]
    
    M --> N{Try Hop #3:<br/>OpenRouter}
    N -->|✅ Success| F
    N -->|❌| O["All hops exhausted"]
    
    O --> P["Fallback: Keyword Search<br/>app/retrieval.lexical_search"]
    P --> Q["Return keyword-matched<br/>sections to user"]
    
    Q --> R["🎯 Answer is ready"]
    
    style A fill:#4ade80
    style E fill:#f59e0b
    style L fill:#f59e0b
    style N fill:#f59e0b
    style O fill:#ef4444
    style P fill:#8b5cf6
    style R fill:#4ade80
```

---

## Deployment Pipeline

```mermaid
graph LR
    A["Local Git Repo"] -->|git push| B["GitHub"]
    
    B -->|Webhook Trigger| C["Render.com<br/>Detection"]
    
    C --> D["Read render.yaml"]
    D --> E["Build Docker Image"]
    E --> F["Install Python deps<br/>from Dockerfile"]
    F --> G["Copy app code"]
    G --> H["Start FastAPI server"]
    
    H --> I["🟢 Service Live<br/>on Public URL"]
    
    I --> J["Users visit URL"]
    J --> K["Download index.html"]
    K --> L["Download sw.js +<br/>other assets"]
    L --> M["💾 Service Worker<br/>caches everything"]
    
    M --> N["User clicks 'Install'"]
    N --> O["📱 App added to<br/>home screen / start menu"]
    
    O --> P["🚀 Users can now ask questions"]
    
    style A fill:#4ade80
    style B fill:#4ade80
    style C fill:#60a5fa
    style I fill:#10b981
    style P fill:#10b981
```

---

## Environment & Configuration

```mermaid
graph TB
    A[".env File (Local / Render)"]
    
    A --> B["API Keys"]
    B --> B1["GROQ_API_KEY"]
    B --> B2["GEMINI_API_KEY"]
    B --> B3["OPENROUTER_API_KEY"]
    
    A --> C["Hop Order"]
    C --> C1["LLM_HOP_ORDER='groq,gemini,openrouter'"]
    
    A --> D["Server Config"]
    D --> D1["HOST='0.0.0.0'"]
    D --> D2["PORT=8000"]
    
    A -.->|Loaded by| E["app/config.py"]
    E -.->|Used by| F["app/llm_router.py"]
    E -.->|Used by| G["app/main.py"]
    
    F --> H["Provider Registry"]
    H --> H1["Groq: https://api.groq.com/openai/v1"]
    H --> H2["Gemini: https://generativelanguage.googleapis.com/v1beta/openai"]
    H --> H3["OpenRouter: https://openrouter.ai/api/v1"]
    
    style A fill:#f59e0b
    style B fill:#60a5fa
    style C fill:#60a5fa
    style D fill:#60a5fa
    style H fill:#8b5cf6
```

---

## Module Dependencies

```mermaid
graph TD
    A["app/main.py<br/>(Orchestrator)"]
    
    A -->|imports| B["app/config.py<br/>(Provider Registry)"]
    A -->|imports| C["app/llm_router.py<br/>(Failover Routing)"]
    A -->|imports| D["app/retrieval.py<br/>(Law Text Lookup)"]
    A -->|imports| E["app/i18n.py<br/>(Language Detection)"]
    
    C -->|uses| B
    D -->|reads| F["data/betrvg.json<br/>(Law Sections)"]
    
    E -->|used by| A
    
    G["tests/test_llm_router.py"] -->|tests| C
    H["tests/test_retrieval.py"] -->|tests| D
    I["tests/test_i18n.py"] -->|tests| E
    
    J["app/static/index.html"] -->|calls| A
    K["app/static/sw.js"] -->|caches| J
    
    style A fill:#4ade80
    style B fill:#60a5fa
    style C fill:#f59e0b
    style D fill:#8b5cf6
    style E fill:#ec4899
    style F fill:#8b5cf6
    style J fill:#4ade80
```

---

## Bilingual Flow Example

```mermaid
graph LR
    A["User asks in GERMAN:<br/>'Wie wird ein Betriebsrat gewählt?'"] 
    
    B["detect_language() → 'de'"]
    C["Selector LLM: Find sections<br/>(prompt in German)"]
    D["Return: BetrVG §1, §8, §18, ..."]
    E["Retrieval: Fetch German text"]
    F["Answerer LLM:<br/>question + sections +<br/>ENFORCE: answer in German"]
    G["LLM Generates Answer<br/>entirely in German<br/>+ § citations"]
    H["Frontend shows:<br/>Answer in German"]
    
    A --> B --> C --> D --> E --> F --> G --> H
    
    I["User asks in ENGLISH:<br/>'How does the works<br/>council election work?'"]
    
    J["detect_language() → 'en'"]
    K["Selector LLM: Find sections<br/>(prompt in German, question in English)"]
    L["Return: BetrVG §1, §8, §18, ..."]
    M["Retrieval: Fetch German text"]
    N["Answerer LLM:<br/>question + sections +<br/>ENFORCE: answer in English"]
    O["LLM Generates Answer<br/>entirely in English<br/>+ § citations"]
    P["Frontend shows:<br/>Answer in English"]
    
    I --> J --> K --> L --> M --> N --> O --> P
    
    style H fill:#4ade80
    style P fill:#4ade80
```

---

## Cost Breakdown (Monthly)

```mermaid
graph TB
    A["💰 Total Monthly Cost"]
    
    A --> B["Compute: €0"]
    B --> B1["Render Free Tier"]
    B1 --> B1a["750 hours/month included"]
    B1 --> B1b["One service = 720 hrs needed"]
    
    A --> C["LLM API: €0"]
    C --> C1["Groq Free: 30 req/min"]
    C --> C2["Gemini Free: Daily quota"]
    C --> C3["OpenRouter Free: 20 req/min"]
    C --> C4["Auto-failover spreads load"]
    
    A --> D["Domain: €0"]
    D --> D1["*.onrender.com domain<br/>(included)"]
    
    A --> E["Data: €0"]
    E --> E1["No database costs"]
    E --> E2["Law data stored locally<br/>in JSON"]
    
    A --> F["Total: €0/month"]
    F --> F1["(Genuinely free)"]
    
    style A fill:#10b981
    style F fill:#10b981
    style F1 fill:#10b981
```

---

This comprehensive visual guide shows:
- **System architecture** (end-to-end)
- **Request/response flow** (sequence)
- **Data flow** (question to answer)
- **Frontend PWA structure**
- **LLM failover logic**
- **Deployment pipeline**
- **Configuration & dependencies**
- **Bilingual handling**
- **Cost model** (€0)

All diagrams are Mermaid-compatible and render in GitHub, markdown viewers, and documentation sites.
