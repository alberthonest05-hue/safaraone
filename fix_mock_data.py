import pprint

# Read the current module
import importlib.util
spec = importlib.util.spec_from_file_location("mock", "data/mock_data.py")
mock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock)

DEST = mock.DESTINATIONS
ACC = mock.ACCOMMODATIONS
EXP = mock.EXPERIENCES
GUIDES = mock.GUIDES

def set_urls(lst, kword_field, extra):
    for item in lst:
        kw = item.get(kword_field, "").replace(" ", ",")
        dest_id = item.get("destination_id", item.get("id"))
        base = f"https://source.unsplash.com/400x300/?{dest_id},{kw},{extra}"
        item["image_url"] = base
        if "avatar_url" in item:
            item["avatar_url"] = f"https://source.unsplash.com/200x200/?portrait,face,{item['destination_id']}"
        if "gallery" in item:
            item["gallery"] = [
                f"https://source.unsplash.com/400x300/?{dest_id},scenic,1",
                f"https://source.unsplash.com/400x300/?{dest_id},scenic,2",
                f"https://source.unsplash.com/400x300/?{dest_id},scenic,3",
            ]

set_urls(DEST, "name", "landscape")
set_urls(ACC, "type", "hotel,resort")
set_urls(EXP, "category", "activity,tour")

for g in GUIDES:
    g["avatar_url"] = f"https://source.unsplash.com/400x300/?portrait,face,african"

methods_str = """
def get_destination_by_id(dest_id: str):
    return next((d for d in DESTINATIONS if d["id"] == dest_id), None)

def get_accommodations_by_destination(dest_id: str):
    return [a for a in ACCOMMODATIONS if a["destination_id"] == dest_id]

def get_experiences_by_destination(dest_id: str):
    return [e for e in EXPERIENCES if e["destination_id"] == dest_id]

def get_guides_by_destination(dest_id: str):
    return [g for g in GUIDES if g["destination_id"] == dest_id]

def generate_itinerary(destination_id: str, budget_usd: float, days: int, travelers: int) -> dict:
    dest = get_destination_by_id(destination_id)
    if not dest:
        return {"error": "Destination not found"}

    stays = get_accommodations_by_destination(destination_id)
    exps  = get_experiences_by_destination(destination_id)
    guides_list = get_guides_by_destination(destination_id)

    per_person_budget = budget_usd / travelers

    accom_budget_per_night = (per_person_budget * 0.50) / days
    suitable_stays = sorted(
        [s for s in stays if s["price_per_night_usd"] <= accom_budget_per_night * 1.3],
        key=lambda x: x["rating"],
        reverse=True
    )
    chosen_stay = suitable_stays[0] if suitable_stays else stays[-1]
    stay_total = chosen_stay["price_per_night_usd"] * days

    guide_budget = per_person_budget * 0.20
    suitable_guides = sorted(
        [g for g in guides_list if g["price_per_day_usd"] <= guide_budget],
        key=lambda x: x["rating"],
        reverse=True
    )
    chosen_guide = suitable_guides[0] if suitable_guides else None

    remaining = per_person_budget - stay_total
    if chosen_guide:
        remaining -= chosen_guide["price_per_day_usd"]

    chosen_experiences = []
    exp_pool = sorted(exps, key=lambda x: x["rating"], reverse=True)
    for exp in exp_pool:
        if remaining >= exp["price_usd"] and len(chosen_experiences) < days + 1:
            chosen_experiences.append(exp)
            remaining -= exp["price_usd"]

    itinerary_days = []
    exp_idx = 0
    for day_num in range(1, days + 1):
        day_exp = chosen_experiences[exp_idx] if exp_idx < len(chosen_experiences) else None
        if day_exp:
            exp_idx += 1
        itinerary_days.append({
            "day": day_num,
            "date_label": f"Day {day_num}",
            "accommodation": chosen_stay,
            "experience": day_exp,
            "guide": chosen_guide if day_num == 1 else None,
            "day_cost_usd": (
                chosen_stay["price_per_night_usd"]
                + (day_exp["price_usd"] if day_exp else 0)
                + (chosen_guide["price_per_day_usd"] if chosen_guide and day_num == 1 else 0)
            )
        })

    total_cost = sum(d["day_cost_usd"] for d in itinerary_days)
    savings = per_person_budget - total_cost

    return {
        "destination": dest,
        "days": days,
        "travelers": travelers,
        "budget_usd": budget_usd,
        "total_cost_usd": round(total_cost, 2),
        "savings_usd": round(max(savings, 0), 2),
        "budget_utilization_pct": round(min((total_cost / per_person_budget) * 100, 100), 1),
        "itinerary": itinerary_days,
        "summary": {
            "accommodation": chosen_stay["name"],
            "accommodation_tier": chosen_stay["tier"],
            "guide": chosen_guide["name"] if chosen_guide else "Self-guided",
            "experiences_count": len(chosen_experiences),
            "tip": _generate_tip(destination_id, per_person_budget),
        }
    }

def _generate_tip(destination_id: str, budget: float) -> str:
    tips = {
        "zanzibar": [
            "Book dolphin tours early morning for the best sightings at Kizimkazi.",
            "Forodhani Night Market in Stone Town is a must — $5 fills you up royally.",
            "Negotiate spice prices at Darajani Market using Swahili phrases.",
        ],
        "serengeti": [
            "June–October offers the best Great Migration river crossing views.",
            "Early morning (6–9am) and late afternoon (4–7pm) are prime animal activity times.",
            "Pack light layers — mornings on the savanna can be surprisingly cold.",
        ],
        "kilimanjaro": [
            "Spend an extra acclimatization day — your summit chances increase by 40%.",
            "Pack high-energy snacks like nuts, chocolate, and dried fruit for the summit push.",
            "Hire local porters — they're essential support and it directly helps the community.",
        ]
    }
    import random
    dest_tips = tips.get(destination_id, ["Enjoy your Tanzania adventure!"])
    return random.choice(dest_tips)
"""

with open("data/mock_data.py", "w") as f:
    f.write('import random\nfrom datetime import datetime\n\n')
    f.write('DESTINATIONS = ' + pprint.pformat(DEST, sort_dicts=False) + '\n\n')
    f.write('ACCOMMODATIONS = ' + pprint.pformat(ACC, sort_dicts=False) + '\n\n')
    f.write('EXPERIENCES = ' + pprint.pformat(EXP, sort_dicts=False) + '\n\n')
    f.write('GUIDES = ' + pprint.pformat(GUIDES, sort_dicts=False) + '\n\n')
    f.write(methods_str)

print("success!")
