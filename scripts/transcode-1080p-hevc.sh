#!/usr/bin/env bash
# Recodifica em massa uma biblioteca de vídeos para HEVC (H.265), limitando
# o lado curto à resolução-alvo (lado longo escalado mantendo 16:9), mantendo
# áudio/legendas/anexos intactos (copy). Pula arquivos que já estão em HEVC
# dentro do teto de resolução. Detecta VAAPI (Intel Quick Sync) automaticamente
# e cai pra libx265 (CPU) se não tiver acesso à GPU.
#
# Uso:
#   transcode-1080p-hevc.sh <diretorio|arquivo> [--replace] [--dry-run] [--crf N]
#                           [--resolution N] [--fps N]
#
#   <diretorio|arquivo>  pasta raiz (varre recursivamente pasta/subpasta/arquivos)
#                        ou um único arquivo de vídeo (processa só ele)
#   --replace       apaga o original após validar o novo arquivo (senão só
#                   grava "nome.hevc.mkv" do lado do original, sem tocar nele)
#   --dry-run       só lista o que seria convertido/pulado, não roda ffmpeg
#   --crf N         qualidade CPU (libx265), padrão 24. Menor = mais qualidade/maior arquivo.
#   --resolution N  teto do lado curto em pixels, padrão 1080. O lado longo é
#                   derivado mantendo 16:9 (ex: 1080 -> 1920, 720 -> 1280).
#   --fps N         fps-alvo, padrão 30. Só força a taxa quando a fonte está
#                   bem acima do alvo (>= 1.5x), pra não mexer em fontes já ok.
#
# Exemplos:
#   ./transcode-1080p-hevc.sh /mnt/data/filmes --dry-run
#   ./transcode-1080p-hevc.sh /mnt/data/filmes --replace
#   ./transcode-1080p-hevc.sh /mnt/data/filmes --resolution 720 --fps 24
#   ./transcode-1080p-hevc.sh /mnt/data/filmes/filme.mkv --replace

set -uo pipefail

DIR=""
REPLACE=0
DRYRUN=0
CRF=24
RESOLUTION=1080
FPS=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    --replace) REPLACE=1; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    --crf) CRF="$2"; shift 2 ;;
    --resolution) RESOLUTION="$2"; shift 2 ;;
    --fps) FPS="$2"; shift 2 ;;
    *) DIR="$1"; shift ;;
  esac
done

if [[ -z "$DIR" || ( ! -d "$DIR" && ! -f "$DIR" ) ]]; then
  echo "Uso: $0 <diretorio|arquivo> [--replace] [--dry-run] [--crf N] [--resolution N] [--fps N]" >&2
  exit 1
fi

LONG_EDGE=$(awk "BEGIN{printf \"%d\", $RESOLUTION * 16 / 9}")

LOG="$HOME/scripts/transcode-1080p-hevc.$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOG")"
echo "Log: $LOG"

# --- detecta VAAPI real (não só se o encoder existe, mas se abre o device) ---
VAAPI_DEV="/dev/dri/renderD128"
USE_VAAPI=0
if [[ -e "$VAAPI_DEV" ]]; then
  if ffmpeg -hide_banner -init_hw_device "vaapi=va:$VAAPI_DEV" -f lavfi -i "color=black:s=64x64:d=0.1" \
     -vf 'format=nv12,hwupload' -vaapi_device va -c:v hevc_vaapi -f null - >/dev/null 2>&1; then
    USE_VAAPI=1
  fi
fi

if [[ "$USE_VAAPI" -eq 1 ]]; then
  echo "Aceleração: VAAPI (Intel Quick Sync) detectada e funcionando." | tee -a "$LOG"
else
  echo "Aceleração: sem VAAPI utilizável, usando CPU (libx265, crf=$CRF)." | tee -a "$LOG"
fi

echo "Alvo: resolução ${RESOLUTION}p (lado longo ${LONG_EDGE}), fps ${FPS}." | tee -a "$LOG"

SCALE="scale='if(gte(iw,ih),min($LONG_EDGE,iw),min($RESOLUTION,iw))':'if(gte(iw,ih),min($RESOLUTION,ih),min($LONG_EDGE,ih))':force_original_aspect_ratio=decrease"

shopt -s nullglob
if [[ -f "$DIR" ]]; then
  FILES=("$DIR")
