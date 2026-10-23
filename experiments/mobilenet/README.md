# Optional MobileNet training experiment

The live application uses zero-shot CLIP, not this TensorFlow model. Training is
not required for a mechanical mount change. This older experiment is retained
separately because its `.keras` output is not consumed by `live_smart_bin.py`.
Install TensorFlow and matplotlib separately if you choose to use it. Run from
the intended dataset/output working directory; outputs and labels are written
there. Normal HTTPS certificate verification is enabled.
