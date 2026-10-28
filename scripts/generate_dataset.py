"""Create independent reproducible train/eval CSVs and detector evaluation."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from ledgershield.evidence import Detector, dataset

if __name__ == "__main__":
    output = Path("artifacts/datasets")
    output.mkdir(parents=True, exist_ok=True)
    detector = Detector(seed=101)
    for split, seed in (("train", 101), ("evaluation", 202)):
        x, y = dataset(seed)
        np.savetxt(output / f"{split}.csv", np.column_stack((x, y)), delimiter=",",
                   header="invalid_vote_rate,timeout_rate,latency_fraction,label", comments="")
    x, y = dataset(202)
    predictions = detector.model.predict(x) == -1
    results = {"training_seed": 101, "evaluation_seed": 202,
               "train_normal_only": True, "evaluation_rows": len(y),
               "true_positives": int(sum(predictions & (y == 1))),
               "false_positives": int(sum(predictions & (y == 0))),
               "true_negatives": int(sum(~predictions & (y == 0))),
               "false_negatives": int(sum(~predictions & (y == 1)))}
    (output / "evaluation.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))
