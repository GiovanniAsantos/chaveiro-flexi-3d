---
name: "chaveiro-flexi-3d"
description: "Transforma um modelo 3D de bichinho (STL/3MF/OBJ) em chaveiro flexi print-in-place: corte na base, 2 juntas escondidas (3 partes) que giram e inclinam, e túnel em arco para argola, sem suporte. Use quando pedirem chaveiro articulado, flexi, print-in-place, dobrável, \"bichinho que mexe\" ou juntas para impressão 3D a partir de um modelo."
---

# Chaveiro flexi articulado a partir de modelo 3D

Entrada: STL/3MF/OBJ de um bichinho. Saída: **um único STL** com as 3 partes já montadas, pronto pro Bambu Studio, impressão **sem suporte** (nada de árvore, nada de filamento perdido).

Script: `scripts/flexi_chaveiro.py` (na pasta desta skill). Ele tem 2 subcomandos: `analyze` e `build`.

## Padrão fixo
- **Base**: corte plano em Z com área de apoio ≥ ~2000 mm² × (comprimento/100)², traseira encostando na mesa.
- **3 partes**: emendas no **pescoço** e na **cintura** (entre braços e pernas). Nunca cortar membro, orelha ou pata.
- **Juntas** (`--joint`):
  - `pino` (**padrão aprovado**): lajes + lingueta + pino vertical, emenda em V (9°, folga 0,45). Com `--pitch` > 0, o script também **inclina**: tira da parte da frente o espaço varrido pela de trás, em todas as posições de giro e inclinação. A estrutura interna continua a mesma; só a borda das lajes perde ~R·sen(pitch).
  - `bola`: bola truncada apoiada na mesa, pescoço horizontal, soquete varrido com teto a 45°. Gira e inclina, mas a trava é por encaixe (pode estourar se a trava for < 1 mm).
  - `elos`: 2 argolas entrelaçadas. A da frente fica deitada na mesa e faz ponte sobre a barra da de trás; a de trás fica em pé. Não solta nunca (presa pela geometria), é o movimento mais fluido, mas tem folga e precisa de altura.
- **Qual junta usar** (perguntar ao usuário se ele não disser; padrão `pino`):
  | | pino | bola | elos |
  |---|---|---|---|
  | Resistência | forte (pino Ø3,6–4 em cisalhamento) | fraca: trava por encaixe 0,5–1 mm | não solta (geometria), limitada pela espessura do arame |
  | Movimento | firme, sem folga | firme | o mais solto, folga ~1,2 mm |
  | Espaço que pede | o menor | parede ≥ 1,5 mm em volta da bola | o maior (altura ≥ ~10 mm, largura ~3,3 × arame) |
  | Bom para | qualquer bicho | testes / bichos grandes | bichos de pescoço e cintura grossos |
- **Movimento padrão**: giro ±18° (`--yaw`), inclinação ±12° (`--pitch`). `--pitch=0` volta ao comportamento antigo (só horizontal).
- **Entalhe no dorso**: subir a cabeça abre a emenda no dorso ≈ altura × tan(ângulo); com 12° fica ~4 mm num corpo de 25 mm. Descer só abre na barriga, que fica escondida. Para manter a beleza, usar `--pitch_up=6 --pitch_down=15` (~2 mm no dorso). É a combinação recomendada com `pino`.
- **Bordas das emendas arredondadas** (raio 1 mm). Isso só tira material e nunca toca o interior da junta.
- **Argola**: túnel em arco (toro R=3,6, tubo r=1,5 → canal Ø3 mm) no topo da traseira. Piso ≥ 2,5 mm, ponte ≥ 3,5 mm, ≥ 1 mm da junta (o script confere).

## Passos

