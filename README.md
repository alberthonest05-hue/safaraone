# SafaraOne 🦒

SafaraOne is an AI-powered travel platform specializing in Tanzania tourism. This MVP showcases a dark glassmorphic UI, an AI itinerary planner (with offline fallback capability), dynamic mocked database integration, and pre-built models for destinations, accommodations, experiences, and guides.

## Features Let Up
- **Smart Itinerary Planner**: Connects to OpenAI or falls back beautifully to a deterministic deterministic selection algorithm.
- **Glassmorphic Design**: Built raw with CSS for maximum performance and pristine aesthetics.
- **Full Database Schema**: Preloaded with Swahili guides, boutique accommodations, and Serengeti/Kilimanjaro/Zanzibar tours.

## Getting Started Locally

1. Set up a virtual env and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Seeding the database:
   ```bash
   python3 seed_db.py
   ```

3. Configure your API keys in `.env`:
   - Duplicate `.env.example` -> `.env`
   - Set `OPENAI_API_KEY` to your key, or use `sk-placeholder` to test the fallback system.

4. Run the development server:
   ```bash
   python3 app.py
   ```

## Production Deployment (Beta)

If you are pushing this to Render, Heroku, or an Ubuntu environment, be sure to use `gunicorn`:
```bash
gunicorn -w 4 -b 0.0.0.0:5050 app:app
```
(Make sure your production environment loads `.env` properly or injects the secrets directly through the dashboard!)
