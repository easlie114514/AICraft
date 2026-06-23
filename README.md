# AICraft

A desktop launcher that turns any LLM into a fully equipped AI assistant with plug-and-play Skills, MCP tools, RAG knowledge bases and memory.

## What is AICraft?

Like a mod launcher for AI — plug in Skills, MCP, RAG, memory and start crafting.

AICraft is a lightweight desktop application that provides visual management for AI capabilities. Instead of wrestling with config files and CLI commands, you get a clean interface to manage everything your LLM can do:

- **Skill** — Drop a skill folder in, toggle it on, and your LLM gains new abilities
- **MCP** — Add a server by IP:Port, see connection status in real-time, toggle on/off
- **RAG** — Point to a document directory, auto-index, toggle retrieval on/off
- **Memory** — Conversation history, project notes, and smart retrieval across sessions
- **Role** — Switch system prompts like changing characters
- **Model** — Manage multiple LLM API configs, switch with one click

## Quick Start

```bash
pip install -r requirements.txt
python aicraft.py
```

## Architecture

```
AICraft/
├── aicraft.py              # Main entry
├── config/                  # Global config
│   └── profiles/           # Project profiles (isolated configs)
├── models/                  # LLM API configs
├── roles/                   # System prompt templates
├── skills/                  # Skill modules
├── mcp/                     # MCP connection configs
├── rag/                     # RAG data source configs
├── memory/                  # Conversation history & notes
├── chroma_db/               # Vector database (auto-managed)
└── docs/                    # Documentation
```

## Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| UI Framework | Flet | Pure Python, Material Design |
| LLM Client | litellm | Unified API for 100+ models |
| MCP Client | mcp Python SDK | Official SDK |
| Vector DB | ChromaDB | Embedded, pure Python, no server |
| Embedding | sentence-transformers | Local, free, offline |
| Search | duckduckgo-search | Free, no API key |
| Packaging | PyInstaller | Single .exe output |

## Development

See [docs/TECH_SPEC.md](docs/TECH_SPEC.md) for full technical specification.

## License

MIT
