import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import logger
from exercise_extractor import extract_exercises
from reviewer_agent import review_exercises
from synthesis_agent import synthesize_session

MAX_RETRIES = 2

# Parallelism for extract+review per row. Mistral free tier = 1 req/sec,
# Anthropic much higher. 5 workers is safe for most cases; override via env.
DEFAULT_WORKERS = int(os.environ.get("LOBSTER_WORKERS", "5"))


def _extract_and_review(
    text: str,
    model: str,
    provider: str,
    protocol: dict | None,
) -> tuple[list[dict], str, float]:
    """
    Runs Agent 1 (extractor) + Agent 2 (reviewer) with the retry loop.
    Returns: (exercises, decision, confidence)
    """
    exercises = extract_exercises(text, model=model, provider=provider, protocol=protocol)
    decision = "approved"
    confidence = 1.0

    for attempt in range(1, MAX_RETRIES + 1):
        review = review_exercises(text, exercises, model=model, provider=provider, protocol=protocol)
        decision = review.get("decision", "approved")
        confidence = review.get("confidence", 1.0)
        issues = review.get("issues", [])

        if decision == "approved":
            exercises = review["exercises"] or exercises
            break
        elif decision == "corrected":
            exercises = review["exercises"] or exercises
            break
        elif decision == "rejected" and attempt < MAX_RETRIES:
            feedback = f"Previous extraction was rejected: {'; '.join(issues)}. Please try again more carefully."
            exercises = extract_exercises(
                text + f"\n\n[FEEDBACK FROM REVIEWER]: {feedback}",
                model=model, provider=provider, protocol=protocol,
            )
        else:
            exercises = review["exercises"] or exercises
            break

    return exercises, decision, confidence


def _format_exercise_rows(
    exercises: list[dict],
    patient_id: str,
    session: str,
    exercise_num_start: int,
    protocol: dict | None,
    decision: str,
    confidence: float,
) -> tuple[list[dict], list[dict]]:
    """
    Formats exercises into (rows_for_output, exercises_for_synthesis).
    Handles protocol-based objective fallback and top-3 muscle trimming.
    """
    protocol_obj_principal = protocol.get("obj_principal", "") if protocol else ""
    protocol_obj_secondaires = ", ".join(protocol.get("obj_secondaires", [])) if protocol else ""
    valid_protocol_objectives = (
        {protocol_obj_principal} | set(protocol.get("obj_secondaires", []))
        if protocol else set()
    )

    rows = []
    for i, ex in enumerate(exercises):
        objective = ex.get("objective", "unknown")
        if protocol and (objective == "unknown" or objective not in valid_protocol_objectives):
            objective = protocol_obj_principal

        muscles = ex.get("muscles", [])[:3]

        rows.append({
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

    return rows, exercises


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
    Runs the 3-agent pipeline for a single session row (sequential).
    Kept for backward compatibility and single-row use cases.

    Returns:
        - formatted exercise rows (list[dict])
        - per-session synthesis (dict)
    """
    logger.info(f"[Orchestrator] Agent 1+2 — extract+review: {text[:60]}...")
    exercises, decision, confidence = _extract_and_review(text, model, provider, protocol)

    print(f"    [Review] decision={decision}, confidence={confidence:.2f}")

    rows, exercises_for_synth = _format_exercise_rows(
        exercises, patient_id, session, exercise_num_start, protocol, decision, confidence,
    )

    logger.info(f"[Orchestrator] Agent 3 — synthesizing session '{session}'")
    synthesis = synthesize_session(patient_id, session, exercises_for_synth,
                                   model=model, provider=provider, protocol=protocol)
    return rows, synthesis


def orchestrate(
    df: pd.DataFrame,
    patient_id: str,
    session_col: str | None,
    exercise_col: str,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    protocol: dict = None,
    max_workers: int = DEFAULT_WORKERS,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Orchestrates the full pipeline over all rows of a DataFrame.

    Two phases:
      Phase 1 — parallel extract+review per row (ThreadPoolExecutor, `max_workers` concurrent)
      Phase 2 — parallel synthesis per session (one Agent 3 call per unique session)

    Returns:
        - exercises_df: structured exercise DataFrame
        - syntheses: list of per-session clinical summaries
    """
    if protocol:
        print(f"\n  [Protocol] {protocol.get('description', '')}")
        print(f"  [Protocol] obj_principal={protocol.get('obj_principal')} | obj_secondaires={', '.join(protocol.get('obj_secondaires', []))}")

    # Build work items (idx → session, text)
    work_items = []
    for idx, row in df.iterrows():
        session = str(row[session_col]) if session_col and session_col in df.columns else f"session_{idx + 1}"
        text = str(row[exercise_col])
        if not text or text.lower() in ("nan", "none", ""):
            continue
        work_items.append((idx, session, text))

    if not work_items:
        return pd.DataFrame(), []

    print(f"\n  [Orchestrator] Phase 1 — extract+review ({len(work_items)} rows, {max_workers} workers)")

    # ── Phase 1: parallel extract+review ───────────────────────────────────────
    row_results = {}  # idx → (exercises, decision, confidence, session, text)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(_extract_and_review, text, model, provider, protocol): (idx, session, text)
            for idx, session, text in work_items
        }
        for future in as_completed(future_to_item):
            idx, session, text = future_to_item[future]
            try:
                exercises, decision, confidence = future.result()
                row_results[idx] = (exercises, decision, confidence, session, text)
                print(f"    [{session}] {text[:60]}... → {decision} ({confidence:.2f})")
            except Exception as e:
                logger.error(f"[Orchestrator] row {idx} failed: {e}")
                print(f"    [{session}] FAILED: {e}")

    # ── Format rows in deterministic order (by original index) ─────────────────
    all_exercise_rows = []
    session_exercise_counter = {}  # session → running count
    exercises_by_session = {}       # session → list of exercises (for synthesis)

    for idx in sorted(row_results.keys()):
        exercises, decision, confidence, session, text = row_results[idx]
        start_num = session_exercise_counter.get(session, 0) + 1
        rows, ex_list = _format_exercise_rows(
            exercises, patient_id, session, start_num, protocol, decision, confidence,
        )
        all_exercise_rows.extend(rows)
        session_exercise_counter[session] = start_num + len(rows) - 1
        exercises_by_session.setdefault(session, []).extend(ex_list)

    # ── Phase 2: parallel synthesis per session ────────────────────────────────
    print(f"\n  [Orchestrator] Phase 2 — synthesis ({len(exercises_by_session)} session(s))")

    syntheses = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_session = {
            executor.submit(
                synthesize_session, patient_id, session, ex_list,
                model=model, provider=provider, protocol=protocol,
            ): session
            for session, ex_list in exercises_by_session.items()
        }
        for future in as_completed(future_to_session):
            session = future_to_session[future]
            try:
                syntheses.append(future.result())
            except Exception as e:
                logger.error(f"[Orchestrator] synthesis failed for '{session}': {e}")

    exercises_df = pd.DataFrame(all_exercise_rows) if all_exercise_rows else pd.DataFrame()
    logger.info(f"[Orchestrator] done — {len(exercises_df)} exercises, {len(syntheses)} session syntheses.")

    return exercises_df, syntheses
