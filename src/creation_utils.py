
# src/creation_utils.py
"""Utility functions for the creation process, including color extraction and title generation."""

from pathlib import Path
from typing import Tuple, List
from PIL import Image
import random
import re
import colorsys

# === Color Extraction ===
def get_dominant_color(image_path: Path, quality: int = 150) -> Tuple[int, int, int]:
    """
    Finds the dominant color in an image.

    Args:
        image_path: Path to the image file.
        quality: The quality of the analysis. A lower number is faster but less accurate.
                 It corresponds to the size the image is resized to for analysis.

    Returns:
        A tuple (r, g, b) representing the dominant color.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found at {image_path}")

    image = Image.open(image_path).convert("RGB")
    
    # Resize for performance. 
    image.thumbnail((quality, quality))
    
    # Get colors from image and find the most common one
    pixels = image.getcolors(image.width * image.height)
    
    # Sort them by count
    sorted_pixels = sorted(pixels, key=lambda t: t[0], reverse=True)
    
    # The dominant color is the first one in the sorted list.
    # We iterate to find the first non-grayscale color for more interesting results.
    for count, color in sorted_pixels:
        # Avoid pure grays/whites/blacks if possible
        if abs(color[0] - color[1]) > 15 or abs(color[1] - color[2]) > 15:
            return color
            
    # Fallback to the most dominant color if all are grayscale
    if sorted_pixels:
        return sorted_pixels[0][1]
    else:
        # Fallback for very unusual images
        return (128, 128, 128)


def select_vivid_dark_color(image_path: Path, quality: int = 150, top_k: int = 12) -> Tuple[int, int, int]:
    """Pick a background color that is darker yet saturated (avoid grey/near white).

    Strategy:
    - Sample palette via getcolors on a downsized image
    - Rank by score = saturation_weight * S + darkness_weight * (1 - V)
      with soft constraints 0.18 <= V <= 0.80 and S >= 0.25 preferred
    - Fall back to get_dominant_color if no good candidate
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found at {image_path}")

    image = Image.open(image_path).convert("RGB")
    image.thumbnail((quality, quality))
    pixels = image.getcolors(image.width * image.height)
    if not pixels:
        return get_dominant_color(image_path, quality)

    # Take top_k most frequent colors first to avoid outliers
    top = sorted(pixels, key=lambda t: t[0], reverse=True)[:max(4, top_k)]

    def score(rgb: Tuple[int, int, int]) -> float:
        r, g, b = [c / 255.0 for c in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        # Soft masks: penalize too bright/too dark and low saturation
        sat_pref = s
        dark_pref = (1.0 - v)
        # Windowing boosts for preferred range
        v_boost = 1.0 if 0.18 <= v <= 0.80 else 0.5
        s_boost = 1.0 if s >= 0.25 else 0.4
        return (1.2 * sat_pref + 1.0 * dark_pref) * v_boost * s_boost

    # Filter near-greys/near-whites quickly
    candidates = []
    for _, rgb in top:
        r, g, b = rgb
        if abs(r - g) < 6 and abs(g - b) < 6:
            continue  # near grey
        candidates.append(rgb)

    if not candidates:
        candidates = [rgb for _, rgb in top]

    best = max(candidates, key=score)
    # If best is still too light, blend slightly toward black to reduce value while keeping hue
    r, g, b = best
    rr, gg, bb = [c / 255.0 for c in (r, g, b)]
    h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
    if v > 0.85:
        v = 0.65  # pull down brightness
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        best = (int(rr * 255), int(gg * 255), int(bb * 255))
    return best

def get_color_family(rgb: Tuple[int, int, int]) -> str:
    """Categorizes an RGB color into a poetic color family (English)."""
    r, g, b = rgb
    
    # Calculate perceived brightness
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    
    # Check for neutrals
    if max(r, g, b) - min(r, g, b) < 40: # Low saturation means neutral
        if brightness > 200: return "whisper-white"
        if brightness < 50: return "deepest shadow"
        return "neutral grey"

    # Hues
    if r > g and r > b: # Reddish
        if b < 100 and g < 100 and brightness > 150: return "vibrant red"
        if r > 180 and g > 100 and b < 100: return "warm orange"
        if g > b: return "earthy brown"
        return "crimson dusk"
    elif g > r and g > b: # Greenish
        if r < 100 and b < 100: return "forest green"
        if r > 100 and b > 100: return "pale mint"
        return "verdant moss"
    elif b > r and b > g: # Bluish
        if r < 100 and g < 100: return "deep ocean"
        if r > 150 and g > 150: return "sky blue"
        return "cool blue"
    
    # Special cases
    if r > 200 and g > 200 and b < 100: return "golden light" # Yellowish
    if r > 150 and b > 150 and g < 100: return "velvet violet" # Purplish

    return "undefined hue" # Fallback


# === Poetic Thesaurus (English) ===
IMAGE_CONCEPT_MAP = {
    "cat": ["a cat's soft sigh", "velvet paws on sunbeams", "the slow blink of contentment", "a curled-up warmth", "whispers of fur"],
    "window": ["through pane-glass dreams", "framed by gentle light", "a quiet observer's gaze", "beyond the sill"],
    "sun": ["the slow dance of light patterns", "golden hour haze", "a pool of warmth", "liquid gold"],
    "rain": ["soft drumming on the glass", "a world washed anew", "distant thunder's hush", "petrichor's embrace"],
    "book": ["rustling pages", "stories whispered low", "ink-stained dreams", "a silent journey"],
    "radio": ["static hum of forgotten tunes", "a vintage melody's embrace", "waves carrying old solace"],
    "plant": ["tender shoots reaching", "a silent growth", "verdant peace"],
    "coffee": ["steaming comfort", "the bitter-sweet morning", "a grounding ritual"],
    "vinyl": ["the crackle of memory", "spinning nostalgia", "grooves of time"],
    "music": ["unseen harmonies", "a melody's journey", "silent symphonies"],
    "cozy": ["a soft embrace", "comfort's quiet hum", "nestled deep"],
    "dream": ["stolen moments of slumber", "a realm of gentle fancy", "waking reverie"],
    "sleep": ["a lullaby's soft touch", "deep rest's embrace", "unfurling peace"],
    "peace": ["a quiet heart's rhythm", "serene stillness", "the gentle ebb"],
    "calm": ["still waters run deep", "a serene whisper", "untroubled depths"],
    "chill": ["a gentle breeze's caress", "the cool touch of fate", "quietude's realm"],
    "relax": ["unwinding moments", "sinking into bliss", "letting go"],
}

COLOR_CONCEPT_MAP = {
    "warm brown": ["earthy calm", "baked earth's embrace", "cinnamon whispers", "woodsmoke haze", "velvet stillness"],
    "cool blue": ["deep twilight's expanse", "ocean's soft murmur", "sky's silent song", "distant horizons", "gentle tide"],
    "neutral grey": ["morning mists", "silvered silence", "urban hush", "stone's quietude", "soft-focus dream"],
    "crimson dusk": ["embers of day", "a slow burn", "velvet twilight", "wine-dark peace"],
    "golden light": ["amber reverie", "honeyed moments", "a sun-drenched hush", "radiant calm"],
    "vibrant red": ["fire's soft glow", "passion's quiet breath"],
    "warm orange": ["sunset's memory", "whispers of citrus"],
    "whisper-white": ["cloud-spun thoughts", "a fresh beginning"],
    "deepest shadow": ["night's gentle cloak", "unseen depths"],
    "forest green": ["canopy's embrace", "leaves' subtle dance"],
    "undefined hue": ["a fleeting glimpse", "unspoken thoughts"], # Fallback for unknown colors
}

# === Title Generation ===
def sanitize_title(raw: str) -> str:
    """Remove excessive punctuation, collapse spaces, and cap to 8 words."""
    import re as _re
    text = _re.sub(r"\s+", " ", raw or "").strip()
    text = _re.sub(r'(^[-.,;:\'"\s]+)|([-.,;:\'"\s]+$)', '', text)
    text = _re.sub(r"[\.,;:!?\-–—_/\\\(\)\[\]\{\}\"]+", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    parts = text.split(" ") if text else []
    if len(parts) > 8:
        parts = parts[:8]
    return " ".join(parts)


def to_title_case(text: str) -> str:
    """Apply simple English title case with common minor-words exceptions."""
    minor = {
        "a","an","the","and","but","or","nor","for","so","yet",
        "as","at","by","for","in","of","on","per","to","via","with",
        "over","into","onto","from","up","off"
    }
    words = text.split()
    if not words:
        return text
    result: List[str] = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i == 0 or i == len(words) - 1 or lw not in minor:
            result.append(lw.capitalize())
        else:
            result.append(lw)
    return " ".join(result)


def generate_poetic_title(
    image_filename: str, 
    dominant_color: Tuple[int, int, int], 
    playlist_keywords: List[str], 
    seed: int
) -> str:
    """
    Generates a poetic English title based on image content, color, and playlist vibe.
    
    Args:
        image_filename: The filename of the chosen image (e.g., "0xgarfield_a_cute_cat...").
        dominant_color: The (r, g, b) tuple of the image's dominant color.
        playlist_keywords: A list of keywords extracted from the playlist.
        seed: A seed for a random number generator to ensure reproducibility.
        
    Returns:
        A poetic English title string.
    """
    rng = random.Random(seed)
    
    # 1. Extract image keywords from filename
    image_base_name = image_filename.replace("0xgarfield_", "").split("_", 1)[-1]
    raw_image_keywords = re.findall(r'[a-z]+', image_base_name.lower())
    image_keywords = [
        kw for kw in raw_image_keywords 
        if kw in IMAGE_CONCEPT_MAP and len(kw) > 2 # Filter out short non-descriptive words
    ]
    
    # 2. Get color family
    color_family = get_color_family(dominant_color)
    
    # 3. Collect concepts from thesaurus
    # Prioritize image concepts if available
    img_concept = rng.choice(IMAGE_CONCEPT_MAP[rng.choice(image_keywords)]) if image_keywords else None
    
    # If no specific image keyword, try to get a more general concept related to 'cozy' or 'dream' from image concepts
    if not img_concept and ("cozy" in IMAGE_CONCEPT_MAP or "dream" in IMAGE_CONCEPT_MAP):
        img_concept = rng.choice(IMAGE_CONCEPT_MAP[rng.choice(["cozy", "dream"])]) # Fallback for images without parseable keywords

    color_concept = rng.choice(COLOR_CONCEPT_MAP[color_family]) if color_family in COLOR_CONCEPT_MAP else None
    
    # Randomly pick a playlist keyword to use, if available
    pl_keyword_concept = rng.choice(playlist_keywords) if playlist_keywords else None


    # Define templates for "Poetic Titles" - favoring shorter, evocative phrases
    # (Templates are ordered to give a slight preference to shorter/more impactful if picked randomly without explicit weighting)
    TEMPLATES = [
        # Highly compact, single-concept
        "{img_concept}", # e.g., A cat's soft sigh
        "{color_concept}", # e.g., Earthy calm
        "{pl_keyword_concept}", # e.g., Dream
        
        # Two concepts, short and evocative
        "{color_concept}'s {img_concept_short}", # e.g., Earthy calm's soft sigh
        "{img_concept} in {color_concept}", # e.g., Velvet paws in golden light
        "{pl_keyword_concept} with {img_concept_short}", # e.g., Dream with velvet paws
        "{color_concept} of {pl_keyword_concept}", # e.g., Deep ocean of calm
        
        # Slightly longer, more narrative
        "{img_concept}, a {color_concept} whisper", # e.g., A curled-up warmth, an earthy calm whisper
        "The {pl_keyword_concept} of {color_concept}", # e.g., The lullaby of deep ocean
        "Lost in {img_concept}, found in {color_concept}", # e.g., Lost in vapor trails, found in golden light
        
        # Poetic Questions / Imperatives
        "Did you dream of {img_concept}?", # e.g., Did you dream of whispers of fur?
    ]
    
    # Filter templates based on available concepts to avoid partial titles
    available_templates = []
    
    # Prepare shortened versions of concepts for some templates (e.g. "soft sigh" from "a cat's soft sigh")
    img_concept_short = img_concept.split(" of ", 1)[-1] if img_concept and " of " in img_concept else img_concept
    color_concept_short = color_concept.split("'s ", 1)[-1] if color_concept and "'s " in color_concept else color_concept

    
    for tmpl in TEMPLATES:
        # Simple check for required placeholders
        if "{img_concept}" in tmpl and not img_concept:
            continue
        if "{img_concept_short}" in tmpl and not img_concept_short:
            continue
        if "{color_concept}" in tmpl and not color_concept:
            continue
        if "{color_concept_short}" in tmpl and not color_concept_short:
            continue
        if "{pl_keyword_concept}" in tmpl and not pl_keyword_concept:
            continue
        available_templates.append(tmpl)
        
    if not available_templates:
        return f"A Moment of {seed}" # Fallback if no template fits
        
    chosen_template = rng.choice(available_templates)
    
    # Format the title using available concepts
    title = chosen_template.format(
        img_concept=img_concept or "", 
        img_concept_short=img_concept_short or "",
        color_concept=color_concept or "",
        color_concept_short=color_concept_short or "",
        pl_keyword_concept=pl_keyword_concept or ""
    ).strip()
    
    # Sanitize and title case
    title = sanitize_title(title)
    title = to_title_case(title)
    return title if title else f"A Quiet Melody ({seed})"

