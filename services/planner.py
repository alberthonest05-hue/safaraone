import os
import json
from models import db, Destination, Accommodation, Experience, Guide

# Try to import OpenAI. Fallback mode if unavailable or key invalid.
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy"))
except ImportError:
    client = None

def generate_itinerary(destination_id: str, budget_usd: float, days: int, travelers: int) -> dict:
    """
    Phase 2B: DB-Constrained AI Planner.
    Queries the DB first, then maps specific results to OpenAI context to prevent hallucinations.
    """
    dest = db.session.get(Destination, destination_id)
    if not dest:
        return {"error": "Destination not found"}
    
    per_person_budget = budget_usd / travelers
    
    # 1. Provide Context Options from DB Constraints (avoid sending entire DB if too large)
    # We'll filter accommodations by maximum potential budget per night
    accom_budget_per_night = (per_person_budget * 0.70) / days
    db_stays = Accommodation.query.filter_by(destination_id=destination_id)\
                                  .filter(Accommodation.price_per_night_usd <= accom_budget_per_night * 1.5)\
                                  .limit(10).all()
                                  
    if not db_stays:
        db_stays = Accommodation.query.filter_by(destination_id=destination_id)\
                                      .order_by(Accommodation.price_per_night_usd.asc())\
                                      .limit(5).all()
    
    db_guides = Guide.query.filter_by(destination_id=destination_id).limit(5).all()
    
    # Send all experiences for this dest to context (usually < 20 items, perfectly fine for context limit)
    db_experiences = Experience.query.filter_by(destination_id=destination_id).all()
    
    # Convert constraints to minimalist JSON context for OpenAI
    context = {
        "accommodations": [{"id": s.id, "name": s.name, "tier": s.tier, "price_usd": s.price_per_night_usd, "type": s.type} for s in db_stays],
        "guides": [{"id": g.id, "name": g.name, "price_per_day_usd": g.price_per_day_usd, "specializations": g.specializations} for g in db_guides],
        "experiences": [{"id": e.id, "title": e.title, "price_usd": e.price_usd, "duration_hours": e.duration_hours, "category": e.category} for e in db_experiences]
    }
    
    # Check if we should use fallback
    use_fallback = False
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not client or api_key == "" or api_key.startswith("your_openai") or api_key.startswith("sk-placeholder"):
        use_fallback = True

    if not use_fallback:
        try:
            prompt = f"""
            You are a master Safari & Travel Planner for Tanzania.
            The user wants a {days}-day itinerary to {dest.name} for {travelers} traveler(s).
            Total Per Person Budget: ${per_person_budget:.2f}.
            
            Based EXACTLY on the JSON database context provided below, build an optimized day-by-day itinerary.
            You MUST ONLY select accommodations, guides, and experiences that exist in the JSON database context. DO NOT hallucinate names or IDs.
            
            Database Context Options:
            {json.dumps(context)}
            
            Return ONLY a raw JSON strictly matching this schema exactly (No markdown formatting or extra text):
            {{
                "total_cost_usd": float,
                "summary": {{
                    "accommodation": "string (name)",
                    "accommodation_tier": "string (e.g. luxury, mid-range)",
                    "guide": "string (name) or 'Self-guided'",
                    "tip": "string (1 helpful local tip)"
                }},
                "itinerary": [
                    {{
                        "day": int,
                        "date_label": "Day X",
                        "accommodation_id": "string",
                        "experience_id": "string or null",
                        "guide_id": "string or null",
                        "day_cost_usd": float
                    }}
                ]
            }}
            """
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={ "type": "json_object" },
                timeout=15.0 # Max 15s wait
            )
            
            content = response.choices[0].message.content
            ai_data = json.loads(content)
            
            # Sanity check the total against traveler budget
            ai_total = ai_data.get("total_cost_usd", 0)
            if ai_total > budget_usd * 1.1:
                print(f"Warning: AI returned cost ${ai_total} exceeding budget ${budget_usd}, using fallback")
                use_fallback = True
            
            if not use_fallback:
                # Rehydrate the AI's selected IDs into real DB objects to ensure they are valid for the frontend
                return _rehydrate_itinerary(dest, budget_usd, days, travelers, ai_data, db_stays, db_guides, db_experiences)
            
        except Exception as e:
            print(f"OpenAI Planner failed or timed out: {e}")
            # Fallback to naive local planner if error occurs
            use_fallback = True
            
    if use_fallback:
        return _naive_fallback_planner(dest, budget_usd, days, travelers, db_stays, db_guides, db_experiences)

