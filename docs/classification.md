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

Every detected item now gets a best-match label among the four supported bins,
even when the internal unsupported/unknown score is larger. In that case the
interface displays **Best guess** and does not pretend the result is reliable.
Scores are not renormalised to hide unsupported evidence. Empty-scene detection
still controls whether there is an item to classify; this does not label every
empty video frame as trash.

A physical sort requires all of the following:

- The selected bin beats all other classes, including the internal unknown group.
- Its relative softmax score is at least `--threshold` (default 0.60).
- Its lead over the second-best class, including unknown, is at least `--margin`
  (default 0.15).
- It wins `--stable-frames` consecutive eligible classifications (default 3).

A rejected prediction clears the stability history. The motors are not
commanded for that prediction and the interface displays the uncertain best guess.
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

## Alternative pretrained backend without training

The cached baseline remains CLIP. `--model siglip2` selects Google's official
`google/siglip2-base-patch16-224` checkpoint, using built-in Transformers code
and safetensors weights. This requires no local training. The first run downloads
a separate checkpoint and processor; allow additional disk space and startup
time. It is a comparison candidate, not a demonstrated accuracy improvement
for these bins. Its CPU latency and power requirements on the Pi still need
measurement after the known power issue is resolved.

```sh
./venv/bin/python live_smart_bin.py --driver sim --model siglip2 --cpu-threads 1
```

Both backends encode prompts separately and use class prompt ensembles. Images
are padded to square before model preprocessing so the centre crop retains
both ends of a wide/tall item. This is a preprocessing hypothesis to evaluate,
not an accuracy guarantee. SigLIP 2 uses its prescribed max-length text padding.
The backend's learned scale is used for relative softmax choice scores. These
are neither calibrated accuracy probabilities nor SigLIP's native independent
image/text sigmoid scores. Thresholds need separate validation per backend.

Compare both on the same untouched images and separate output folders:

```sh
./venv/bin/python scripts/evaluate_classifier.py /path/to/holdout --model clip --output /tmp/clip-results
./venv/bin/python scripts/evaluate_classifier.py /path/to/holdout --model siglip2 --output /tmp/siglip2-results
```

With forced four-way labels, unsupported examples cannot have a correct raw
four-way prediction; assess their rejection in the class-by-decision table.
Do not force sorting just to obtain a higher automatic coverage figure.

References: [Google model card](https://huggingface.co/google/siglip2-base-patch16-224),
[Transformers SigLIP 2 documentation](https://huggingface.co/docs/transformers/model_doc/siglip2).
