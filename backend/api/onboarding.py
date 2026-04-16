"""Center onboarding endpoints.

First-run setup wizard for a new center. ``GET /api/onboarding/status``
reports whether the center is configured, ``POST /api/onboarding/complete``
accepts the wizard payload and:

1. Writes each field to the ``center_config`` key/value table.
2. Generates a minimal markdown handbook in ``settings.handbook_path`` (one
   file per topic: hours, holidays, tuition, sick policy, meals, tours) so
   the retriever has content even before the operator customizes further.
3. Re-runs ``load_handbook()`` so the new files are live without restarting.
"""
import os

from fastapi import APIRouter
from pydantic import BaseModel

from backend.db.config import get_all_config, set_config
from backend.settings import settings
from backend.knowledge.loader import load_handbook

router = APIRouter(tags=["onboarding"])


class OnboardingRequest(BaseModel):
    center_name: str
    operator_email: str
    operating_hours: str
    holidays_closed: str
    tuition_infant: str
    tuition_toddler: str
    tuition_preschool: str
    sick_policy: str
    meals_info: str
    tour_scheduling: str


@router.get("/onboarding/status")
async def onboarding_status():
    config = await get_all_config()
    is_configured = bool(config.get("center_name"))
    return {"configured": is_configured, "config": config}


@router.post("/onboarding/complete")
async def complete_onboarding(request: OnboardingRequest):
    config_items = {
        "center_name": request.center_name,
        "operator_email": request.operator_email,
        "operating_hours": request.operating_hours,
        "holidays_closed": request.holidays_closed,
        "tuition_infant": request.tuition_infant,
        "tuition_toddler": request.tuition_toddler,
        "tuition_preschool": request.tuition_preschool,
        "sick_policy": request.sick_policy,
        "meals_info": request.meals_info,
        "tour_scheduling": request.tour_scheduling,
    }

    for key, value in config_items.items():
        await set_config(key, value)

    _generate_handbook(request)

    load_handbook()

    return {"status": "complete", "center_name": request.center_name}


def _generate_handbook(req: OnboardingRequest):
    handbook_path = settings.handbook_path
    os.makedirs(handbook_path, exist_ok=True)

    _write_md(
        handbook_path,
        "hours.md",
        "hours",
        f"# Operating Hours — {req.center_name}\n\n{req.operating_hours}",
    )

    _write_md(
        handbook_path,
        "holidays.md",
        "holidays",
        f"# Holiday Closures — {req.center_name}\n\n"
        f"{req.center_name} is closed on the following holidays:\n\n{req.holidays_closed}",
    )

    _write_md(
        handbook_path,
        "tuition.md",
        "tuition",
        f"# Tuition — {req.center_name}\n\n"
        f"## Monthly Tuition Rates\n\n"
        f"| Age Group | Monthly Rate |\n|---|---|\n"
        f"| Infant | {req.tuition_infant} |\n"
        f"| Toddler | {req.tuition_toddler} |\n"
        f"| Preschool | {req.tuition_preschool} |\n",
    )

    _write_md(
        handbook_path,
        "sick_policy.md",
        "sick_policy",
        f"# Sick Child Policy — {req.center_name}\n\n{req.sick_policy}",
    )

    _write_md(
        handbook_path,
        "meals.md",
        "meals",
        f"# Meals & Nutrition — {req.center_name}\n\n{req.meals_info}",
    )

    _write_md(
        handbook_path,
        "tours.md",
        "tours",
        f"# Scheduling a Tour — {req.center_name}\n\n{req.tour_scheduling}",
    )


def _write_md(directory: str, filename: str, category: str, content: str):
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write(f"---\ncategory: {category}\nupdated_at: 2025-01-15\n---\n\n{content}\n")
