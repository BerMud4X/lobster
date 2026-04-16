import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from logger import logger
from reference_loader import load_exercises, get_muscles_latin_list, get_objectives_list, validate_code_base, validate_objective_code, load_protocol
import audit_logger
import prompt_cache

# Load API keys from .env
load_dotenv(Path(__file__).parent.parent.parent / ".env")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Available providers and models
PROVIDERS = {
    "1": {
        "name": "Mistral",
        "label": "Mistral API (French company, EU servers, RGPD compliant ✅)",
        "models": {
            "1": ("open-mistral-7b", "Mistral 7B — Fast, free tier"),
            "2": ("open-mixtral-8x7b", "Mixtral 8x7B — More powerful, free tier"),
            "3": ("mistral-small-latest", "Mistral Small — Best balance"),
        },
        "env_key": "MISTRAL_API_KEY",
    },
    "2": {
        "name": "Anthropic",
        "label": "Anthropic Claude API (US company, strong privacy policy ⚠️)",
        "models": {
            "1": ("claude-haiku-4-5-20251001", "Claude Haiku — Fast, affordable"),
            "2": ("claude-sonnet-4-6", "Claude Sonnet — Best balance"),
            "3": ("claude-opus-4-6", "Claude Opus — Most powerful"),
        },
        "env_key": "ANTHROPIC_API_KEY",
    },
}

RGPD_NOTICE = """
┌─────────────────────────────────────────────────────────────────┐
│                        RGPD / GDPR NOTICE                       │
├─────────────────────────────────────────────────────────────────┤
│ Your exercise data will be sent to the selected AI provider.    │
│                                                                 │
│  ✅ Mistral AI  — French company, servers in EU. Best choice    │
│     for identifiable or sensitive clinical data.                │
│                                                                 │
│  ⚠️  Anthropic  — US company (subject to US law). Acceptable    │
│     for fully anonymized data. Review their privacy policy.     │
│                                                                 │
│ BYOK model: you use your own API key. No data transits through  │
│ LOBSTER servers. You are responsible for your data.             │
└─────────────────────────────────────────────────────────────────┘
"""


def select_provider_and_model() -> tuple[str, str]:
    """Asks the user to select a provider and model. Returns (provider_name, model_id)."""
    print(RGPD_NOTICE)
    print("Choose your AI provider:")
    for key, provider in PROVIDERS.items():
        print(f"  {key} - {provider['label']}")

    provider_choice = input("Provider (1-2): ").strip()
    provider = PROVIDERS.get(provider_choice, PROVIDERS["1"])
    provider_name = provider["name"]

    print(f"\nAvailable models ({provider_name}):")
    for key, (model_id, description) in provider["models"].items():
        print(f"  {key} - {description}")

    model_choice = input("Choose a model (1-3): ").strip()
    model_id, _ = provider["models"].get(model_choice, list(provider["models"].values())[0])

    print(f"\nUsing: {provider_name} / {model_id}")
    logger.info(f"Provider selected: {provider_name}, model: {model_id}")

    return provider_name, model_id


def _build_prompt(text: str, exercises_ref: list[dict], muscles_ref: list[str], objectives_ref: list[dict], protocol: dict = None) -> str:
    """Builds the prompt for exercise extraction."""
    exercises_str = "\n".join(
        f"- {e['name']} | code: {e['code']} | code_base: {e['code_base']}"
        for e in exercises_ref
    ) if exercises_ref else "No reference available yet."

    muscles_str = "\n".join(f"- {m}" for m in muscles_ref)

    objectives_str = "\n".join(
        f"- {o['code']}: {o['label']}"
        for o in objectives_ref
    ) if objectives_ref else "No objectives available."

    protocol_block = ""
    if protocol:
        sec = ", ".join(protocol.get("obj_secondaires", [])) or "none"
        protocol_block = f"""
RESEARCH PROTOCOL CONTEXT:
- Description: {protocol.get("description", "N/A")}
- Primary objective: {protocol.get("obj_principal", "unknown")}
- Secondary objectives: {sec}

Use the protocol's primary objective as the default objective for each exercise unless the exercise clearly belongs to a secondary objective. Do NOT use objectives outside of the primary and secondary ones listed above.
"""

    return f"""You are a clinical physiotherapy expert. Analyze the following exercise description written by a therapist and extract structured information.
{protocol_block}

EXERCISE DESCRIPTION:
"{text}"

REFERENCE EXERCISES (use these codes if the exercise matches):
{exercises_str}

MUSCLES — you MUST only use muscles from this list:
{muscles_str}

VALID CODE_BASE VALUES: Push, Pull, Transfer, Balance, Stretch, Cardio, Functional, unknown

THERAPEUTIC OBJECTIVES — assign the most relevant code(s) from this list, or "unknown":
{objectives_str}

INSTRUCTIONS:
- Extract all exercises mentioned in the description.
- For each exercise return a JSON array with these exact fields:
  - exercise_name: standardized English name
  - code: short code (3-4 chars). Use reference if available, otherwise generate one.
  - code_base: one of the valid values above only, or "unknown"
  - muscles: list of primary muscles — ONLY from the provided muscle list above
  - assistance: description of any assistance mentioned, or null
  - series: number of sets if mentioned, otherwise null
  - repetitions: number of repetitions per set if mentioned, otherwise null
  - time: duration in seconds if mentioned, otherwise null
  - objective: the most relevant therapeutic objective code from the list above, or "unknown"

IMPORTANT: Return ONLY a valid JSON array. No explanation. No markdown. No code blocks.

Example:
[{{"exercise_name": "Knee locking", "code": "KnL", "code_base": "Push", "muscles": ["Quadriceps femoris", "Vastus medialis"], "assistance": "parallel bars", "series": 3, "repetitions": 10, "time": null, "objective": "STR"}}]"""


