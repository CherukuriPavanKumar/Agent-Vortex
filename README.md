# Agent Vortex

Agent Vortex is a personal AI operating system built with LangGraph, PostgreSQL, MCP servers, and modern LLM tooling.

It combines:

* Browser Automation
* WhatsApp Automation
* Gmail Integration
* Google Calendar Integration
* Long-Term Memory
* File Generation (PDF & Excel)
* Human Approval Workflows
* Persistent Conversations

into a single agent workflow.

---

# Features

## Core Agent

* LangGraph-based architecture
* Planner → Risk → Approval → Executor workflow
* Tool calling
* Persistent conversations
* Conversation titles
* Long-term memory
* Short-term memory

## Browser Automation

Powered by Playwright MCP.

Capabilities:

* Open websites
* Read page content
* Interact with webpages
* Manage tabs
* Extract information

## WhatsApp Automation

Powered by MCP WhatsApp.

Capabilities:

* Send WhatsApp messages
* Contact lookup
* Automated messaging workflows

## Gmail

Capabilities:

* Read emails
* Send emails
* Gmail search support

## Google Calendar

Capabilities:

* Read upcoming events
* Create calendar events

## File Generation

Capabilities:

* Generate PDF documents
* Generate Excel spreadsheets

## Terminal Access

Capabilities:

* Execute Linux terminal commands

---

# Architecture

```text
START
  ↓
Planner
  ↓
Risk Assessment
  ↓
Approval
  ↓
Executor
  ↓
Tools
  ↓
Executor Loop
  ↓
END
```

Memory Stack:

```text
User
 ↓
STM (Conversation Memory)
 ↓
LTM (PostgreSQL Memory Store)
 ↓
Context Injection
```

---

# Tech Stack

## Core

* Python 3.14+
* LangGraph
* LangChain
* PostgreSQL
* OpenRouter

## Integrations

* Playwright MCP
* WhatsApp MCP
* Gmail API
* Google Calendar API

## Storage

* AsyncPostgresSaver
* PostgreSQL Store

---

# Prerequisites

Install:

* Python 3.14+
* uv
* PostgreSQL
* Node.js

Verify:

```bash
python --version
uv --version
node --version
psql --version
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/CherukuriPavanKumar/Agent-Vortex.git

cd Agent-Vortex
```

Install dependencies:

```bash
uv sync
```

---

# Environment Variables

Create:

```bash
cp .env.example .env
```

Example:

```env
OPENROUTER_API_KEY=your_openrouter_key

DATABASE_URL=postgresql://postgres:password@localhost:5433/agent_vortex
```

---

# PostgreSQL Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE agent_vortex;
```

Ensure PostgreSQL is running and the DATABASE_URL is correct.

The application automatically creates required tables during startup.

---

# Browser MCP Setup

Agent Vortex uses Playwright MCP.

Verify it works:

```bash
npx @playwright/mcp@latest --headless
```

The browser integration will automatically connect during startup.

Expected:

```text
[Browser MCP] Connected.
[Browser MCP] 23 tools available.
```

---

# Gmail & Google Calendar Setup

Google integrations are optional.

To enable:

1. Open Google Cloud Console
2. Create a project
3. Enable:

   * Gmail API
   * Google Calendar API
4. Configure OAuth Consent Screen
5. Create Desktop OAuth Credentials
6. Download:

```text
credentials.json
```

Place it in the repository root.

Run once locally:

```bash
uv run main.py
```

Authorize the application.

A:

```text
token.pickle
```

file will be generated automatically.

---

# WhatsApp Setup

WhatsApp integration is optional.

Agent Vortex uses an MCP-based WhatsApp server.

The server must be running before startup.

When configured correctly:

```text
[WhatsApp] Tool loaded.
```

appears during startup.

---

# Running Agent Vortex

Start the agent:

```bash
uv run main.py
```

Expected startup:

```text
[1/6] Bootstrapping database...
[2/6] Checking LLM...
[3/6] Connecting Browser MCP...
[4/6] Loading tools...
[5/6] Connecting checkpointer...
[6/6] Building graph...

Agent Vortex Ready.
```

---

# Available Tools

Current tools:

* terminal_tool
* browser_navigate
* browser_read
* browser_interaction
* browser_tabs
* whatsapp_send_message
* gmail_read
* gmail_send
* calendar_read
* calendar_write
* generate_pdf
* generate_excel

---

# Project Structure

```text
Agent-Vortex/
│
├── core_setup/
├── memory/
├── nodes/
├── tools/
│
├── generated_pdfs/
├── generated_excels/
│
├── main.py
├── state.py
├── config.yaml
├── pyproject.toml
└── README.md
```

---

# Current Status

Current version:

```text
v0.1.0
```

Implemented:

* Browser Automation
* WhatsApp Automation
* Gmail
* Calendar
* Memory System
* PostgreSQL Persistence
* PDF Generation
* Excel Generation

Future work:

* Docker support
* Simplified onboarding
* Additional MCP integrations
* Improved memory architecture
* Expanded tool ecosystem

---

# License

MIT License
