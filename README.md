# chaveiro-flexi-3d

Skill do [Claude Code](https://code.claude.com) que transforma o modelo 3D de um bichinho (STL, 3MF ou OBJ) em um **chaveiro flexi articulado, print-in-place**: um único STL com as 3 partes já montadas, pronto para o Bambu Studio (ou outro fatiador) e impressão **sem suporte**.

- **Base plana**: corte em Z com área de apoio ≥ ~2000 mm² × (comprimento/100)², traseira encostando na mesa
- **3 partes, 2 juntas escondidas** (pescoço e cintura), em 3 tipos à escolha (veja abaixo)
- **Giro e inclinação**: as juntas giram para os lados (±18°) e inclinam para cima e para baixo (±12°, ou um ângulo diferente para cada lado)
- **Bordas das emendas arredondadas** (raio 1 mm), visual infantil
- **Túnel em arco para a argola** (canal Ø3 mm) no topo da traseira, com ponte ≥ 3,5 mm e piso ≥ 2,5 mm
- **Verificação automática**: cada parte watertight e com 1 corpo, sobreposição zero, **sem colisão em toda a faixa de movimento** e **sem ilhas flutuantes** (nada que precise de suporte)

## Tipos de junta

| | `pino` (padrão) | `bola` | `elos` |
|---|---|---|---|
| Como é | lajes + lingueta + pino vertical, emenda em V | bola truncada apoiada na mesa, pescoço horizontal, soquete com teto a 45° | 2 argolas entrelaçadas: uma deitada na parte da frente, outra em pé na de trás |
| Resistência | forte (pino Ø3,6–4 mm em cisalhamento) | fraca: trava por encaixe de 0,5–1 mm, pode soltar ao puxar | não solta (presa pela geometria); limitada pela espessura do arame |
| Movimento | firme, sem folga | firme | o mais solto, com folga de ~1,2 mm |
| Espaço que pede | o menor | parede ≥ 1,5 mm em volta da bola | o maior (altura ≥ ~10 mm) |

Subir a cabeça abre a emenda no dorso (≈ altura × tan do ângulo). Para manter a beleza, a combinação recomendada é `--joint=pino --pitch_up=6 --pitch_down=15`, que deixa ~2 mm no dorso.

## Instalação

```bash
/plugin marketplace add GiovanniAsantos/chaveiro-flexi-3d
```

```bash
/plugin install chaveiro-flexi-3d@chaveiro-flexi-3d
```

Se já tinha instalado a versão 1, atualize o marketplace:

```bash
/plugin marketplace update chaveiro-flexi-3d
```

Ou, como skill avulsa, copie a pasta `plugins/chaveiro-flexi-3d/skills/chaveiro-flexi-3d` para `~/.claude/skills/` (ou envie a pasta compactada em claude.ai → Settings → Capabilities → Skills).

Dependências Python (o Claude instala ao usar a skill):

```bash
pip install trimesh manifold3d scipy scikit-image matplotlib shapely rtree fast-simplification
```

## Como usar

Anexe o modelo e peça, por exemplo:

> Faz um chaveiro flexi desse dinossauro, com junta de pino.

O Claude segue a skill: analisa o modelo, escolhe os parâmetros, gera o STL, verifica tudo, renderiza os cortes e as poses de movimento e entrega o STL com as medidas e as dicas de impressão.

## Script `flexi_chaveiro.py`

Fica em `plugins/chaveiro-flexi-3d/skills/chaveiro-flexi-3d/scripts/` e também pode ser usado sem o Claude. Tem dois subcomandos.

**1. Analisar** (sugere os parâmetros e grava uma imagem com vistas e perfil):

```bash
python3 flexi_chaveiro.py analyze entrada.stl --joint=pino
```

**2. Gerar**:

```bash
python3 flexi_chaveiro.py build entrada.stl saida.stl --joint=pino --zb=0.2 --cut=-15:4.5 --cut=20:6 --ring=41:21.5 --pitch_up=6 --pitch_down=15 --preview prev
```

O modelo é centrado antes de tudo (x e y no meio, z mínimo = 0), depois de `--rot` e `--length`. Ele precisa estar de bruços, com a cabeça em −x.

| Parâmetro | Significado | Padrão |
|---|---|---|
| `--joint` | `pino`, `bola` ou `elos` | `pino` |
| `--zb` | z do corte plano da base | obrigatório |
| `--cut X:R` | emenda em x = X; R = raio do cilindro (pino), raio da bola (bola) ou arame = 0,55·R (elos). Use duas vezes | obrigatório |
| `--ring X:Z` | centro do toro do túnel da argola | — |
| `--yaw` | giro para os lados, ± graus | 18 |
| `--pitch` | inclinação, ± graus (0 = só giro) | 12 |
| `--pitch_up` / `--pitch_down` | inclinação só para cima / só para baixo | = `--pitch` |
| `--rot eixo:graus` | rotaciona o modelo antes (repetível), ex. `z:180` | — |
| `--length` | escala o modelo para este comprimento em mm. **Gere no tamanho final**: escalar no fatiador encolhe a folga | — |
| `--gap` | folga entre partes (mm) | 0,45 |
| `--vang` | pino: meio-ângulo da emenda em V (graus) | 9 |
| `--cap` | espessura da tampa sobre a junta (mm) | 2,4 |
| `--round` | raio do arredondamento das emendas (mm) | 1,0 |
| `--ring_R` / `--ring_r` | raio maior do toro / raio do tubo (canal = 2 × r) | 3,6 / 1,5 |
| `--preview DIR` | grava `vistas.png` (cortes) e `movimento.png` (poses) | — |

Use `=` em valores negativos (`--zb=-9.5`). Leva de 2 a 5 minutos. Não rode dois `build` ao mesmo tempo: cada um usa vários GB de RAM.

Saída: `saida.stl` (peça única) e `saida_parte0.stl`, `_parte1`, `_parte2`. O script imprime as medidas de cada junta, a força estimada, a abertura da emenda no dorso, a pior colisão no movimento e as ilhas flutuantes, e termina com `OK` ou `FALHOU - revisar`.

## Exemplos

[`examples/porquinho/`](examples/porquinho) tem o porquinho gerado com as 3 juntas, em 3MF (abre direto no Bambu Studio).

## Dicas de impressão

- **Suporte desligado** (suporte em árvore automático trava a junta)
- Camada 0,2 mm
- Não escalar no fatiador; gere no tamanho final com `--length`
- Depois de imprimir, dobre cada junta devagar nos dois sentidos (giro e inclinação) para soltar

## Estrutura

```
.claude-plugin/marketplace.json
plugins/chaveiro-flexi-3d/
  .claude-plugin/plugin.json
  skills/chaveiro-flexi-3d/
    SKILL.md                    instruções para o Claude
    scripts/flexi_chaveiro.py   análise e geração do chaveiro
examples/porquinho/             porquinho com as 3 juntas (3MF)
```

Histórico: [CHANGELOG.md](CHANGELOG.md). Licença: [MIT](LICENSE).