else
  mapfile -d '' FILES < <(find "$DIR" -type f \( \
    -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.avi' -o -iname '*.mov' \
    -o -iname '*.wmv' -o -iname '*.flv' -o -iname '*.webm' -o -iname '*.m4v' \
    -o -iname '*.ts' -o -iname '*.m2ts' \) -print0)
fi

TOTAL=${#FILES[@]}
echo "Encontrados $TOTAL arquivo(s) de vídeo em $DIR" | tee -a "$LOG"

CONVERTED=0
SKIPPED=0
FAILED=0
i=0

for f in "${FILES[@]}"; do
  i=$((i+1))
  IFS=',' read -r codec width height fps_raw <<<"$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height,avg_frame_rate -of csv=p=0 "$f" 2>/dev/null)"

  short_edge=$width
  long_edge=$height
  if [[ -n "$width" && -n "$height" && "$width" -gt "$height" ]]; then
    short_edge=$height
    long_edge=$width
  fi

  if [[ "$codec" == "hevc" && -n "$short_edge" && "$short_edge" -le "$RESOLUTION" && "$long_edge" -le "$LONG_EDGE" ]]; then
    echo "[$i/$TOTAL] PULA (já HEVC <=${RESOLUTION}p, considerando orientação): $f" | tee -a "$LOG"
    SKIPPED=$((SKIPPED+1))
    continue
  fi

  dir_f=$(dirname "$f")
  base_f=$(basename "$f")
  name_noext="${base_f%.*}"
  tmp_out="$dir_f/.tmp_${name_noext}.mkv"
  final_out="$dir_f/${name_noext}.hevc.mkv"

  echo "[$i/$TOTAL] CONVERTE ($codec ${width}x${height} -> hevc ${RESOLUTION}p): $f" | tee -a "$LOG"

  if [[ "$DRYRUN" -eq 1 ]]; then
    continue
  fi

  rm -f "$tmp_out"

  fps=$(python3 -c "n,d=('${fps_raw:-0/1}'+'/1').split('/')[:2]; print(float(n)/float(d) if float(d) else 0)" 2>/dev/null || echo 0)
  FPS_ARGS=()
  if awk "BEGIN{exit !($fps >= $FPS * 1.5)}" 2>/dev/null; then
    FPS_ARGS=(-r "$FPS")
    echo "  fps origem: $fps -> forçando ${FPS}fps" | tee -a "$LOG"
  fi

  if [[ "$USE_VAAPI" -eq 1 ]]; then
    ffmpeg -hide_banner -loglevel error -y -vaapi_device "$VAAPI_DEV" \
      -i "$f" -map 0 -map -0:d -c copy \
      -vf "${SCALE},format=nv12,hwupload" -c:v hevc_vaapi -qp 24 "${FPS_ARGS[@]}" \
      "$tmp_out" 2>>"$LOG"
    ok=$?
  else
    ffmpeg -hide_banner -loglevel error -y \
      -i "$f" -map 0 -map -0:d -c copy \
      -vf "$SCALE" -c:v libx265 -preset medium -crf "$CRF" "${FPS_ARGS[@]}" \
      "$tmp_out" 2>>"$LOG"
    ok=$?
  fi

  if [[ $ok -ne 0 || ! -s "$tmp_out" ]]; then
    echo "  FALHOU: $f" | tee -a "$LOG"
    FAILED=$((FAILED+1))
    rm -f "$tmp_out"
    continue
  fi

  # valida duração (tolerância de 2s) antes de considerar sucesso
  dur_orig=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null | cut -d. -f1)
  dur_new=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$tmp_out" 2>/dev/null | cut -d. -f1)
  diff=$(( ${dur_orig:-0} - ${dur_new:-0} ))
  diff=${diff#-}

  if [[ -z "$dur_new" || "$diff" -gt 2 ]]; then
    echo "  FALHOU (duração não bate: original=${dur_orig}s novo=${dur_new}s): $f" | tee -a "$LOG"
    FAILED=$((FAILED+1))
    rm -f "$tmp_out"
    continue
  fi

  if [[ "$REPLACE" -eq 1 ]]; then
    rm -f "$f"
    mv "$tmp_out" "$final_out"
    echo "  OK, original removido: $final_out" | tee -a "$LOG"
  else
    mv "$tmp_out" "$final_out"
    echo "  OK, original mantido intacto: $final_out" | tee -a "$LOG"
  fi
  CONVERTED=$((CONVERTED+1))
done

echo "----" | tee -a "$LOG"
echo "Convertidos: $CONVERTED | Pulados: $SKIPPED | Falharam: $FAILED" | tee -a "$LOG"
