import json
from pathlib import Path
from datetime import datetime
from logger import logger


class Pipeline:
    """Records all ETL steps and allows replaying them automatically."""

    def __init__(self):
        self.steps = []  # list of recorded steps
        self.created_at = datetime.now().isoformat()

    def record(self, step, params=None):
        """Records a step with its parameters."""
        self.steps.append({
            "step": step,
            "params": params or {}
        })
        logger.info(f"Pipeline step recorded: {step} — {params}")

    def save(self, output_path):
        """Saves the pipeline to a JSON file."""
        data = {
            "created_at": self.created_at,
            "steps": self.steps
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Pipeline saved to: {output_path}")
        print(f"Pipeline saved to: {output_path}")

    @staticmethod
    def load(path):
        """Loads a pipeline from a JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pipeline = Pipeline()
        pipeline.created_at = data["created_at"]
        pipeline.steps = data["steps"]
        logger.info(f"Pipeline loaded: {len(pipeline.steps)} steps from {data['created_at']}")
        print(f"Pipeline loaded: {len(pipeline.steps)} steps from {data['created_at']}")
        return pipeline

    def get(self, step):
        """Returns the params of a recorded step, or None if not found."""
        for s in self.steps:
            if s["step"] == step:
                return s["params"]
        return None

    def has(self, step):
        """Returns True if a step was recorded."""
        return any(s["step"] == step for s in self.steps)
