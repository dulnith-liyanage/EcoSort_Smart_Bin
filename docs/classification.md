# Four supported waste classes

| Code | Bin | Supported examples |
|---|---|---|
| paper | Front-left | Paper, newspaper, cardboard |
| plastic | Front-right | Rigid plastic bottles, cups, food containers |
| metal | Rear-left | Aluminium drink cans, metal food tins |
| food | Rear-right | Fruit peels and vegetable scraps |

These are deliberately narrower prototype classes. Glass, polythene bags,
foil wrappers, foam, mixed packaging and other waste are outside the supported
set. An internal `unknown` prompt group includes examples of unsupported items,
an empty tray and a hand. It is a rejection cue, not a fifth bin or a guaranteed
open-world/hazardous-waste detector. An unsupported item can still be mistaken
for a supported one; evaluation is required.

## What changed

Each short description is encoded separately with the existing CLIP model.
Normalised prompt embeddings are averaged within each class and normalised
again. The five class embeddings are compared with each image. This replaces
the previous single long list of unrelated objects per class.

A physical sort requires all of the following:

- The winning class is one of the four supported bins, rather than `unknown`.
- Its relative softmax score is at least `--threshold` (default 0.60).
- Its lead over the second-best class, including unknown, is at least `--margin`
  (default 0.15).
- It wins `--stable-frames` consecutive eligible classifications (default 3).

A rejected prediction clears the stability history. The motors are not
commanded for that prediction and the interface asks for manual removal.
Space requests a scan but cannot bypass these checks. Keys 1-4 remain explicit
manual bin tests; they bypass recognition and can move hardware in real-driver
mode. Automatic routing returns to level before panning and after dumping.

The thresholds are initial settings, not calibrated accuracy estimates. Adding
unknown changes the score distribution, so old percentages are not directly
comparable. Raising confidence by changing labels is not proof of improvement.
CLIP has not been retrained; labelled local data is needed before claiming
better accuracy or deciding whether a trained lightweight classifier is needed.

## Try recognition without motor commands

Close the separate camera preview first. On the Pi desktop:

```sh
cd /home/en12/EcoSort_Smart_Bin
./venv/bin/python live_smart_bin.py --driver sim --cpu-threads 1
```

Add `--headless` over SSH. Leave the tray empty during its first 30 frames.
Keep a fixed camera, a plain matte tray, even lighting, one item at a time and
hands out of view. Simulation still uses the real camera and model. The known
power issue must be resolved before real sorting tests.

## Compare results on local photographs

Collect at least 20 different test items per supported class where practical,
with multiple orientations and a separate set of unsupported objects, hands
and empty-tray images. Photograph them with the real tray and lighting. Keep
all views of the same physical item together when dividing development and
holdout sets; neighbouring video frames must not leak between sets.

Use this folder layout outside the repository (images should already crop to
the item/tray area used for recognition):

```text
holdout/
  paper/item_01/view_01.jpg
  plastic/item_01/view_01.jpg
  metal/item_01/view_01.jpg
  food/item_01/view_01.jpg
  unknown/item_01/view_01.jpg
```

Run without any camera or motor access:

```sh
./venv/bin/python scripts/evaluate_classifier.py /path/to/holdout \
  --output /tmp/ecosort-evaluation --cpu-threads 1
```

The output includes per-image decisions, a class-by-decision table, raw top-1
accuracy, automatic coverage and accuracy among accepted predictions. Missing
classes are reported. Image-level results do not verify temporal stability or
actual item delivery. Compare the old and new versions on the same untouched
holdout; tune thresholds on a separate development set, not on the final test
set. More rejection can raise accepted accuracy while reducing coverage, so
report both.

Custom `--prompts-file` JSON accepts current keys (`paper`, `plastic`, `metal`,
`food`, optionally `unknown`) with a string or a list of short descriptions.
Omitted keys retain defaults. Old keys such as `plastic_metal`, `organic` and
`general` are rejected to prevent silently applying outdated labels.
