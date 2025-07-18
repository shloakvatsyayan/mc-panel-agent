# Minecraft Panel Agent (Pelican v1)

A minimal OpenAI‑function‑calling agent that **only** manages the Minecraft
server whose UUID is `6dcdb020-5ac5-4867-9bc3-98092e4f71fb` through the Pelican
(= Pterodactyl v1) *client* API.

Key points
* **Hard server whitelist** – any request touching a different server raises.
* **Max 20 reasoning/tool loops** per run (`MAX_STEPS = 20`).
* API + panel URL read from `.env` via `python‑dotenv`.
* Plugin workflow  
  1. `list_downloads` → LLM sees available jars in `./downloads`  
  2. If needed: `web_download(url)` from **Modrinth / SpigotMC / Hangar** only  
     (auto‑saves to `downloads/`).  
  3. `upload_plugin(plugin_name)` → uploads jar to `/plugins/` then restarts.

---

## Quick start

```bash
# 1. Install deps
pip install -r requirements.txt        # or 'poetry install'

# 2. Copy & edit .env
cp .env.example .env
#   – fill in PELICAN_BASE_URL, PELICAN_API_KEY, OPENAI_API_KEY

# 3. Run
python -m minecraft_agent.main "Start the server if it is offline."
