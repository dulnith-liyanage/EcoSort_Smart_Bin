# Image reviews and future training

## On the dashboard

Open **Recent activity** and select a route. New automatic routes save the
classifier crop immediately before motor movement. This is the final observation
in the three-frame decision window, not a picture taken after dumping. The
original prediction, relative match score and route time remain visible.
Choose the actual material and **Save review**. Confirm correct predictions as
well as correcting wrong ones. Reviews do not trigger motors or modify the
running model. Old routes have no historical photo and cannot be image-reviewed.
Manual terminal bin tests do not create these camera review records.

**Today’s material split** counts completed hardware routes for the current
Sri Lankan calendar day, using human labels where available and predictions
otherwise. Paper, rigid plastic and metal are *potentially* recyclable; food is
shown separately as compostable/outside dry recycling. Other/unsupported labels
remain uncertain, not automatically non-recyclable. Reviewed empty-tray events
are excluded from material percentages. No item routes means no percentage.
These are counts, not mass measurements or verified recovery. Contamination and
local collection requirements still determine whether material can be recycled.
Bin counts retain the originally commanded routes, even after a label correction.
Demo data stays separate. History CSV includes review fields alongside originals.

## Storage and privacy

Data lives in `~/.local/share/ecosort-dashboard/` by default: `history.sqlite3`
and a `captures/` directory. No captures or labels are committed to GitHub.
The existing trusted-LAN access restriction applies to images and review APIs.
Do not expose the password-free dashboard directly to the internet.

Image storage is bounded to 500 JPEGs / 64 MiB. Old unreviewed images are pruned
first; if all are reviewed, the oldest retained reviewed image can also expire.
History and labels remain. Export reviews regularly to preserve training images.
Only completed automatic routes receive captures; camera preview frames are not
continually recorded. A missing/unwritable capture must not erase a route record.

## Export and train later

**Download reviewed images & labels** exports a ZIP of retained, human-reviewed
*hardware* captures and `labels.json`. Demo and unreviewed examples are excluded.
Each record includes the original prediction, corrected label, model identifier,
match score and capture/review times. `empty` and `unsupported` are rejection
examples rather than one of the four bin labels. Exporting does not train a model.

Human labels can improve a future model, but one correction does not reliably
teach a class. Collect varied objects for every bin: different brands, shapes,
lighting, orientations and contamination conditions. Avoid keeping only errors;
confirm representative correct predictions too. Check labels carefully.

A practical next experiment is to freeze the pretrained CLIP image encoder and
train a small four-class linear head on its image embeddings, retaining an
empty-tray presence gate. This can use less compute than fine-tuning the whole
vision encoder. Unsupported examples need a separately evaluated rejection
policy; forcing four-bin choice still cannot make all objects correctly belong
to one of those bins.

Before training, manually group captures of the same physical object/session.
Split those groups into training, validation and a held-out test set; never put
multiple views of the same object in both training and test sets. The current
review form does not know object identities, so event IDs alone are not a safe
split. Compare per-class precision/recall, a confusion matrix and end-to-end
sorting results against the current pretrained model on that held-out set.
Keep the current model as a rollback. Deploy a trained candidate only after a
measured improvement; tiny or biased datasets can reduce accuracy.
