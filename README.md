# RescueMesh

### Autonomous food rescue coordination with Strands Agents and Amazon Bedrock AgentCore

[![Live Demo](https://img.shields.io/badge/Live_Demo-RescueMesh-2E7D5B)](https://18-213-41-214.nip.io)
![AWS](https://img.shields.io/badge/AWS-AgentCore-orange)
![Strands Agents](https://img.shields.io/badge/Agents-Strands-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**RescueMesh** is an autonomous food-rescue coordination system that turns surplus food into an executable rescue operation.

It connects **food donors, volunteer drivers, community pantries, and rescue operators**, then coordinates the workflow from donation intake through planning, dispatch, delivery, disruption recovery, and verified pantry receipt.

Unlike a chatbot that only recommends what people should do, RescueMesh performs real operational coordination while keeping critical logistics decisions deterministic and escalating to a human when automation should stop.

**Donation → AI coordination → deterministic planning → dispatch → delivery → verified receipt**

Built for the **AWS Agents for Humans Hackathon — Good Neighbor Agents** track.

🌐 **Live Demo:**  
https://18-213-41-214.nip.io

---

## What Is RescueMesh?

RescueMesh acts as the coordination layer between donors, volunteer drivers, food pantries, and rescue operators.

When surplus food becomes available, RescueMesh can:

- inspect the donation and current rescue network;
- determine whether a feasible rescue exists;
- allocate food according to pantry need and capacity;
- assign available volunteer drivers;
- optimize delivery routes;
- track pickup and delivery;
- recover automatically from safe disruptions;
- escalate genuine tradeoffs to a human;
- require independent pantry confirmation before completion.

The goal is not simply to generate advice.

The goal is to **coordinate the rescue itself**.

---

## Why RescueMesh?

Food rescue is not just a matching problem. It is a **real-time coordination problem**.

When surplus food becomes available, someone has to quickly determine:

- Which pantry currently needs it?
- How much can each pantry accept?
- Which volunteer driver is available?
- Does the driver have enough vehicle capacity?
- Can pickup happen before the deadline?
- Can the route finish within the driver's shift?
- What happens if a driver cancels?
- What happens if a pantry becomes unavailable?
- When should the system replan automatically?
- When should a human make the decision?

RescueMesh turns these interconnected decisions into a **stateful, end-to-end rescue workflow**.

---

## Key Features

| Feature | What RescueMesh Does |
|---|---|
| 🤖 **Autonomous Coordination** | A Strands agent inspects state, selects tools, and coordinates the rescue workflow |
| 🚚 **Driver & Pantry Matching** | Matches available drivers and pantries using need, capacity, timing, and feasibility |
| 🗺️ **Deterministic Logistics** | Uses PuLP, OR-Tools, and OpenRouteService instead of asking an LLM to calculate logistics |
| 🔄 **Disruption Recovery** | Replans when drivers or pantries become unavailable |
| 🧑‍💼 **Human-in-the-Loop** | Escalates when no clearly safe deterministic alternative exists |
| ✅ **Verified Delivery** | Requires independent pantry confirmation after the driver reports delivery |
| 📋 **Persistent Operations** | Stores routes, stops, events, and escalations outside the LLM conversation |
| 📊 **Evaluation** | Includes automated tests and reproducible randomized logistics benchmarks |

---

## Live Demo

🌐 **https://18-213-41-214.nip.io**

The application includes six views:

- **Donor** — create a surplus-food donation
- **Driver Dispatch** — view assignments, destinations, quantities, and ETAs
- **Pantry** — review inbound food and confirm receipt
- **Operations** — inspect rescue status, events, and escalations
- **Impact & Evaluation** — view measured system results
- **Live Rescue Demo** — follow a rescue through its lifecycle

### Recommended Demo

Create this donation from the **Donor** page:

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

RescueMesh may select different drivers or pantry combinations depending on the current network state. Follow the rescue plan the system actually generates.

> Demo controls represent events that would normally come from a driver's phone, SMS link, or lightweight mobile application. They still use the real RescueMesh backend workflow.

---

## How It Works

A normal RescueMesh operation follows this lifecycle:

```text
Donation Created
      ↓
Inspect Donation + Network
      ↓
Generate Rescue Plan
      ↓
Allocate Food + Assign Driver
      ↓
Optimize Route
      ↓
Driver Accepts
      ↓
Pickup
      ↓
Delivery
      ↓
Pantry Confirms Receipt
      ↓
Rescue Completed
```

When conditions change:

```text
Disruption
    ↓
Updated Network State
    ↓
Deterministic Replanning
    ↓
┌───────────────────────┬───────────────────────┐
│ Safe alternative      │ No safe alternative   │
▼                       ▼
Automatic recovery      Human review
```

---

# Architecture

> **LLMs orchestrate. Deterministic algorithms optimize.**

RescueMesh separates **AI coordination**, **deterministic logistics**, **persistent operational state**, and **real-world event handling**.

The AI agent determines **what action should happen next**.

Deterministic systems determine **whether and how that action can be executed safely**.

```mermaid
flowchart TB

    USERS["👥 Donors • Drivers • Pantries • Operators"]

    subgraph APP["AWS EC2 — RescueMesh Application"]
        WEB["🔒 Nginx + HTTPS<br/>Streamlit Web App"]
        API["⚡ FastAPI Backend<br/>Restricted Agent API"]
        EVENTS["📋 Rescue Event Processing<br/>Driver • Pantry • Disruptions"]
        STATE[("🗄️ SQLite Operational State<br/>Operations • Routes • Stops • Events")]
    end

    subgraph AI["Amazon Bedrock AgentCore — AI Coordination"]
        RUNTIME["☁️ AgentCore Runtime"]
        AGENT["🤖 Strands RescueCoordinator"]
        MODEL["🧠 Amazon Bedrock<br/>Claude Haiku 4.5"]
        TOOLS["🛠️ Restricted Remote Tools"]

        RUNTIME --> AGENT
        AGENT <--> MODEL
        AGENT --> TOOLS
    end

    subgraph LOGISTICS["Deterministic Logistics Engine"]
        PLANNER["🎯 Rescue Planner"]
        PULP["📦 PuLP<br/>Food Allocation"]
        ROUTE["🗺️ OR-Tools<br/>Route Optimization"]
        ORS["🌐 OpenRouteService<br/>Travel Times"]

        PLANNER --> PULP
        PLANNER --> ROUTE
        ROUTE --> ORS
    end

    HUMAN["🧑‍💼 Human Review"]

    %% USER ENTRY
    USERS -->|"HTTPS"| WEB

    %% AI COORDINATION PATH
    WEB -->|"New donation<br/>IAM-authorized invocation"| RUNTIME
    TOOLS -->|"Authenticated HTTPS"| API
    API -->|"Planning request"| PLANNER
    API <--> STATE

    %% REAL-WORLD EVENT PATH
    WEB -->|"Driver / pantry actions"| EVENTS
    EVENTS <--> STATE

    %% DISRUPTION RECOVERY
    EVENTS -->|"Disruption → replan"| PLANNER
    EVENTS -->|"No safe alternative"| HUMAN
    HUMAN -->|"Human decision"| EVENTS
```

### Architecture at a Glance

**Application.** RescueMesh runs as a **Streamlit application on AWS EC2** behind **Nginx + HTTPS**. FastAPI exposes restricted endpoints used by the remote agent tools, while SQLite stores persistent rescue state.

**AI coordination.** A new donation can invoke **Amazon Bedrock AgentCore Runtime** using an IAM-authorized call. Inside AgentCore, the **Strands RescueCoordinator** uses **Amazon Bedrock Claude Haiku 4.5** for reasoning and selects from a restricted set of RescueMesh tools.

**Deterministic logistics.** The LLM does not calculate quantities, routes, capacities, or ETAs. **PuLP** handles food allocation, **Google OR-Tools** optimizes delivery routes, and **OpenRouteService** provides road-network travel times.

**Safety boundary.** Driver acceptance, pickup, delivery, pantry confirmation, and human approval are real-world events and cannot be fabricated by the AI agent. When a disruption has no clearly safe deterministic alternative, RescueMesh escalates to a human.

---

### Two Execution Paths

RescueMesh intentionally separates AI coordination from physical-world event processing.

#### 1. AI Coordination Path

Used when a donation needs autonomous coordination:

```text
Donation Created
       ↓
Streamlit on AWS EC2
       ↓
Amazon Bedrock AgentCore Runtime
       ↓
Strands RescueCoordinator
       ↕
Amazon Bedrock
       ↓
Restricted RescueMesh Tools
       ↓
Authenticated FastAPI
       ↓
Deterministic Rescue Planner
       ↓
Persistent Rescue Operation
```

The agent can inspect state, select tools, request planning, monitor operations, and inspect escalations.

The deterministic planner remains responsible for logistics feasibility.

#### 2. Real-World Event Path

Used for driver and pantry actions:

```text
Driver / Pantry
      ↓
Streamlit
      ↓
Rescue Event Processing
      ↓
Operational State
      ↓
Continue Rescue
      │
      ├── disruption → deterministic replan
      │
      └── no safe alternative → human review
```

The agent cannot fabricate:

```text
Driver acceptance
Food pickup
Food delivery
Pantry confirmation
Human approval
```

For example:

```text
Driver reports delivery
        ↓
Stop = driver_delivered
        ↓
Pantry independently confirms receipt
        ↓
Stop = completed
```

This separation allows RescueMesh to use AI for flexible coordination while keeping logistics calculations and physical-world state transitions deterministic and verifiable.

---

## Evaluation

RescueMesh was evaluated using automated tests and reproducible randomized logistics scenarios.

### Automated Testing

**53 automated tests passing**

```bash
pytest tests/ -q
```

The test suite covers planning constraints, capacity handling, driver availability, shifts, deadlines, routing, disruption recovery, and workflow state.

### Randomized Planning Benchmark

Using `seed=42`, RescueMesh was evaluated on **50 randomized planning scenarios**.

| Metric | Result |
|---|---:|
| Planning scenarios | **50** |
| Rescue plans generated | **46 / 50 (92%)** |
| Fully rescued scenarios | **46 / 50 (92%)** |
| Safely rejected infeasible scenarios | **4 / 50 (8%)** |
| Safety compliance among generated plans | **46 / 46 (100%)** |
| Weighted food rescued | **89.62%** |
| Capacity violations | **0** |
| Average planning latency | **6.42 s** |
| P95 planning latency | **6.63 s** |

Every generated rescue plan passed the benchmark's independent safety checks.

When no feasible rescue existed, RescueMesh safely rejected the scenario rather than producing an invalid plan.

### Disruption Recovery

The benchmark also simulated **10 in-transit pantry-closure disruptions**.

| Metric | Result |
|---|---:|
| Disruption scenarios | **10** |
| Autonomous recoveries | **10 / 10 (100%)** |
| Unsafe autonomous recoveries | **0** |
| Average recovery latency | **0.79 s** |

> The 100% recovery result applies specifically to the tested in-transit pantry-closure scenarios and should not be interpreted as a 100% recovery rate for every possible disruption type.

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

| Layer | Technology |
|---|---|
| Agent Framework | Strands Agents SDK |
| Agent Runtime | Amazon Bedrock AgentCore |
| Foundation Model | Amazon Bedrock / Claude Haiku 4.5 |
| Frontend | Streamlit |
| Backend | FastAPI |
| Food Allocation | PuLP |
| Route Optimization | Google OR-Tools |
| Travel-Time Data | OpenRouteService |
| Operational State | SQLite |
| Hosting | Amazon EC2 |
| Authorization | AWS IAM |
| Reverse Proxy | Nginx |
| HTTPS | Let's Encrypt |
| Language | Python |

---

## Prerequisites

For local development:

- **Python 3.10+**
- an **OpenRouteService API key**
- AWS credentials with **Amazon Bedrock access** when using the local Strands coordinator
- an **AgentCore Runtime ARN** and permission to invoke it when testing the deployed AgentCore path

---

## Run Locally

Clone the repository:

```bash
git clone https://github.com/maithili74/rescuemesh.git
cd rescuemesh
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Configure `.env`:

```env
ORS_API_KEY=

RESCUEMESH_INTERNAL_API_KEY=

RESCUEMESH_BACKEND_URL=http://127.0.0.1:8000

AGENTCORE_RUNTIME_ARN=

AWS_REGION=us-east-1

AGENTCORE_QUALIFIER=DEFAULT
```

Never commit real credentials or API keys.

### Start FastAPI

```bash
uvicorn app.api.main:app \
  --host 127.0.0.1 \
  --port 8000
```

### Start Streamlit

In another terminal:

```bash
streamlit run app/dashboard/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

For AgentCore-backed execution, the AWS environment must have permission to invoke the configured runtime.

Without `AGENTCORE_RUNTIME_ARN`, RescueMesh can use the local Strands coordinator during development.

---

## Repository Structure

```text
rescuemesh/
├── app/
│   ├── agent/          # Strands + AgentCore integration
│   ├── api/            # FastAPI backend
│   ├── dashboard/      # Streamlit application
│   ├── services/       # Planning and routing services
│   └── tools/          # Agent tools
│
├── deploy/
│   └── agentcore/      # AgentCore deployment package
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
- SQLite rather than a distributed production database;
- web-based driver and pantry interfaces rather than production mobile applications;
- OpenRouteService for external routing data.

A production deployment would add stronger identity management, authentication, observability, monitoring, fault tolerance, and multi-user infrastructure.

---

## License

RescueMesh is licensed under the **MIT License**.

See [LICENSE](LICENSE).