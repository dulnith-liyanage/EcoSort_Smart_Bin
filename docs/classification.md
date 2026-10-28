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

The default `--routing-policy best-match` physically sorts every detected item
into the best match among the four bins. It averages the four bin scores over
`--stable-frames` observations (default 3) and chooses the largest average,
even if the labels fluctuate or the internal unknown score is higher. Ties use
the category order above. Original match scores remain visible; they are not
renormalised or presented as measured accuracy.

Confidence and margin do not block this default policy. Empty-tray detection,
pause/stop, calibrated routes and cooldown still apply. After a route, the tray
must be visibly empty for more than 12 frames before the next item can trigger
a route. The dashboard displays **Waiting for an empty tray** during this lock.
If an item remains after a dump, remove it before adding the next item. If an
empty tray stays locked, pause and use **Reset empty tray** with the tray empty.
Small or low-contrast objects can still be missed by the presence detector.

For the previous conservative policy, run with `--routing-policy confident`.
It requires the winning bin to beat unknown, score at least `--threshold`
(default 0.60), lead by `--margin` (default 0.15), and win three consecutive
eligible frames. A rejected prediction clears that policy's history.
Space requests a scan; keys 1–4 remain explicit manual bin tests.
Automatic routing returns to level before panning and after dumping.

Forced four-bin selection increases coverage, not proven accuracy. Unsupported
objects will also be assigned a bin and may be misclassified. This prototype
cannot identify hazardous waste reliably; keep hazardous items out of the demo.

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
a separate checkpoint and processor; its weights alone are about 1.5 GB.
Allow additional disk space and startup time. After category embeddings are
cached in memory, the text encoder is released to reduce steady-state RAM use.
Initial loading still needs space for the complete model. It is a comparison
candidate, not a demonstrated accuracy improvement
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
