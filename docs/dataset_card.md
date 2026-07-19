---
language:
  - zh
  - en
pretty_name: Cinematic DiT Video Dataset
size_categories:
  - 1K<n<10K
source_datasets:
  - original
annotations_creators:
  - machine-generated
language_creators:
  - expert-generated
multilinguality:
  - multilingual
tags:
  - video
  - webdataset
  - synthetic
  - text-to-video
  - dit
license: other
configs:
  - config_name: default
    data_files:
      - split: train
        path: "metadata.parquet"
---

# Cinematic DiT Video Dataset

> Access is restricted. This dataset is intended for non-commercial research on
> AI-generated video detection, media forensics, authenticity analysis, and
> content-safety evaluation. Access requests should be reviewed manually.

## Dataset Summary

This dataset contains 9,000 synthetic text-to-video samples generated from
3,000 Chinese cinematic prompts. Each source prompt has one video in each of
three generation profiles. The prompt pipeline emphasizes photorealistic,
documentary-like footage and suppresses painterly, CGI, overly stylized, and
beautified output tendencies.

The dataset is intended for DiT-oriented generated-video detection research,
controlled synthetic-data experiments, media forensics, and analysis of the gap
between generated video and real-world visual dynamics. It is not presented as
real camera footage.

## Dataset Details

- Videos: 9,000 MP4 files
- Source prompts: 3,000
- Prompt organization: 300 scene categories x 10 shot designs
- Generation model: `agnes-video-v2.0`
- Generation interface: Agnes Video V2.0 API
- Language: Chinese scene descriptions with English photorealism anchors
- Video payload size: 57.945 GiB
- Repository package size: 30 uncompressed tar shards, approximately 58.003 GiB

The 10 shot designs combine camera platform, motion, framing, and capture
style, for example handheld close tracking, drone overhead movement, static
tripod framing, Steadicam orbiting, and high-speed camera shots.

The profile names are dataset labels rather than claims that the encoded files
match broadcast-standard 1080p/720p/480p geometry. The Agnes API normalizes
requested dimensions to backend-supported encoded sizes before returning the
video. The exact normalization behavior is provider-defined, so public metadata
records both requested values and `ffprobe`-measured encoded values. Researchers
should use the actual metadata fields for preprocessing and avoid treating
profile-specific aspect ratios as semantic signals.

| Profile | Requested size | Actual encoded size | Frames | FPS | Duration |
|---------|----------------|---------------------|--------|-----|----------|
| 1080p | 1920x1080 | 1920x1088 | 169 | 24 | 7.041667 s |
| 720p | 1152x768 | 1088x832 | 409 | 24 | 17.041667 s |
| 480p | 640x480 | 704x512 | 961 | 24 | 40.041667 s |

The three videos associated with one prompt are independent generations. They
are not spatially or temporally aligned versions of the same source video.

## Repository Structure

```text
README.md
LICENSE
metadata.parquet
metadata.csv
metadata.jsonl
prompts.csv
checksums.sha256
shard_index.json
validation_report.json
shards/
  train-00000.tar
  ...
  train-00029.tar
```

Each tar stores MP4 files under `videos/<task_id>.mp4`. The `shard` and
`file_name` columns identify the containing tar and path inside that tar.

The Hugging Face Dataset Viewer is configured to preview `metadata.parquet`.
The MP4 payloads are distributed through the tar shards listed in the metadata,
because the Hub viewer may not reliably infer large WebDataset tar archives.

## Metadata

Important columns include:

| Field | Description |
|-------|-------------|
| `task_id` | Unique video sample identifier |
| `prompt_id` | Unique source-prompt identifier, `0..2999` |
| `global_id` | Unique source-prompt identifier, `0..2999` |
| `category` | Chinese scene category |
| `resolution` | Requested generation profile |
| `prompt_zh` | Chinese prompt variant used for this video |
| `enhanced_prompt` | Photorealism-enhanced prompt submitted for generation |
| `negative_prompt` | Negative prompt submitted for generation |
| `requested_width`, `requested_height` | API request dimensions |
| `actual_width`, `actual_height` | Encoded MP4 dimensions from `ffprobe` |
| `num_frames` | Generation frame count for the profile |
| `actual_frame_rate` | Encoded frame rate from `ffprobe` |
| `actual_duration_seconds` | Encoded duration from `ffprobe` |
| `file_size`, `sha256` | Integrity metadata for the MP4 |
| `shard`, `file_name` | Published tar and tar-internal video path |

