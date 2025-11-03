"""
Description Linting Routes for T2R

Lint and fix description text (branding, CC0, SEO).
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime
import logging
import re

router = APIRouter()
logger = logging.getLogger(__name__)


class DescLintRequest(BaseModel):
    episode_id: str
    description: str
    auto_fix: bool = False


@router.post("/desc/lint")
async def lint_description(request: DescLintRequest) -> Dict:
    """
    Lint description for issues.
    
    Checks:
    - Branding misuse ("Vibe Coding" instead of correct brand)
    - CC0 template missing
    - SEO metadata missing
    
    Returns:
        {
            "status": "ok",
            "flags": List[str],
            "suggestions": List[Dict],
            "fixed": str (if auto_fix)
        }
    """
    flags = []
    suggestions = []
    fixed_text = request.description
    
    # Check for branding misuse
    if "Vibe Coding" in request.description:
        flags.append("branding_misuse")
        suggestions.append({
            "type": "branding_misuse",
            "issue": "Incorrect brand name 'Vibe Coding' used",
            "fix": "Replace with correct brand name"
        })
        if request.auto_fix:
            # Replace with correct brand (placeholder)
            fixed_text = fixed_text.replace("Vibe Coding", "Kat Records")
    
    # Check for CC0 template
    cc0_pattern = r"(CC0|Creative Commons Zero|Public Domain)"
    if not re.search(cc0_pattern, request.description, re.IGNORECASE):
        flags.append("cc0_missing")
        suggestions.append({
            "type": "cc0_missing",
            "issue": "CC0 license statement missing",
            "fix": "Add CC0 license template"
        })
        if request.auto_fix:
            cc0_template = "\n\n---\n\nMusic: CC0 Public Domain"
            fixed_text += cc0_template
    
    # Check for SEO keywords (basic check)
    seo_keywords = ["ambient", "music", "relaxing", "background"]
    has_seo = any(keyword.lower() in request.description.lower() for keyword in seo_keywords)
    if not has_seo:
        flags.append("seo_weak")
        suggestions.append({
            "type": "seo_weak",
            "issue": "Description may lack SEO keywords",
            "fix": "Add relevant keywords naturally"
        })
    
    result = {
        "status": "ok",
        "flags": flags,
        "suggestions": suggestions,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if request.auto_fix and fixed_text != request.description:
        result["fixed"] = fixed_text
    
    return result

