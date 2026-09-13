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
- allocate food to pantries with matching need and capacity;
- assign available volunteer drivers;
- optimize delivery routes;
- track the rescue through pickup and delivery;
- recover automatically from safe disruptions;
- escalate difficult tradeoffs to a human;
- require independent pantry confirmation before completion.

The goal is not simply to generate advice.

The goal is to **coordinate the rescue itself**.

---

## Why RescueMesh?

Food rescue is not just a matching problem. It is a **real-time coordination problem**.

When food becomes available, someone has to quickly answer:

- Which pantry currently needs it?
- How much can the pantry accept?
- Which volunteer driver is available?
- Does that driver have enough capacity?
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
| 🚚 **Driver & Pantry Matching** | Matches available drivers with pantries based on need, capacity, timing, and feasibility |
| 🗺️ **Deterministic Logistics** | Uses PuLP, OR-Tools, and OpenRouteService instead of asking an LLM to calculate routes |
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
- **Pantry** — confirm received food
- **Operations** — inspect rescue status, events, and escalations
- **Impact & Evaluation** — view system results
- **Live Rescue Demo** — follow the rescue lifecycle through guided events

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

A normal rescue follows this lifecycle:

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

If something changes during the rescue:

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

RescueMesh deliberately separates **AI coordination** from **real-world event processing**.

The AI agent determines **what action should happen next**.

Deterministic systems determine **whether and how the rescue can actually happen safely**.

```mermaid
flowchart TB

    USERS["👥 Donors • Drivers • Pantries • Operators"]

    subgraph APP["AWS EC2 — RescueMesh Application"]
        WEB["🔒 Nginx + HTTPS<br/>Streamlit Web App"]
        EVENTS["📋 Rescue Event Processing"]
        API["⚡ FastAPI Agent API"]
        STATE[("🗄️ SQLite<br/>Operational State")]
    end

    subgraph AI["Amazon Bedrock AgentCore — AI Coordination"]
        AGENT["🤖 Strands RescueCoordinator"]
        MODEL["🧠 Amazon Bedrock<br/>Claude Haiku 4.5"]
        TOOLS["🛠️ Restricted Remote Tools"]

        AGENT <--> MODEL
        AGENT --> TOOLS
    end

    subgraph PLAN["Deterministic Logistics Engine"]
        PLANNER["🎯 Rescue Planner"]
        PULP["📦 PuLP<br/>Food Allocation"]
        ROUTE["🗺️ OR-Tools<br/>Route Optimization"]
        ORS["🌐 OpenRouteService<br/>Travel Times"]

        PLANNER --> PULP
        PLANNER --> ROUTE
        ROUTE --> ORS
    end

    HUMAN["🧑‍💼 Human Review"]

    USERS -->|"HTTPS"| WEB

    %% AI COORDINATION PATH
    WEB -->|"New donation<br/>IAM-authorized invocation"| AGENT
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

**1. Application layer**

RescueMesh runs as a **Streamlit application on AWS EC2**, exposed through **Nginx over HTTPS**.

The application provides the donor, driver, pantry, operations, evaluation, and demo interfaces.

---

**2. AI coordination path**

When a donor creates a new donation, the EC2 application invokes the deployed **Amazon Bedrock AgentCore Runtime**.

Inside AgentCore, the **Strands RescueCoordinator** uses Amazon Bedrock for reasoning and selects from a restricted set of RescueMesh tools.

```text
Donation
   ↓
Streamlit
   ↓
Amazon Bedrock AgentCore
   ↓
Strands RescueCoordinator
   ↕
Amazon Bedrock
   ↓