`prompts.csv` contains one row per source prompt and links each prompt to its
three video task IDs. Its `prompt_zh` field contains the canonical prompt text
for the prompt group, while `prompt_variants_json` records all source or repair
variants observed for that group. Seven prompt groups contain two variants after
repair. Per-video metadata preserves the prompt variant actually used for that
video.

## Generation and Repair Pipeline

The construction pipeline includes atomic task assignment, per-credential rate
limiting, retry with backoff, resumable state files, failure classification,
download verification, and post-run hole repair. Every prompt passes through a
deterministic enhancement stage that removes style-triggering camera color terms
and adds photorealistic positive and negative constraints.

After the main run, failed samples were audited by task ID. Ninety-nine failures
were retried without prompt changes. Persistent content-policy failures were
generated successfully with more neutral wording where needed. The resulting
canonical prompt groups and their variants are integrated into `prompts.csv`;
the per-video metadata preserves the actual generation prompt for
reproducibility.

## Validation

- 9,000 task records, completed states, and MP4 files
- No missing, extra, empty, or unfinished samples
- 9,000/9,000 MP4 files readable by `ffprobe`
- Exactly 3,000 videos for each generation profile
- Encoded frame rate is 24 FPS for every video
- Encoded frame counts are 169, 409, and 961 for the three profiles
- SHA-256 recorded for every video and every shard
- 18 review samples inspected across six prompts and all three profiles

## Intended Uses

- Training, validating, and benchmarking AI-generated video detectors
- Studying synthetic-to-real distribution gaps for media authenticity research
- Analyzing temporal consistency, generation artifacts, and forensic signals
- Content-safety, provenance, and authenticity evaluation
- Reproducing fault-tolerant synthetic dataset construction workflows

## Prohibited Uses

- Training, fine-tuning, distilling, or evaluating text-to-video, image-to-video,
  video-to-video, or other generative video models
- Commercial use or incorporation into commercial products or services
- Rehosting, mirroring, redistributing, sublicensing, or repackaging the videos
  or shards outside the approved Hugging Face access mechanism
- Creating, improving, or distributing deceptive, impersonating, or harmful
  synthetic media
- Presenting generated videos as real-world recordings or evidence of real
  events

## Limitations and Risks

- Every video is machine-generated and may contain physical, semantic, temporal,
  anatomical, text-rendering, or camera-motion artifacts.
- Photorealistic prompting does not make the samples equivalent to real footage.
- All samples come from a single closed-source generation model. Detectors
  trained only on this dataset may overfit model-specific artifacts, encoder
  behavior, prompt style, or resolution-profile geometry, and may require domain
  adaptation before generalizing to other video generators.
- The prompt taxonomy is manually designed and does not represent all Chinese
  language use, cultures, locations, people, or filming styles.
- Generated people, brands, text, faces, and scenes may accidentally resemble
  real entities or protected material. Users should perform their own review for
  their intended jurisdiction and use case.
- Independent multi-resolution generations must not be treated as aligned video
  triplets for super-resolution evaluation.
- The dataset should not be used to misrepresent generated footage as authentic
  evidence or recordings of real events.

## Access and License

The dataset is distributed under the accompanying Research and Content Safety
Use License. This is a restricted research license, not an open-source or
open-data license.

Access should be granted through Hugging Face gated access with manual approval.
Applicants should describe their research purpose and agree to the license
before receiving file access. The maintainers may deny, revoke, or pause access
when a request is outside the intended scope, when misuse is suspected, or when
needed to respond to a rights-holder or platform request.

This license grants only the rights that the dataset maintainers can grant. It
does not override third-party rights, platform terms, provider terms, or
applicable law. Users are responsible for confirming that their intended use is
allowed in their jurisdiction and under any terms that apply to their work.

## Project Leadership and Contributions

Project lead and dataset creator: **Tsu7am1**

Responsibilities: project conception, prompt taxonomy, photorealistic prompt
pipeline, worker architecture, generation operations, failure recovery, quality
control, metadata design, release packaging, and documentation.

## Citation

```bibtex
@dataset{tsu7am1_2026_cinematic_dit_video,
  author    = {Tsu7am1},
  title     = {Cinematic DiT Video Dataset},
  year      = {2026},
  publisher = {Hugging Face},
  version   = {1.0.0},
  url       = {https://huggingface.co/datasets/Tsu7am1/Cinematic-DiT-Video-Dataset}
}
```

## Related Resources

- Construction code: https://github.com/Ad3n1ne/Cinematic-DiT-Video-Dataset
- Stable release and DOI: not assigned yet
- Contact: Hugging Face user `Tsu7am1`
