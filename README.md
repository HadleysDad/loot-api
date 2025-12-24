🎲 Loot Table API

A lightweight, deterministic, and simulation-ready Loot Table API for game developers.
Designed for balancing, drop simulation, and fair randomness validation across indie and studio-scale projects.

Built with Python + FastAPI, optimized for clarity, extensibility, and zero-cost deployment.

🚀 Overview

The Loot Table API allows developers to:

Generate randomized loot drops based on weighted rarity tables

Simulate thousands of drops to validate balance

Analyze drop distributions before shipping to players

Maintain deterministic and testable RNG behavior

This API is ideal for:

Roblox developers

Unity / Godot / Unreal backend services

Indie game balancing pipelines

Marketplace-distributed APIs (RapidAPI, custom SaaS)

✨ Core Features

🎯 Weighted loot generation

📊 Large-scale drop simulations

⚖️ Balance analysis endpoints

🔁 Deterministic RNG support

📁 JSON-based loot tables

🧩 Modular service architecture

🚀 FastAPI performance + OpenAPI docs

🧱 Project Structure
loot-api/
├── app/
│   ├── main.py                # FastAPI entry point
│   ├── schemas.py             # Request / response schemas
│   ├── rng.py                 # Random number utilities
│   ├── drop_engine.py         # Core loot selection logic
│   ├── loot_loader.py         # Loot table JSON loader
│   ├── loot_table.json        # Example loot table
│   │
│   ├── models/
│   │   └── loot_models.py     # Internal data models
│   │
│   ├── services/
│   │   └── loot_service.py    # Business logic layer
│   │
│   └── routes/
│       ├── loot.py            # Drop generation endpoints
│       ├── simulation.py      # Simulation endpoints
│       └── balance.py         # Balance analysis endpoints
│
├── requirements.txt
└── .gitignore

🛠 Tech Stack

Python 3.11+

FastAPI

Pydantic

Uvicorn

JSON-driven configuration

📦 Installation
1. Clone the repository
git clone https://github.com/your-username/loot-api.git
cd loot-api

2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

▶️ Running the API
uvicorn app.main:app --reload


API will be available at:

http://127.0.0.1:8000


Interactive documentation:

http://127.0.0.1:8000/docs

🔌 API Endpoints
🎁 Generate Loot Drop

POST /loot/generate

Generates a single loot drop from the configured loot table.

Example Request

{
  "table_name": "default"
}

📊 Simulate Drops

POST /simulate

Runs large-scale simulations to validate rarity distribution.

Example Request

{
  "table_name": "default",
  "iterations": 10000
}

⚖️ Balance Analysis

POST /balance

Provides drop distribution percentages and imbalance insights.

Example Request

{
  "table_name": "default",
  "iterations": 5000
}

🧬 Loot Table Format

Loot tables are JSON-based and fully customizable.

Example: loot_table.json

{
  "default": {
    "Common": [
      { "item": "Wood Sword", "weight": 60 },
      { "item": "Cloth Armor", "weight": 40 }
    ],
    "Rare": [
      { "item": "Steel Sword", "weight": 25 }
    ],
    "Legendary": [
      { "item": "Dragon Blade", "weight": 5 }
    ]
  }
}

🧠 Design Philosophy

Deterministic randomness – reproducible results for testing

Separation of concerns – routes, services, models

Extensibility first – easy to add modifiers, luck, profiles

Marketplace-ready – stateless, scalable, documented

🛣 Roadmap

Planned enhancements:

Luck modifiers & rarity multipliers

Player profile-based drops

Import/export loot table validation

Seeded RNG per player/session

Auth + rate limiting (RapidAPI-ready)

Web dashboard for simulations

📈 Use Cases

Game loot balancing before launch

Regression testing after balance patches

Marketplace API consumption

Internal tooling for game studios

Educational probability simulations

🤝 Contributing

Contributions are welcome.

Fork the repository

Create a feature branch

Submit a pull request with clear scope

📄 License

MIT License
Free for personal and commercial use.

📬 Contact

Built for developers who care about fair loot, transparent odds, and clean architecture.