#!/usr/bin/env bash
# Testa/calibra um encoder: extrai os primeiros 60s de um vídeo, salva o
# trecho bruto e o trecho reencodado com as configs passadas, e imprime uma
# linha RESULTADO com o bpp/velocidade REAIS medidos no encode — usado pelo
# backend pra calibrar a estimativa de analyze-video-bloat.py e o encoder
# real de transcode-1080p-hevc.sh, em vez de constantes hardcoded.
#
# Mesma lógica de $SCALE e dos ramos de encoder de transcode-1080p-hevc.sh
# (replicada aqui, não importada — script pequeno, evita complexidade de
# source-ar bash entre dois pontos de entrada diferentes). Mudanças num
# devem ser espelhadas no outro.
#
# Uso:
#   sample-test.sh <video_entrada> <pasta_saida> --encoder cpu|nvenc
#                  --quality N [--resolution N] [--fps N]
#
# Exemplo:
#   sample-test.sh /mnt/data/jellyfin/movies/filme.mkv /mnt/data/jellyfin/tmp \
#     --encoder nvenc --quality 26 --resolution 1080 --fps 30

set -uo pipefail

INPUT=""
OUTDIR=""
ENCODER="cpu"
QUALITY=24
RESOLUTION=1080
FPS=30
SAMPLE_SECONDS=60

while [[ $# -gt 0 ]]; do
  case "$1" in
    --encoder) ENCODER="$2"; shift 2 ;;
    --quality) QUALITY="$2"; shift 2 ;;
    --resolution) RESOLUTION="$2"; shift 2 ;;
    --fps) FPS="$2"; shift 2 ;;
    *)
      if [[ -z "$INPUT" ]]; then INPUT="$1"; else OUTDIR="$1"; fi
      shift ;;
  esac
done

if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
  echo "Erro: vídeo de entrada não encontrado: $INPUT" >&2
  exit 1
fi
if [[ -z "$OUTDIR" || ! -d "$OUTDIR" ]]; then
  echo "Erro: pasta de saída não encontrada: $OUTDIR" >&2
  exit 1
fi
case "$ENCODER" in
  cpu)   encoder_label="libx265"; quality_label="crf" ;;
  nvenc) encoder_label="nvenc";   quality_label="cq" ;;
  *) echo "Erro: --encoder deve ser cpu ou nvenc (recebido: $ENCODER)" >&2; exit 1 ;;
esac

LONG_EDGE=$(awk "BEGIN{printf \"%d\", $RESOLUTION * 16 / 9}")
SCALE="scale='if(gte(iw,ih),min($LONG_EDGE,iw),min($RESOLUTION,iw))':'if(gte(iw,ih),min($RESOLUTION,ih),min($LONG_EDGE,ih))':force_original_aspect_ratio=decrease"

base=$(basename "$INPUT")
name_noext="${base%.*}"
raw_out="$OUTDIR/${name_noext}.original-${SAMPLE_SECONDS}s.mkv"
encoded_out="$OUTDIR/${name_noext}.${encoder_label}-${RESOLUTION}p-${FPS}fps-${quality_label}${QUALITY}.mkv"

echo "Extraindo os primeiros ${SAMPLE_SECONDS}s de $INPUT..."
rm -f "$raw_out"
if ! ffmpeg -hide_banner -loglevel error -y -ss 0 -t "$SAMPLE_SECONDS" -i "$INPUT" \
    -map 0 -map -0:d -c copy "$raw_out" || [[ ! -s "$raw_out" ]]; then
  echo "Erro: falha ao extrair o trecho de ${SAMPLE_SECONDS}s" >&2
  exit 1
fi
echo "Trecho bruto salvo em: $raw_out"

fps_raw=$(ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of csv=p=0 "$raw_out" 2>/dev/null)
src_fps=$(python3 -c "n,d=('${fps_raw:-0/1}'+'/1').split('/')[:2]; print(float(n)/float(d) if float(d) else 0)" 2>/dev/null || echo 0)
FPS_ARGS=()
if awk "BEGIN{exit !($src_fps >= $FPS * 1.5)}" 2>/dev/null; then
  FPS_ARGS=(-r "$FPS")
fi

echo "Reencodando o trecho com $ENCODER ($quality_label=$QUALITY, ${RESOLUTION}p, ${FPS}fps)..."
rm -f "$encoded_out"
start=$(date +%s.%N)
if [[ "$ENCODER" == "nvenc" ]]; then
  ffmpeg -hide_banner -loglevel error -y -i "$raw_out" -map 0 -map -0:d -c copy \
    -vf "$SCALE" -c:v hevc_nvenc -rc vbr -cq "$QUALITY" -b:v 0 "${FPS_ARGS[@]}" \
    "$encoded_out"
  ok=$?
else
  ffmpeg -hide_banner -loglevel error -y -i "$raw_out" -map 0 -map -0:d -c copy \
    -vf "$SCALE" -c:v libx265 -preset medium -crf "$QUALITY" "${FPS_ARGS[@]}" \
    "$encoded_out"
  ok=$?
fi
end=$(date +%s.%N)

if [[ $ok -ne 0 || ! -s "$encoded_out" ]]; then
  echo "Erro: falha ao reencodar o trecho" >&2
  exit 1
fi
echo "Trecho reencodado salvo em: $encoded_out"

wall_seconds=$(awk "BEGIN{print $end - $start}")

python3 - "$encoded_out" "$wall_seconds" <<'PYEOF'
import json
import subprocess
import sys

encoded_out, wall_seconds = sys.argv[1], float(sys.argv[2])

out = subprocess.run(
    ["ffprobe", "-v", "error", "-print_format", "json",
     "-show_entries", "format=duration,size",
     "-show_entries", "stream=width,height,bit_rate,avg_frame_rate",
     "-select_streams", "v:0", encoded_out],
    capture_output=True, text=True,
)
data = json.loads(out.stdout)
fmt = data["format"]
stream = data["streams"][0]

duration = float(fmt["duration"])
size = int(fmt["size"])
width = int(stream["width"])
height = int(stream["height"])

bit_rate = stream.get("bit_rate")
bit_rate = int(bit_rate) if bit_rate else size * 8 / duration

num, den = (stream.get("avg_frame_rate") or "0/1").split("/")
fps = float(num) / float(den) if float(den) else 0
if not fps:
    fps = 24.0  # avg_frame_rate ausente/inválido — não deveria acontecer num arquivo válido

bpp = bit_rate / (width * height * fps)
speed_factor = duration / wall_seconds

print(f"RESULTADO bpp={bpp:.6f} speed_factor={speed_factor:.3f} "
      f"encoded_bytes={size} encoded_duration={duration:.2f}")
PYEOF
