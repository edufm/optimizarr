#!/usr/bin/env python3
"""
Varre uma pasta de vídeos e estima, por arquivo, o quanto vale a pena
recomprimir em HEVC — sem rodar nenhum encode de verdade, só analisando
metadata (ffprobe). Serve pra dimensionar o problema antes de gastar
tempo/CPU/GPU de verdade.

Métrica central: bits por pixel (bpp) = bitrate_video / (largura * altura * fps).
Normaliza o bitrate pela "quantidade de imagem", permitindo comparar arquivos
de resoluções diferentes. Valores de referência (calibrados em testes reais
neste projeto, num arquivo H264 High Profile de conteúdo com bastante
detalhe/movimento):
  - bpp ~0.04  -> já eficiente, pouco ganho esperado com HEVC
  - bpp ~0.54  -> muito acima do necessário, ganho grande esperado

A estimativa de tamanho final considera também o teto de resolução/fps que
seria aplicado por transcode-1080p-hevc.sh (--resolution/--fps): pra fontes
acima desse teto, o cálculo já assume o downscale/fps-cap real, não só o
ganho de eficiência do codec — senão a estimativa fica conservadora demais
pra fontes muito acima da resolução/fps-alvo.

Uso:
  analyze-video-bloat.py <diretorio> [--csv saida.csv] [--min-savings N]
                         [--resolution N] [--fps N]

  --min-savings N   % mínimo de redução estimada pra considerar "vale a pena"
                     (padrão 20)
  --csv arquivo      também exporta a tabela completa em CSV
  --resolution N    teto do lado curto em pixels usado na estimativa, mesmo
                     significado do transcode-1080p-hevc.sh (padrão 1080)
  --fps N           fps-alvo usado na estimativa, mesmo significado do
                     transcode-1080p-hevc.sh (padrão 30)
"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts"}

# bpp-alvo pra "boa qualidade", calibrado nos testes reais deste projeto
TARGET_BPP_X265 = 0.060   # ~libx265 crf 23-24 numa fonte com bastante detalhe
TARGET_BPP_NVENC = 0.130  # ~hevc_nvenc cq 25-26 na mesma fonte

# fator de velocidade medido nos testes reais (multiplicador de tempo real)
SPEED_X265 = 1.0    # CPU 12 threads, ~1x tempo real pra crf~24
SPEED_NVENC = 15.0  # GPU (GTX 1070), conservador; GPUs mais novas são mais rápidas


def ffprobe(path: Path):
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_entries", "format=duration,size",
        "-show_entries",
        "stream=codec_name,codec_type,width,height,avg_frame_rate,r_frame_rate,bit_rate,"
        "profile,pix_fmt,color_space,color_transfer,color_primaries,field_order",
        str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout)
    except Exception:
        return None


def parse_fps(s: str):
    if not s or s == "0/0":
        return None
    try:
        num, den = s.split("/")
        num, den = float(num), float(den)
        return num / den if den else None
    except Exception:
        return None


def analyze_file(path: Path, resolution: int, long_edge: int, fps_target: float):
    data = ffprobe(path)
    if not data or "format" not in data:
        return None

    fmt = data["format"]
    duration = float(fmt.get("duration", 0) or 0)
    size = int(fmt.get("size", 0) or 0)
    if duration <= 0 or size <= 0:
        return None

    video_stream = None
    audio_bitrate = 0
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and video_stream is None:
            video_stream = s
        elif s.get("codec_type") == "audio" and s.get("bit_rate"):
            audio_bitrate += int(s["bit_rate"])

    if not video_stream:
        return None

    width = video_stream.get("width")
    height = video_stream.get("height")
    codec = video_stream.get("codec_name", "?")
    fps = parse_fps(video_stream.get("avg_frame_rate")) or parse_fps(video_stream.get("r_frame_rate")) or 24.0

    if not width or not height:
        return None

    video_bitrate = video_stream.get("bit_rate")
    if video_bitrate:
        video_bitrate = int(video_bitrate)
    else:
        overall_bitrate = size * 8 / duration
        video_bitrate = max(overall_bitrate - audio_bitrate, overall_bitrate * 0.5)

    pixels = width * height
    bpp = video_bitrate / (pixels * fps)

    # pixels/fps "efetivos" pós-transcode: mesma lógica do scale filter e do
    # FPS_ARGS em transcode-1080p-hevc.sh — decrease-only (nunca faz upscale),
    # aspect ratio preservado, e só força fps pra baixo se a fonte estiver bem
    # acima do alvo (>= 1.5x).
    short_edge_src, long_edge_src = (height, width) if width > height else (width, height)
    scale = min(1.0, resolution / short_edge_src, long_edge / long_edge_src)
    effective_pixels = pixels * scale * scale
    effective_fps = fps_target if fps >= fps_target * 1.5 else fps

    est_bitrate_x265 = min(video_bitrate, TARGET_BPP_X265 * effective_pixels * effective_fps)
    est_bitrate_nvenc = min(video_bitrate, TARGET_BPP_NVENC * effective_pixels * effective_fps)

    est_video_size_x265 = est_bitrate_x265 * duration / 8
    est_video_size_nvenc = est_bitrate_nvenc * duration / 8

    audio_size = audio_bitrate * duration / 8
    original_video_size = video_bitrate * duration / 8

    est_size_x265 = size - original_video_size + est_video_size_x265
    est_size_nvenc = size - original_video_size + est_video_size_nvenc

    savings_x265 = 100 * (1 - est_size_x265 / size)
    savings_nvenc = 100 * (1 - est_size_nvenc / size)

    gb_per_hour = size / duration * 3600 / 1024**3

    return {
        "path": path,
        "codec": codec,
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "size": size,
        "bpp": bpp,
        "est_size_x265": est_size_x265,
        "est_size_nvenc": est_size_nvenc,
        "savings_x265": savings_x265,
        "savings_nvenc": savings_nvenc,
        "gb_per_hour": gb_per_hour,
        "profile": video_stream.get("profile", ""),
        "pix_fmt": video_stream.get("pix_fmt", ""),
        "color_space": video_stream.get("color_space", ""),
        "color_transfer": video_stream.get("color_transfer", ""),
        "color_primaries": video_stream.get("color_primaries", ""),
        "field_order": video_stream.get("field_order", ""),
    }


def human(n):
    for unit in ["B", "K", "M", "G", "T"]:
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}P"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--csv")
    ap.add_argument("--min-savings", type=float, default=20.0)
    ap.add_argument("--exclude", action="append", default=[],
                     help="nome de pasta a ignorar (pode repetir), ex: --exclude downloads --exclude musicas")
    ap.add_argument("--resolution", type=int, default=1080,
                     help="teto do lado curto em pixels usado na estimativa (padrão 1080)")
    ap.add_argument("--fps", type=float, default=30,
                     help="fps-alvo usado na estimativa (padrão 30)")
    args = ap.parse_args()

    long_edge = round(args.resolution * 16 / 9)

    root = Path(args.dir)
    excludes = set(args.exclude)

    def is_excluded(p: Path) -> bool:
        return any(part in excludes for part in p.relative_to(root).parts)

    files = sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in VIDEO_EXTS and p.is_file() and not is_excluded(p)
    )

    print(f"Analisando {len(files)} arquivos em {root}...", file=sys.stderr)
    print(f"Alvo da estimativa: resolução {args.resolution}p (lado longo {long_edge}), fps {args.fps}.\n",
          file=sys.stderr)

    results = []
    for i, f in enumerate(files, 1):
        print(f"\r[{i}/{len(files)}] {f.name[:60]}", end="", file=sys.stderr, flush=True)
        r = analyze_file(f, args.resolution, long_edge, args.fps)
        if r:
            results.append(r)
    print(file=sys.stderr)

    results.sort(key=lambda r: r["savings_x265"], reverse=True)

    worth_it = [r for r in results if r["savings_x265"] >= args.min_savings]
    marginal = [r for r in results if r["savings_x265"] < args.min_savings]

    print(f"\n{'ARQUIVO':<50} {'RES':<10} {'CODEC':<6} {'BPP':<7} {'GB/h':<6} {'GANHO x265':<11} {'GANHO NVENC':<11}")
    print("-" * 108)
    for r in results:
        rel = str(r["path"].relative_to(root))
        if len(rel) > 49:
            rel = "..." + rel[-46:]
        print(f"{rel:<50} {r['width']}x{r['height']:<5} {r['codec']:<6} {r['bpp']:<7.3f} {r['gb_per_hour']:<6.2f} "
              f"{r['savings_x265']:>9.0f}% {r['savings_nvenc']:>10.0f}%")

    total_size = sum(r["size"] for r in results)
    total_est_x265 = sum(r["est_size_x265"] if r in worth_it else r["size"] for r in results)
    total_est_nvenc = sum(r["est_size_nvenc"] if r in worth_it else r["size"] for r in results)
    total_duration_worth_it = sum(r["duration"] for r in worth_it)

    print("\n=== RESUMO ===")
    print(f"Total de arquivos analisados: {len(results)}")
    print(f"Tamanho total atual: {human(total_size)}")
    print(f"Vale a pena recomprimir (>= {args.min_savings:.0f}% de ganho estimado): {len(worth_it)} arquivos")
    print(f"Ganho baixo / já eficiente: {len(marginal)} arquivos")
    print()
    if total_size > 0:
        print(f"Tamanho estimado após libx265 (CPU) nos arquivos que valem a pena: {human(total_est_x265)} "
              f"(economia de {human(total_size - total_est_x265)}, {100*(1-total_est_x265/total_size):.0f}%)")
        print(f"Tamanho estimado após hevc_nvenc (GPU) nos arquivos que valem a pena: {human(total_est_nvenc)} "
              f"(economia de {human(total_size - total_est_nvenc)}, {100*(1-total_est_nvenc/total_size):.0f}%)")
    print()
    print(f"Tempo estimado CPU (libx265, ~{SPEED_X265}x tempo real): "
          f"{total_duration_worth_it / SPEED_X265 / 3600:.1f} horas")
    print(f"Tempo estimado GPU (NVENC, ~{SPEED_NVENC}x tempo real): "
          f"{total_duration_worth_it / SPEED_NVENC / 3600:.1f} horas")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["arquivo", "largura", "altura", "codec", "profile", "pix_fmt", "color_space",
                        "color_transfer", "color_primaries", "field_order", "fps", "duracao_s", "tamanho_bytes",
                        "gb_por_hora", "bpp", "estimado_x265_bytes", "estimado_nvenc_bytes",
                        "ganho_x265_pct", "ganho_nvenc_pct"])
            for r in results:
                w.writerow([str(r["path"]), r["width"], r["height"], r["codec"], r["profile"], r["pix_fmt"],
                            r["color_space"], r["color_transfer"], r["color_primaries"], r["field_order"],
                            f"{r['fps']:.2f}", f"{r['duration']:.1f}", r["size"], f"{r['gb_per_hour']:.3f}",
                            f"{r['bpp']:.4f}", f"{r['est_size_x265']:.0f}", f"{r['est_size_nvenc']:.0f}",
                            f"{r['savings_x265']:.1f}", f"{r['savings_nvenc']:.1f}"])
        print(f"\nCSV salvo em {args.csv}")


if __name__ == "__main__":
    main()