def _rehydrate_itinerary(dest, budget_usd, days, travelers, ai_data, db_stays, db_guides, db_exps):
    """Maps the OpenAI JSON with IDs back to full SQLAlchemy Dictionary objects for the frontend."""
    stay_map = {s.id: s.to_dict() for s in db_stays}
    guide_map = {g.id: g.to_dict() for g in db_guides}
    exp_map = {e.id: e.to_dict() for e in db_exps}
    
    full_itinerary = []
    total_cost = 0
    
    for day_plan in ai_data.get("itinerary", []):
        day_cost = day_plan.get("day_cost_usd", 0)
        total_cost += day_cost
        
        full_itinerary.append({
            "day": day_plan.get("day", 1),
            "date_label": day_plan.get("date_label", f"Day {day_plan.get('day', '?')}"),
            "accommodation": stay_map.get(day_plan.get("accommodation_id")),
            "experience": exp_map.get(day_plan.get("experience_id")) if day_plan.get("experience_id") else None,
            "guide": guide_map.get(day_plan.get("guide_id")) if day_plan.get("guide_id") else None,
            "day_cost_usd": round(day_cost, 2)
        })
        
    per_person_budget = budget_usd / travelers
    return {
        "destination": dest.to_dict(),
        "days": days,
        "travelers": travelers,
        "budget_usd": budget_usd,
        "total_cost_usd": round(total_cost * travelers, 2),
        "savings_usd": round(budget_usd - (total_cost * travelers), 2),
        "budget_utilization_pct": round(((total_cost * travelers) / budget_usd) * 100, 1),
        "itinerary": full_itinerary,
        "summary": ai_data.get("summary", {})
    }

def _naive_fallback_planner(dest, budget_usd, days, travelers, db_stays, db_guides, db_experiences):
    """Fallback planner if OpenAI is down. Uses the naive Phase 2A algorithm but with DB objects."""
    per_person_budget = budget_usd / travelers
    
    # 1) Pick best accommodation that fits budget
    suitable_stays = sorted(db_stays, key=lambda x: x.rating or 0, reverse=True)
    chosen_stay = suitable_stays[0] if suitable_stays else None
    if not chosen_stay:
        chosen_stay = Accommodation.query.filter_by(destination_id=dest.id).first()
        
    stay_total = chosen_stay.price_per_night_usd * days if chosen_stay else 0

    # 2) Pick a guide
    guide_budget = per_person_budget * 0.20
    suitable_guides = [g for g in db_guides if g.price_per_day_usd <= guide_budget]
    suitable_guides = sorted(suitable_guides, key=lambda x: x.rating or 0, reverse=True)
    chosen_guide = suitable_guides[0] if suitable_guides else None

    # 3) Pick experiences
    remaining = per_person_budget - stay_total
    if chosen_guide:
        remaining -= chosen_guide.price_per_day_usd

    chosen_experiences = []
    exp_pool = sorted(db_experiences, key=lambda x: x.rating or 0, reverse=True)
    for exp in exp_pool:
        if remaining >= exp.price_usd and len(chosen_experiences) < days + 1:
            chosen_experiences.append(exp)
            remaining -= exp.price_usd

    # Build itinerary days
    itinerary_days = []
    exp_idx = 0
    for day_num in range(1, days + 1):
        day_exp = chosen_experiences[exp_idx] if exp_idx < len(chosen_experiences) else None
        if day_exp:
            exp_idx += 1
            
        day_cost = 0
        if chosen_stay: day_cost += chosen_stay.price_per_night_usd
        if day_exp: day_cost += day_exp.price_usd
        if chosen_guide and day_num == 1: day_cost += chosen_guide.price_per_day_usd
            
        itinerary_days.append({
            "day": day_num,
            "date_label": f"Day {day_num}",
            "accommodation": chosen_stay.to_dict() if chosen_stay else None,
            "experience": day_exp.to_dict() if day_exp else None,
            "guide": chosen_guide.to_dict() if chosen_guide and day_num == 1 else None,
            "day_cost_usd": day_cost
        })

    total_cost = sum(d["day_cost_usd"] for d in itinerary_days)
    savings = per_person_budget - total_cost

    DESTINATION_TIPS = {
        "zanzibar": "Book dolphin tours early morning for the best sightings.",
        "serengeti": "The Great Migration peaks July–October. Book campsites 6 months ahead.",
        "kilimanjaro": "Acclimatize for 2 days in Moshi before your summit attempt."
    }
    tip = DESTINATION_TIPS.get(dest.id, f"Explore {dest.name} like a local — ask your guide for hidden spots.")

    return {
        "destination": dest.to_dict(),
        "days": days,
        "travelers": travelers,
        "budget_usd": budget_usd,
        "total_cost_usd": round(total_cost * travelers, 2),
        "savings_usd": round(savings * travelers, 2),
        "budget_utilization_pct": round((total_cost / per_person_budget) * 100, 1),
        "itinerary": itinerary_days,
        "summary": {
            "accommodation": chosen_stay.name if chosen_stay else "None selected",
            "accommodation_tier": chosen_stay.tier.title() if chosen_stay and chosen_stay.tier else "Standard",
            "guide": f"{chosen_guide.name} (Day 1 only)" if chosen_guide else "Self-guided",
            "tip": tip
        }
    }
