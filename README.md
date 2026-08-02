# optimizarr

Dashboard local e autocontido pra gerenciar recompressão de biblioteca de vídeo (Jellyfin/similar)
em HEVC. Roda direto na máquina que tem os arquivos — sem upload, sem serviço externo, sem banco de
dados. **Os CSVs gerados pelos próprios scripts de análise são 100% o "banco de dados" da aplicação**;
não há histórico de execução persistido além disso.

## O que faz

- Você configura, em **Configurações**, quais pastas monitorar (caminhos absolutos no servidor) e os
  parâmetros padrão de encode (resolução, fps, CRF).
- O **Dashboard** mostra uso de disco por mount e um resumo por pasta: tamanho atual vs. estimativa de
  quanto encolheria se recomprimida — direto da última análise, sem recalcular nada na hora.
- Cada pasta tem sua própria página com uma **tabela ordenável** (clique no header de qualquer coluna)
  com os dados que o script de análise extraiu de cada arquivo, mais um botão **Otimizar** por linha e um
  botão **Atualizar** no topo pra reanalisar a pasta inteira.

## Estrutura

```
scripts/    analyze-video-bloat.py (estima ganho, via ffprobe, sem recodificar nada de verdade)
            transcode-1080p-hevc.sh (recodifica de verdade, HEVC + libx265/VAAPI)
backend/    FastAPI — chama os scripts via subprocess, expõe a API em /api/*
frontend/   React + Vite + TS — Dashboard, Configurações, página por pasta
data/       criado no primeiro run (gitignorado): config.json + CSVs por pasta
```

Mais detalhes de cada script em [`scripts/`](scripts) (veja os comentários de cabeçalho de cada um).

## Rodando

Pré-requisitos no host: `python3`, `node`/`npm`, `ffmpeg`/`ffprobe` (e, opcionalmente, um device VAAPI
em `/dev/dri/renderD128` pra aceleração de encode via iGPU Intel — sem isso cai pra CPU/libx265 sozinho).

### Dev (dois processos)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev   # Vite em :5173, proxy de /api -> :8000
```

Abra `http://localhost:5173`.

### Uso real (processo único, como roda no servidor de mídia no dia a dia)

```bash
cd frontend && npm install && npm run build   # gera frontend/dist/

cd ../backend
source .venv/bin/activate   # depois de criado uma vez, como acima
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abra `http://<host>:8000` — o próprio backend serve o frontend buildado, porta única.

## Notas

- **"Otimizar" um arquivo é destrutivo**: o backend sempre chama `transcode-1080p-hevc.sh --replace`,
  ou seja, o original é apagado depois que o novo arquivo é validado (duração bate). O frontend pede
  confirmação antes de disparar.
- Um job (analisar pasta ou otimizar arquivo) roda por vez por pasta; jobs de otimização são
  serializados globalmente (fila), já que encode de verdade é pesado — analisar (só `ffprobe`) não tem
  esse limite.
- A tabela de uma pasta só reflete a realidade depois de clicar **Atualizar** — otimizar um arquivo não
  atualiza a linha automaticamente, só marca um badge local até a próxima análise.
