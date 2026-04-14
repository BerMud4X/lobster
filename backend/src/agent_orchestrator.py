import pandas as pd
from logger import logger
from exercise_extractor import extract_exercises
from reviewer_agent import review_exercises
from synthesis_agent import synthesize_session

MAX_RETRIES = 2


def run_agents(
    text: str,
    patient_id: str,
    session: str,
    exercise_num_start: int = 1,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    protocol: dict = None,
) -> tuple[list[dict], dict]:
    """
    Runs the 3-agent pipeline for a single session row.

    Returns:
        - exercises: list of validated exercise dicts
        - synthesis: clinical summary dict
    """
    # ── Agent 1 — Extract ──────────────────────────────────────────────────────
    logger.info(f"[Orchestrator] Agent 1 — extracting from: {text[:60]}...")
    exercises = extract_exercises(text, model=model, provider=provider, protocol=protocol)

    # ── Agent 2 — Review (with retry loop) ────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"[Orchestrator] Agent 2 — review attempt {attempt}/{MAX_RETRIES}")
        review = review_exercises(text, exercises, model=model, provider=provider, protocol=protocol)

        decision = review.get("decision", "approved")
        confidence = review.get("confidence", 1.0)
        issues = review.get("issues", [])

        print(f"    [Review] decision={decision}, confidence={confidence:.2f}")
        if issues:
            print(f"    [Review] issues: {'; '.join(issues)}")

        if decision == "approved":
            exercises = review["exercises"] or exercises
            break
        elif decision == "corrected":
            exercises = review["exercises"] or exercises
            logger.info(f"[Orchestrator] Agent 2 corrected exercises.")
            break
        elif decision == "rejected" and attempt < MAX_RETRIES:
            feedback = f"Previous extraction was rejected: {'; '.join(issues)}. Please try again more carefully."
            logger.warning(f"[Orchestrator] Agent 2 rejected — retrying Agent 1 (attempt {attempt + 1})")
            print(f"    [Review] rejected — retrying extraction...")
            exercises = extract_exercises(
                text + f"\n\n[FEEDBACK FROM REVIEWER]: {feedback}",
                model=model,
                provider=provider,
                protocol=protocol,
            )
        else:
            logger.error(f"[Orchestrator] Agent 2 final rejection after {attempt} attempt(s). Keeping last extraction.")
            exercises = review["exercises"] or exercises
            break

    # Attach exercise numbers, patient/session context, and protocol metadata
    protocol_obj_principal = protocol.get("obj_principal", "") if protocol else ""
    protocol_obj_secondaires = ", ".join(protocol.get("obj_secondaires", [])) if protocol else ""
    valid_protocol_objectives = (
        {protocol_obj_principal} | set(protocol.get("obj_secondaires", []))
        if protocol else set()
    )

    numbered = []
    for i, ex in enumerate(exercises):
        # If objective is unknown or outside protocol, default to obj_principal
        objective = ex.get("objective", "unknown")
        if protocol and (objective == "unknown" or objective not in valid_protocol_objectives):
            objective = protocol_obj_principal

        # Limit to top 3 muscles
        muscles = ex.get("muscles", [])[:3]

        numbered.append({
            "patient_id": patient_id,
            "session": session,
            "exercise_num": exercise_num_start + i,
            "exercise_name": ex.get("exercise_name"),
            "code": ex.get("code"),
            "code_base": ex.get("code_base"),
            "objective": objective,
            "protocol_obj_principal": protocol_obj_principal,
            "protocol_obj_secondaires": protocol_obj_secondaires,
            "muscles": ", ".join(muscles),
            "assistance": ex.get("assistance"),
            "series": ex.get("series"),
            "repetitions": ex.get("repetitions"),
            "time": ex.get("time"),
            "review_decision": decision,
            "review_confidence": confidence,
        })

    # ── Agent 3 — Synthesis ───────────────────────────────────────────────────
    logger.info(f"[Orchestrator] Agent 3 — synthesizing session '{session}'")
    synthesis = synthesize_session(patient_id, session, exercises, model=model, provider=provider, protocol=protocol)

    return numbered, synthesis


def orchestrate(
    df: pd.DataFrame,
    patient_id: str,
    session_col: str | None,
    exercise_col: str,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    protocol: dict = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Orchestrates the 3-agent pipeline over all rows of a DataFrame.

    Returns:
        - exercises_df: structured exercise DataFrame
        - syntheses: list of per-session clinical summaries
    """
    if protocol:
        print(f"\n  [Protocol] {protocol.get('description', '')}")
        print(f"  [Protocol] obj_principal={protocol.get('obj_principal')} | obj_secondaires={', '.join(protocol.get('obj_secondaires', []))}")

    all_exercises = []
    all_syntheses = []
    session_exercise_counter = {}

    for idx, row in df.iterrows():
        session = str(row[session_col]) if session_col and session_col in df.columns else f"session_{idx + 1}"
        text = str(row[exercise_col])

        if not text or text.lower() in ("nan", "none", ""):
            continue

        print(f"\n  [{session}] {text[:60]}...")
        start_num = session_exercise_counter.get(session, 0) + 1

        exercises, synthesis = run_agents(
            text=text,
            patient_id=patient_id,
            session=session,
            exercise_num_start=start_num,
            model=model,
            provider=provider,
            protocol=protocol,
        )

        session_exercise_counter[session] = start_num + len(exercises) - 1
        all_exercises.extend(exercises)

        all_syntheses = [s for s in all_syntheses if s["session"] != session]
        all_syntheses.append(synthesis)

    exercises_df = pd.DataFrame(all_exercises) if all_exercises else pd.DataFrame()
    logger.info(f"[Orchestrator] done — {len(exercises_df)} exercises, {len(all_syntheses)} session syntheses.")

    return exercises_df, all_syntheses
