# Data Access

The Cinematic DiT Video Dataset is hosted on Hugging Face:

<https://huggingface.co/datasets/Tsu7am1/Cinematic-DiT-Video-Dataset>

The repository is publicly visible, but file access is gated with manual
approval. Applicants should describe their research purpose and agree to the
Research and Content Safety Use License before accessing the data files.

## Intended Scope

Access is intended for non-commercial research on:

- AI-generated video detection;
- media forensics and authenticity analysis;
- provenance and content-safety evaluation;
- synthetic-to-real distribution-gap analysis for detection research.

## Not Allowed

The dataset license does not allow:

- training, fine-tuning, distilling, improving, benchmarking, or evaluating
  generative video models;
- commercial use;
- rehosting, mirroring, redistributing, sublicensing, or repackaging the video
  shards;
- presenting generated videos as real-world recordings;
- creating or improving deceptive, impersonating, or harmful synthetic media.

## Files

The Hugging Face Dataset Viewer is configured to preview `metadata.parquet`.
The video payload is stored in `shards/train-*.tar`. Each MP4 can be located
using the `shard` and `file_name` columns in the metadata.

## Notes

The dataset is synthetic and generated from a single closed-source video
generation model. Detectors trained only on this dataset may overfit
model-specific artifacts, encoder behavior, prompt style, or resolution-profile
geometry. Cross-generator evaluation is recommended for claims about
generalization.

