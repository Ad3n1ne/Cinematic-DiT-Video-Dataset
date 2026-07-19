# Cinematic DiT Video Dataset

Construction code and release documentation for the
[Cinematic DiT Video Dataset](https://huggingface.co/datasets/Tsu7am1/Cinematic-DiT-Video-Dataset).

The dataset contains 9,000 synthetic text-to-video samples generated from 3,000
cinematic prompts across three generation profiles. The release is designed for
non-commercial research on AI-generated video detection, media forensics,
authenticity analysis, and content-safety evaluation.

The video payload is hosted on Hugging Face as a gated dataset with manual
access approval. This GitHub repository does not contain the videos, API keys,
private logs, account files, or large tar shards.

## Dataset

- Hugging Face: <https://huggingface.co/datasets/Tsu7am1/Cinematic-DiT-Video-Dataset>
- Samples: 9,000 generated MP4 videos
- Prompts: 3,000 source prompt groups
- Packaging: 30 uncompressed tar shards
- Metadata preview: `metadata.parquet`
- License: Research and Content Safety Use License

## Repository Contents

```text
docs/
  dataset_card.md                 # Hugging Face dataset card source
  data_access.md                  # Gated access and usage notes
scripts/
  build_metadata.py               # Build metadata and checksums
  make_shards.py                  # Package MP4 files into tar shards
  validate_dataset.py             # Validate tasks, states, and videos
  validate_staging.py             # Validate staged release files
  probe_videos.sh                 # ffprobe helper
worker/
  generate_tasks.py               # Expand prompts into generation tasks
  prompt_enhancer.py              # Photorealistic prompt enhancement
  summarize.py                    # Progress summarization
examples/
  inspect_metadata.py             # Minimal metadata loading example
```

The public repository intentionally omits production API-calling workers,
credential handling, private runtime logs, and provider-specific operational
configuration. The included code focuses on dataset construction logic,
metadata, validation, packaging, and documentation.

## Access

The dataset is publicly visible on Hugging Face, but file access is gated and
requires manual approval. Access is limited to non-commercial research in
AI-generated video detection, media forensics, authenticity analysis, and
content-safety evaluation.

See [docs/data_access.md](docs/data_access.md) and the dataset
[LICENSE](LICENSE) before requesting access.

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

## Credits

Project lead and dataset maintainer: **Tsu7am1**

Core contributions:

- Dataset concept and research positioning
- Prompt taxonomy and photorealistic prompt pipeline
- Resumable generation worker and task orchestration
- Failure recovery, validation, metadata construction, and release packaging
- Dataset card, restricted-access release, and project documentation

Acknowledgements:

- [MarcoDJS](https://github.com/MarcoDJS) for research feedback and operational
  support.
- [pity11](https://github.com/pity11) for research feedback and operational
  support.
- [ptilopsises](https://github.com/ptilopsises) for research feedback and
  operational support.

## Security

Do not commit credentials, API keys, Hugging Face tokens, account mappings,
private logs, generated videos, or release shards to this repository. The
included `.gitignore` blocks the expected sensitive and large-file paths, but it
is still the maintainer's responsibility to review changes before publishing.
