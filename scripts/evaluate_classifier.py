"""Measure image-level accuracy and rejection coverage on a labelled holdout set."""
import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
from live_smart_bin import ClipClassifier, build_prompt_groups, prediction_is_eligible


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path, help='Folders paper/plastic/metal/food/unknown containing held-out images')
    parser.add_argument('--output', type=Path, required=True, help='Directory for predictions.csv and summary.json')
    parser.add_argument('--threshold', type=float, default=.60)
    parser.add_argument('--margin', type=float, default=.15)
    parser.add_argument('--cpu-threads', type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    if not 0 < args.threshold <= 1 or not 0 <= args.margin <= 1:
        parser.error('Invalid threshold or margin')
    labels = list(build_prompt_groups())
    images = [(label, path) for label in labels for path in sorted((args.dataset/label).rglob('*'))
              if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}]
    if not images:
        parser.error('No labelled images found; no evaluation or accuracy claim can be made.')
    model = ClipClassifier(cpu_threads=args.cpu_threads)
    rows = []
    for truth, path in images:
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError(f'Cannot read {path}; evaluation stopped rather than skipping it.')
        predicted, score, probabilities = model.predict(frame)
        ordered = sorted(probabilities.values(), reverse=True)
        accepted = prediction_is_eligible(predicted, probabilities, args.threshold, args.margin)
        rows.append(dict(image=str(path), truth=truth, predicted=predicted, score=score,
                         margin=ordered[0]-ordered[1], decision=predicted if accepted else 'manual'))
    accepted = [row for row in rows if row['decision'] != 'manual']
    summary = {
        'images': len(rows), 'threshold': args.threshold, 'margin': args.margin,
        'raw_top1_accuracy': sum(r['truth'] == r['predicted'] for r in rows)/len(rows),
        'automatic_coverage': len(accepted)/len(rows),
        'accepted_accuracy': sum(r['truth'] == r['decision'] for r in accepted)/len(accepted) if accepted else None,
        'by_true_class': {label: {decision: sum(r['truth'] == label and r['decision'] == decision for r in rows)
                                  for decision in labels[:-1] + ['manual']} for label in labels},
        'missing_classes': [label for label in labels if not any(r['truth'] == label for r in rows)],
        'note': 'Image-level results only. Runtime also requires consecutive stable predictions. No hardware delivery test.',
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'predictions.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
