#!/usr/bin/env bash
set -euo pipefail

input_dir=${1:?usage: probe_videos.sh INPUT_DIR OUTPUT_CSV}
output_csv=${2:?usage: probe_videos.sh INPUT_DIR OUTPUT_CSV}
ffprobe_bin=${FFPROBE_BIN:-ffprobe}
tmp_csv="${output_csv}.tmp"

mkdir -p "$(dirname "$output_csv")"
printf '%s\n' 'task_id,width,height,frame_rate,duration_seconds,num_frames' > "$tmp_csv"

count=0
while IFS= read -r video_path; do
    task_id=$(basename "$video_path" .mp4)
    probe=$(
        "$ffprobe_bin" -v error -select_streams v:0 \
            -show_entries stream=width,height,avg_frame_rate,duration,nb_frames \
            -of compact=p=0:nk=1 "$video_path"
    )
    IFS='|' read -r width height frame_rate duration num_frames <<< "$probe"
    printf '%s,%s,%s,%s,%s,%s\n' \
        "$task_id" "$width" "$height" "$frame_rate" "$duration" "$num_frames" \
        >> "$tmp_csv"
    count=$((count + 1))
    if (( count % 250 == 0 )); then
        printf 'probed %d videos\n' "$count" >&2
    fi
done < <(find "$input_dir" -maxdepth 1 -type f -name '*.mp4' | sort)

mv "$tmp_csv" "$output_csv"
printf 'wrote %s rows to %s\n' "$count" "$output_csv"