Restricted RescueMesh Tools
```

The agent coordinates the workflow, but it does not calculate logistics itself.

---

**3. Restricted agent tools**

The AgentCore-hosted coordinator can safely:

```text
Inspect donation
Inspect network state
Plan rescue
Inspect operation
Inspect operation events
Inspect pending escalations
Inspect escalation
```

These tools communicate with the **FastAPI Agent API over authenticated HTTPS**.

The AI agent is intentionally not given unrestricted backend access.

---

**4. Deterministic logistics**

Critical logistics decisions are calculated outside the LLM.

| Component | Responsibility |
|---|---|
| **PuLP** | Allocate donated food across eligible pantries |
| **Google OR-Tools** | Build feasible volunteer-driver delivery routes |
| **OpenRouteService** | Provide road-network travel times |

The planner evaluates constraints such as:

- pantry need and capacity;
- driver availability and capacity;
- driver shifts;
- pickup deadlines;
- delivery feasibility.

The language model does **not** invent quantities, capacities, routes, or ETAs.

---

**5. Persistent operational state**

RescueMesh stores its operational state in **SQLite**, including:

```text
Donations
Drivers
Pantries
Pantry needs
Operations
Driver routes
Delivery stops
Events
Escalations
```

A rescue therefore exists independently of the LLM conversation.

---

**6. Real-world event path**

Driver and pantry actions deliberately bypass the AI agent.

```text
Driver / Pantry
      ↓
Streamlit
      ↓
Rescue Event Processing
      ↓
Operational State
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

This provides two-sided delivery verification.

---

**7. Disruption recovery**

When a real-world disruption occurs, RescueMesh uses the updated state to run deterministic replanning.

```text
Disruption
    ↓
Updated Operational State
    ↓
Deterministic Replanning
    ↓
┌───────────────────────┬───────────────────────┐
│ Safe alternative      │ No safe alternative   │
▼                       ▼
Automatic recovery      Human review
```

The agent can coordinate recovery, but logistics feasibility remains deterministic and consequential tradeoffs remain under human control.

---

## Two Execution Paths

RescueMesh intentionally uses two separate execution paths.

### AI Coordination Path

Used when a donation needs agentic coordination:

```text
Donation
   ↓
Streamlit on AWS EC2
   ↓
Amazon Bedrock AgentCore
   ↓
Strands RescueCoordinator
   ↕
Amazon Bedrock
   ↓
Restricted Remote Tools
   ↓
Authenticated FastAPI
   ↓
Deterministic Rescue Planner
   ↓
Persistent Rescue Operation
```

### Real-World Event Path

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

This separation lets RescueMesh use AI for flexible coordination while keeping physical-world state transitions deterministic and verifiable.

---

## Evaluation

RescueMesh was evaluated using automated tests and reproducible randomized logistics scenarios.

### Automated Testing

**53 automated tests passing**

```bash
pytest tests/ -q
```

The test suite covers planning constraints, capacity, driver availability, deadlines, routing, disruption recovery, and workflow state.

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
| Average planning latency | **6.42 s** |
| P95 planning latency | **6.63 s** |

All generated plans passed the benchmark's independent safety checks.

When no feasible rescue existed, RescueMesh safely rejected the scenario rather than producing an invalid plan.

### Disruption Recovery

The benchmark also simulated **10 in-transit pantry closures**.

| Metric | Result |
|---|---:|
| Disruption scenarios | **10** |
| Autonomous recoveries | **10 / 10 (100%)** |
| Unsafe autonomous recoveries | **0** |
| Average recovery latency | **0.79 s** |

The recovery result applies specifically to the tested pantry-closure scenarios and should not be interpreted as a 100% recovery rate for every possible disruption type.

### Reproduce the Benchmark

```bash
python evaluation/randomized_benchmark.py \
  --planning 50 \
  --disruptions 10 \
  --seed 42
```

Detailed benchmark outputs are available in:

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

## Run Locally

```bash
git clone https://github.com/maithili74/rescuemesh.git
cd rescuemesh

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

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
│   ├── api/            # FastAPI agent API
│   ├── dashboard/      # Streamlit application
│   ├── services/       # Planning and routing
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
- OpenRouteService for routing data.

A production deployment would add stronger identity management, observability, fault tolerance, monitoring, and multi-user infrastructure.

---

## License

RescueMesh is licensed under the **MIT License**.

See [LICENSE](LICENSE).