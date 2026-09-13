# RescueMesh

### Autonomous food rescue coordination with Strands Agents and Amazon Bedrock AgentCore

[![Live Demo](https://img.shields.io/badge/Live_Demo-RescueMesh-2E7D5B)](https://18-213-41-214.nip.io)
![AWS](https://img.shields.io/badge/AWS-AgentCore-orange)
![Strands Agents](https://img.shields.io/badge/Agents-Strands-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**RescueMesh** is an autonomous food-rescue coordination system that turns a surplus-food donation into an executable rescue operation.

It matches real-time pantry demand with available volunteer drivers, optimizes food allocation and delivery routes, tracks the rescue through pickup and verified delivery, and automatically replans when disruptions occur.

Unlike a chatbot that only recommends what people should do, RescueMesh coordinates the actual workflow across **donors, drivers, pantries, and operators** while preserving deterministic safety constraints and escalating to a human when no clearly safe option exists.

**Donation → AI coordination → deterministic planning → driver dispatch → delivery → pantry verification**

Built for the **AWS Agents for Humans Hackathon — Good Neighbor Agents** track to demonstrate an AI agent that performs real operational work for a real community need.

🌐 **Live Demo:**  
https://18-213-41-214.nip.io

---

## Try RescueMesh

The fastest way to understand RescueMesh is to run one complete rescue through the live application.

### Recommended Demo

Open the **Donor** page and create:

```text
Donor: Community Bakery
Food: Prepared Food
Quantity: 50 lbs
Available: 11:00
Pickup deadline: 14:00
```

Click:

**Create Donation & Start Rescue**

Then follow:

```text
Donor
  ↓
Driver Dispatch
  ↓
Live Rescue Demo
  ↓
Pantry Confirmation
  ↓
Operations
  ↓
Impact & Evaluation
```

During the rescue:

1. RescueMesh automatically creates the rescue plan.
2. **Driver Dispatch** shows the assigned driver, destinations, quantities, and ETAs.
3. **Live Rescue Demo** guides the driver through acceptance, pickup, and delivery.
4. **Pantry** independently confirms that food was actually received.
5. **Operations** shows the completed rescue and event history.
6. **Impact & Evaluation** shows measured system results.

The optimizer may choose different drivers or pantry combinations depending on the current network state. Always follow the plan RescueMesh actually generates.

> The Live Rescue Demo simulates events that would normally come from a driver's phone, SMS link, or lightweight mobile application. The events still use the real RescueMesh backend workflow.

---

## Why RescueMesh?

Food rescue is a coordination problem.

When surplus food becomes available, someone has to quickly determine:

- Which pantry needs this food?
- How much can it accept?
- Which volunteer driver is available?
- Does the driver have enough capacity?
- Can pickup happen before the deadline?
- Can deliveries finish within the driver's shift?
- What happens if a driver cancels?
- What happens if a pantry becomes unavailable?
- When should the system automatically replan?
- When should automation stop and ask a human?

RescueMesh combines an AI coordination agent with deterministic logistics optimization to make these decisions safely.

---

## How It Works

```text
Donor creates donation
        ↓
Strands RescueCoordinator
        ↓
Inspect donation + network state
        ↓
Deterministic logistics optimizer
        ↓
Assign pantry + driver + route
        ↓
Driver accepts and picks up food
        ↓
Driver reports delivery
        ↓
Pantry independently confirms receipt
        ↓
Rescue completed
```

If something changes during the rescue, RescueMesh evaluates the updated state and attempts a safe replan.

```text
Disruption
    ↓
Inspect latest network state
    ↓
Is a safe deterministic alternative available?
    ↓
 ┌───────────────┴───────────────┐
 YES                             NO
  ↓                               ↓
Re-optimize                Human escalation
  ↓
Continue rescue
```

If there is no clearly safe alternative, the system pauses instead of allowing the LLM to guess.

---

## Key Features

### 🤖 Autonomous Rescue Planning

A donor submission automatically triggers the Strands-based RescueCoordinator to inspect the donation and current network state and request a deterministic rescue plan.

### 🚚 Driver & Pantry Matching

RescueMesh allocates food to pantries with matching need and available capacity and assigns available volunteer drivers.

### 🗺️ Deterministic Logistics Optimization

**PuLP**, **Google OR-Tools**, and **OpenRouteService** handle allocation, routing, and road-network travel times.

### 🔄 Disruption Recovery

Driver failures, pantry closures, and capacity changes can trigger automatic replanning using the latest network state.

### 🧑 Human-in-the-Loop Safety

When RescueMesh cannot find a clearly safe deterministic alternative, it transitions the rescue to human review instead of allowing the AI agent to invent a decision.

### ✅ Two-Sided Delivery Verification

A driver reporting a delivery is not enough to complete a rescue.

The receiving pantry must independently confirm:

**Confirm Food Received**

Only then is the delivery considered verified.

### 📜 Persistent Operations and Events

RescueMesh stores donations, rescue operations, routes, delivery stops, events, and escalations as persistent state rather than keeping the workflow inside an LLM conversation.

---

# Architecture

> **LLMs orchestrate. Deterministic algorithms optimize.**

The language model coordinates the workflow, selects tools, and reasons about state.

It does **not** invent:

- food quantities;
- driver capacity;
- pantry capacity;
- routes;
- travel times;
- ETAs;
- physical delivery events.

Those values come from deterministic systems and persisted operational state.

```mermaid
flowchart TD

    USERS["Donor • Driver • Pantry • Operator"]

    subgraph EC2["AWS EC2 — RescueMesh Application"]
        NGINX["Nginx<br/>HTTPS Reverse Proxy"]
        UI["Streamlit Web Application"]
        APP["Dashboard / Application Services"]
        CLIENT["AgentCore Client<br/>boto3"]
        API["FastAPI Agent API"]
        EVENTS["Event Processor"]
        DB[("SQLite<br/>Donations • Operations • Routes<br/>Events • Escalations")]
        PLANNER["Deterministic Rescue Planner"]
    end

    subgraph AGENTCORE["Amazon Bedrock AgentCore Runtime"]
        AGENT["Strands RescueCoordinator"]
        MODEL["Amazon Bedrock<br/>Claude Haiku 4.5"]
        TOOLS["Remote RescueMesh Tools"]

        AGENT <--> MODEL
        AGENT --> TOOLS
    end

    subgraph OPT["Optimization Services"]
        PULP["PuLP<br/>Food Allocation"]
        ORTOOLS["Google OR-Tools<br/>Route Optimization"]
        ORS["OpenRouteService<br/>Travel-Time Matrix"]
    end

    USERS -->|"HTTPS"| NGINX
    NGINX -->|"/"| UI
    UI --> APP

    APP -->|"Create donation + coordinate"| CLIENT
    CLIENT -->|"IAM: InvokeAgentRuntime"| AGENT

    TOOLS -->|"Authenticated HTTPS /api"| NGINX
    NGINX -->|"/api/"| API

    API --> PLANNER
    API <--> DB

    PLANNER --> PULP
    PLANNER --> ORTOOLS
    ORTOOLS --> ORS

    APP -->|"Driver / pantry actions"| EVENTS
    EVENTS <--> DB
    EVENTS -->|"Safe disruption replan"| PLANNER
    EVENTS -->|"No safe deterministic option"| HUMAN["Human Escalation"]
```

### Agentic Coordination

The `RescueCoordinator` is built with the **Strands Agents SDK** and deployed to **Amazon Bedrock AgentCore Runtime**.

The deployed coordinator can safely:

```text
inspect donation
inspect network state
plan rescue
inspect operation
inspect operation events
inspect pending escalations
inspect escalation
```

AgentCore calls these tools through the authenticated RescueMesh FastAPI API.

### Deterministic Logistics

The logistics layer handles calculations that should not depend on language-model guesses:

- **PuLP** — food allocation
- **Google OR-Tools** — driver route construction
- **OpenRouteService** — road travel-time matrix

### Safety Boundary

The AgentCore tool set intentionally does **not** include tools that pretend a real-world event happened.

The agent cannot fabricate:

```text
driver accepted assignment
food picked up
food delivered
pantry confirmed receipt
human approved escalation
```

Those state changes must come through the corresponding RescueMesh workflow.

---

## AWS Deployment

The live application uses:

- **Amazon EC2** — application hosting
- **Amazon Bedrock AgentCore Runtime** — deployed Strands coordinator
- **Amazon Bedrock** — LLM inference
- **AWS IAM** — EC2 → AgentCore authorization
- **Nginx** — HTTPS reverse proxy
- **Let's Encrypt** — TLS
- **systemd** — persistent Streamlit and FastAPI services

On EC2:

```text
127.0.0.1:8501 → Streamlit
127.0.0.1:8000 → FastAPI
```

Nginx exposes:

```text
/      → Streamlit
/api/  → FastAPI
```

The live coordination path is:

```text
Browser
  ↓
Streamlit on EC2
  ↓
EC2 IAM Role
  ↓
Amazon Bedrock AgentCore
  ↓
Strands RescueCoordinator
  ↓
Amazon Bedrock
  ↓
Remote RescueMesh Tools
  ↓
HTTPS FastAPI
  ↓
Deterministic Optimizer
  ↓
Persistent Rescue Operation
```

---

## Evaluation

RescueMesh was evaluated using automated tests and reproducible randomized logistics scenarios.

### Automated Tests

The project currently has:

**53 passing automated tests**

```bash
pytest tests/ -q
```

The tests cover:

- planning constraints;
- driver availability;
- capacity limits;
- deadlines;
- routing behavior;
- disruption recovery;
- operation state;
- workflow transitions.

### Randomized Logistics Benchmark

Using a reproducible benchmark with `seed=42`, RescueMesh was evaluated on **50 randomized planning scenarios**.

| Metric | Result |
|---|---:|
| Randomized planning scenarios | 50 |
| Rescue plans generated | 46 / 50 (92%) |
| Fully rescued scenarios | 46 / 50 (92%) |
| Safely rejected infeasible scenarios | 4 / 50 (8%) |
| Safety compliance among generated plans | 46 / 46 (100%) |
| Weighted food rescued | 89.62% |
| Unsafe plans | 0 |
| Capacity violations | 0 |
| Driver double-booking violations | 0 |
| Driver shift violations | 0 |
| Pickup deadline violations | 0 |
| Average planning latency | 6.42 s |
| P95 planning latency | 6.63 s |

All generated rescue plans passed the benchmark's independent safety checks.

When a randomized scenario had no feasible rescue, RescueMesh safely rejected it instead of producing an invalid plan.

### Disruption Recovery Benchmark

The benchmark also simulated **10 in-transit pantry-closure disruptions**.

| Metric | Result |
|---|---:|
| Disruption scenarios | 10 |
| Autonomous recoveries | 10 / 10 (100%) |
| Unsafe autonomous recoveries | 0 |
| Average disruption recovery latency | 0.79 s |

The 100% recovery result applies specifically to the tested in-transit pantry-closure scenarios and should not be interpreted as a 100% recovery rate for every possible disruption type.

### Reproduce the Benchmark

```bash
python evaluation/randomized_benchmark.py \
  --planning 50 \
  --disruptions 10 \
  --seed 42
```

Detailed outputs are stored in:

```text
evaluation/results/
├── planning_scenarios.csv
├── disruption_scenarios.csv
├── benchmark_summary.json
└── benchmark_summary.md
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Agent Framework | Strands Agents SDK |
| Agent Runtime | Amazon Bedrock AgentCore |
| Foundation Model | Amazon Bedrock / Claude Haiku 4.5 |
| Frontend | Streamlit |
| Backend | FastAPI |
| Food Allocation | PuLP |
| Route Optimization | Google OR-Tools |
| Travel Times | OpenRouteService |
| Operational State | SQLite |
| Hosting | Amazon EC2 |
| Authorization | AWS IAM |
| Reverse Proxy | Nginx |
| HTTPS | Let's Encrypt |
| Language | Python |

---

## Run Locally

Clone the repository:

```bash
git clone https://github.com/maithili74/rescuemesh.git
cd rescuemesh
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Configure the required values:

```env
ORS_API_KEY=

RESCUEMESH_INTERNAL_API_KEY=

RESCUEMESH_BACKEND_URL=http://127.0.0.1:8000

AGENTCORE_RUNTIME_ARN=

AWS_REGION=us-east-1

AGENTCORE_QUALIFIER=DEFAULT
```

Never commit real secrets.

### Start the Backend

```bash
uvicorn app.api.main:app \
  --host 127.0.0.1 \
  --port 8000
```

### Start the Frontend

In another terminal:

```bash
streamlit run app/dashboard/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

For the deployed AgentCore path, the calling AWS environment must have permission to invoke the configured AgentCore runtime.

Without `AGENTCORE_RUNTIME_ARN`, RescueMesh can use the local Strands coordinator during development.

---

## Repository Structure

```text
rescuemesh/
│
├── app/
│   ├── agent/            # Strands + AgentCore integration
│   ├── api/              # FastAPI agent API
│   ├── dashboard/        # Streamlit application
│   ├── services/         # Planning and routing services
│   └── tools/            # Agent tools
│
├── deploy/
│   └── agentcore/        # Lightweight AgentCore deployment package
│
├── evaluation/
│   ├── randomized_benchmark.py
│   └── results/
│
├── scripts/
├── tests/
│
├── .env.example
├── LICENSE
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Limitations

RescueMesh is a hackathon prototype.

The current implementation uses:

- simulated donors, pantries, and volunteer drivers;
- SQLite instead of a distributed production database;
- web-based driver and pantry interfaces rather than production mobile applications;
- OpenRouteService for external routing data.

A production deployment would add stronger identity management, authentication, observability, monitoring, fault tolerance, and multi-user infrastructure.

---

## License

RescueMesh is licensed under the **MIT License**.

See [LICENSE](LICENSE).