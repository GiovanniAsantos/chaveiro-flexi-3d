# Changelog

## [1.0.1] - 2026-11-24

### Mudado
- Volta ao padrão da v1.0.0 (junta de pino só com giro horizontal). A v2.0.0, com as juntas pino, bola e elos e a inclinação vertical, fica guardada no branch `v2-tres-articulacoes`.

## [2.0.0] - 2026-11-24

### Adicionado
- 3 tipos de junta com `--joint`: `pino` (padrão, a da v1), `bola` e `elos`.
- Inclinação vertical além do giro: `--pitch`, `--pitch_up` e `--pitch_down`. As folgas são geradas varrendo uma parte por toda a faixa de movimento e tirando esse espaço da outra.
- Subcomando `analyze`: sugere `--zb`, `--cut` e `--ring` e grava uma imagem com vistas e perfil.
- Checagens novas: colisão em toda a faixa de movimento, ilhas flutuantes (camadas que precisariam de suporte), parede lateral fina, piso, ponte e distância do túnel até a junta.
- `--preview` grava os cortes (`vistas.png`) e as poses de movimento (`movimento.png`).
- `--rot` e `--length` (gerar no tamanho final em vez de escalar no fatiador).
- Exemplos do porquinho com as 3 juntas em `examples/porquinho/`.

### Mudado
- **Quebra de compatibilidade**: a linha de comando agora usa subcomandos (`analyze` / `build`), e o modelo é centrado (z mínimo = 0) antes de aplicar os parâmetros.
- O arredondamento das emendas só tira material e não mexe no interior das juntas.

### Corrigido
- Saída com extensão `.STL` maiúscula sobrescrevia o arquivo único com as partes.
- Arquivos 3MF/OBJ que carregavam como cena.
- Crash quando o raio não encontrava o topo do corpo ou o corte da base ficava vazio.
- Lascas de volume zero deixadas pelas booleanas.

## [1.0.0] - 2026-11-24

### Adicionado
- Skill `chaveiro-flexi-3d` (padrão v3 do Chubby T-Rex): corte de base, 2 juntas flexi escondidas, emendas arredondadas e túnel em arco para argola.
- Script `flexi_chaveiro.py` extraído para arquivo próprio, com verificação de watertight, corpos e sobreposição.
- Empacotamento como plugin/marketplace do Claude Code.