def _parse_response(raw: str, muscles_ref: list[str]) -> list[dict]:
    """Parses and validates a raw JSON string from any provider."""
    # Strip markdown code blocks if present
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()

    # Find JSON array start
    if not raw.startswith("["):
        start = raw.find("[")
        if start != -1:
            raw = raw[start:]

    exercises = json.loads(raw)

    # Filter non-dict elements
    exercises = [ex for ex in exercises if isinstance(ex, dict)]

    # Validate and normalize
    for ex in exercises:
        ex["code_base"] = validate_code_base(ex.get("code_base", ""))
        ex["objective"] = validate_objective_code(ex.get("objective", ""))
        ex["series"] = ex.get("series") or None
        ex["repetitions"] = ex.get("repetitions") or None
        ex["time"] = ex.get("time") or None
        ex["assistance"] = ex.get("assistance") or None
        ex["muscles"] = [
            m for m in (ex.get("muscles") or [])
            if m in muscles_ref
        ]

    return exercises


def _call_mistral(model: str, prompt: str, muscles_ref: list[str]) -> list[dict]:
    """Calls Mistral API and parses the response."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not found in .env file.")

    from mistralai.client import Mistral
    client = Mistral(api_key=MISTRAL_API_KEY)
    max_retries = 3
    raw = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Mistral/{model}] attempt {attempt}: {prompt[:80]}...")

            def _fetch():
                response = client.chat.complete(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content.strip()

            raw, cached = prompt_cache.get_or_fetch("Mistral", model, prompt, _fetch)
            logger.info(f"[Mistral/{model}] raw response ({'cache' if cached else 'api'}): {raw[:200]}")
            exercises = _parse_response(raw, muscles_ref)
            audit_logger.log_call("extractor", "Mistral", model, prompt, raw, parsed=exercises,
                                  metadata={"cache_hit": cached})
            logger.info(f"[Mistral/{model}] extracted {len(exercises)} exercises.")
            return exercises
        except json.JSONDecodeError as e:
            logger.warning(f"[Mistral/{model}] attempt {attempt} invalid JSON: {e} — raw: {raw[:200]}")

    logger.error(f"[Mistral/{model}] all {max_retries} attempts failed.")
    return _fallback()


def _call_anthropic(model: str, prompt: str, muscles_ref: list[str]) -> list[dict]:
    """Calls Anthropic Claude API and parses the response."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in .env file.")

    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    max_retries = 3
    raw = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Anthropic/{model}] attempt {attempt}: {prompt[:80]}...")

            def _fetch():
                response = client.messages.create(
                    model=model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            raw, cached = prompt_cache.get_or_fetch("Anthropic", model, prompt, _fetch)
            logger.info(f"[Anthropic/{model}] raw response ({'cache' if cached else 'api'}): {raw[:200]}")
            exercises = _parse_response(raw, muscles_ref)
            audit_logger.log_call("extractor", "Anthropic", model, prompt, raw, parsed=exercises,
                                  metadata={"cache_hit": cached})
            logger.info(f"[Anthropic/{model}] extracted {len(exercises)} exercises.")
            return exercises
        except json.JSONDecodeError as e:
            logger.warning(f"[Anthropic/{model}] attempt {attempt} invalid JSON: {e} — raw: {raw[:200]}")

    logger.error(f"[Anthropic/{model}] all {max_retries} attempts failed.")
    return _fallback()


def _fallback() -> list[dict]:
    return [{
        "exercise_name": "unknown",
        "code": "UNK",
        "code_base": "unknown",
        "objective": "unknown",
        "muscles": [],
        "assistance": None,
        "series": None,
        "repetitions": None,
        "time": None,
    }]


def extract_exercises(text: str, model: str = "open-mistral-7b", provider: str = "Mistral", protocol: dict = None) -> list[dict]:
    """
    Extracts and standardizes exercises from free text using the selected AI provider.
    """
    exercises_ref = load_exercises()
    muscles_ref = get_muscles_latin_list()
    objectives_ref = get_objectives_list()
    prompt = _build_prompt(text, exercises_ref, muscles_ref, objectives_ref, protocol=protocol)

    if provider == "Anthropic":
        return _call_anthropic(model, prompt, muscles_ref)
    else:
        return _call_mistral(model, prompt, muscles_ref)