### 1. Preparar
```bash
pip install --break-system-packages -q trimesh manifold3d scipy scikit-image matplotlib shapely rtree fast-simplification
```
- Se vier `.3mf` (ou zip de 3MF), extrair a malha: `trimesh.load(arquivo, force='mesh')`. Se o loader falhar, ler os `<vertex>`/`<triangle>` de `3D/Objects/*.model`. Extrair arquivos baixados numa pasta própria.
- **Gerar no tamanho final.** Escalar no slicer depois encolhe a folga: 0,45 mm a 60% vira 0,27 mm, e o pino e as lajes encolhem junto. Use `--length=<mm>` em vez disso.
- Não rodar dois `build` em paralelo: cada um usa vários GB de RAM.

### 2. Analisar
```bash
python3 scripts/flexi_chaveiro.py analyze entrada.stl --joint=pino [--rot=z:180] [--length=60]
```
- O modelo é centrado (x e y no meio, z mín = 0) depois de `--rot`/`--length`. Os mesmos flags precisam ir para o `build`.
- Ele imprime a sugestão de `--zb`, `--cut` (pescoço e cintura pela meia-largura mínima, R pela parede de 1,6 mm) e `--ring`, e grava `*_analise.png`. **Olhar a imagem**: a cabeça precisa estar em −x (senão use `--rot=z:180`) e os cortes não podem pegar em patas.
- `--cut=X:R`: X = emenda. R = raio do cilindro (pino), raio da bola (bola) ou arame = 0,55·R (elos).

### 3. Gerar
```bash
python3 scripts/flexi_chaveiro.py build entrada.stl saida.stl --joint=pino --zb=0.2 --cut=-15:4.5 --cut=20:6 --ring=41:21.5 --preview prev
```
Use `=` nos valores negativos. Leva de 2 a 5 min. Ele grava `saida.stl`, `saida_parteN.stl` e, com `--preview`, `prev/vistas.png` e `prev/movimento.png`.

### 4. Verificar (obrigatório)
A saída precisa terminar com `OK`. Isso exige:
- cada parte watertight, 1 corpo, **0 ilhas flutuantes** (camadas de 0,2 mm sem nada embaixo = precisaria suporte);
- sobreposição 0 em repouso;
- **pior colisão no movimento < 0,5 mm³** (as partes são giradas em toda a faixa de giro × inclinação).

Avisos para tratar:
- `parede lateral < 1.5`: reduza R ou mova o corte;
- `camada < 1.8`: reduza R;
- `trava < 1 mm` (bola);
- `juntas muito perto`;
- problemas no túnel.

Olhar os PNGs. Em `vistas.png`: corte lateral y=0, corte em z e em x de cada junta, e túnel. Em `movimento.png`: poses no giro e na inclinação máximos. Se o STL passar de ~20 MB, simplificar (fast-simplification) e rechecar watertight.

### 5. Entregar
- Enviar o STL único com SendUserFile, mais os PNGs de preview.
- Resumo curto: onde ficaram as emendas, o tipo de junta, as medidas (linha `forca:`), a abertura da emenda no dorso e o volume de filamento.
- Dicas de impressão:
  - **suporte desligado** (árvore automática trava a junta);
  - camada de 0,2 mm;
  - não escalar no slicer;
  - depois de imprimir, dobrar cada junta devagar nos dois sentidos (giro e inclinação) para soltar.

## Armadilhas já resolvidas
- Não usar `mesh.contains` em grade grande (estoura memória). O script rasteriza fatias com matplotlib Path.
- marching_cubes com `allow_degenerate=False` e campo com `np.pad`; inverter as normais **antes** de checar `is_volume`.
- Booleanas sempre com `engine='manifold'`. Depois delas, o `clean()` remove lascas de volume ~0.
- `trimesh.load(..., force='mesh')`, senão um 3MF/OBJ vira Scene.
- A saída `.STL` maiúscula não sobrescreve mais o arquivo único (o sufixo é tratado com `os.path.splitext`).
- Sem pouso para a peça (ex.: bola pendurada no pescoço) = ilha flutuante. Tudo dentro da junta precisa nascer na mesa ou ser ponte entre duas partes do mesmo corpo.
