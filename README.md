# chaveiro-flexi-3d

Skill do [Claude Code](https://code.claude.com) que transforma o STL de um bichinho em um **chaveiro flexi articulado, print-in-place**: um único STL com as 3 partes já montadas, pronto para o Bambu Studio (ou outro fatiador) e impressão **sem suporte**.

- **Base plana**: corte em Z com área de apoio ≥ ~2000 mm², traseira encostando na mesa
- **3 partes, 2 juntas escondidas** (pescoço e cintura): emenda em V (meio-ângulo 9°, folga 0,45 mm, giro de ±18°) + cilindro interno com lajes, lingueta e pino, coberto por tampa de 2,4 mm. Por fora só aparece a emenda em V
- **Bordas das emendas arredondadas** (raio 1 mm), visual infantil
- **Túnel em arco para a argola** (canal Ø3 mm) no topo da traseira, com ponte ≥ 3,5 mm e piso ≥ 2,5 mm
- **Verificação automática**: cada parte watertight, 1 corpo, sobreposição zero entre partes

Padrão aprovado na v3 do Chubby T-Rex.

## Instalação

```bash
/plugin marketplace add GiovanniAsantos/chaveiro-flexi-3d
```

```bash
/plugin install chaveiro-flexi-3d@chaveiro-flexi-3d
```

O mesmo marketplace também lista o plugin **caveman** (modo de resposta ultra-curto), que é de outro autor ([Julius Brussee](https://github.com/JuliusBrussee/caveman)) e é instalado direto do repositório dele:

```bash
/plugin install caveman@chaveiro-flexi-3d
```

Ou, como skill avulsa, copie a pasta `plugins/chaveiro-flexi-3d/skills/chaveiro-flexi-3d` para `~/.claude/skills/` (ou envie a pasta compactada em claude.ai → Settings → Capabilities → Skills).

Dependências Python (o Claude instala ao usar a skill):

```bash
pip install trimesh manifold3d scipy scikit-image matplotlib shapely rtree fast-simplification
```

## Como usar

Anexe o STL e peça, por exemplo:

> Faz um chaveiro flexi desse dinossauro.

O Claude segue a skill:

1. **Analisa o modelo**: tamanho, vistas renderizadas, perfil de largura e altura ao longo do comprimento. O modelo precisa estar de bruços, Z para cima, cabeça em −x e centrado em y = 0; se não estiver, ele rotaciona antes.
2. **Escolhe os parâmetros**: altura do corte da base, posição e raio das juntas (pescoço e cintura, sem cortar membros) e posição do túnel.
3. **Gera o STL** com `flexi_chaveiro.py`.
4. **Verifica** watertight, corpos e sobreposição, e renderiza cortes da junta e do túnel.
5. **Entrega** o STL com o resumo das medidas e dicas de impressão.

## Script `flexi_chaveiro.py`

Fica em `plugins/chaveiro-flexi-3d/skills/chaveiro-flexi-3d/scripts/` e também pode ser usado sem o Claude:

```bash
python3 flexi_chaveiro.py entrada.stl saida.stl --zb=-9.5 --cut=-19:4.5 --cut=4:6.5 --ring=34:-1.9
```

| Parâmetro | Significado | Padrão |
|---|---|---|
| `--zb` | z do corte plano da base | obrigatório |
| `--cut X:R` | junta no eixo x = X com cilindro interno de raio R (use duas vezes: pescoço e cintura) | obrigatório |
| `--ring X:Z` | centro do toro do túnel da argola | obrigatório |
| `--gap` | folga entre partes (mm) | 0,45 |
| `--vang` | meio-ângulo da emenda em V (graus) | 9 |
| `--cap` | espessura da tampa sobre a junta (mm) | 2,4 |
| `--round` | raio do arredondamento das emendas (mm) | 1,0 |
| `--ring_R` / `--ring_r` | raio maior do toro / raio do tubo (canal = 2 × r) | 3,6 / 1,5 |

Use `=` em valores negativos (`--zb=-9.5`). Regras práticas: R ≈ 0,35–0,4 × meia-largura no ponto do corte, com ≥ 1,5 mm de parede lateral; o túnel precisa de meia-largura ≥ ~5,5 mm e ≥ 1 mm de distância do cilindro da junta.

Saída: `saida.stl` (peça única) e `saida_parte0.stl`, `_parte1`, `_parte2`. O script imprime as medidas de cada junta, avisa se alguma camada ficar < 1,8 mm e termina com `OK` ou `FALHOU — revisar`.

## Dicas de impressão

- **Suporte desligado** (ou "só na mesa"; suporte em árvore automático pode travar a junta)
- Camada 0,2 mm (0,16 mm se as partes grudarem)
- Depois de imprimir, dobre cada junta devagar para soltar
- Se a argola não passar ou a junta ficar dura, aumente `--ring_r` ou `--gap`

## Estrutura

```
.claude-plugin/marketplace.json
plugins/chaveiro-flexi-3d/
  .claude-plugin/plugin.json
  skills/chaveiro-flexi-3d/
    SKILL.md                    instruções para o Claude
    scripts/flexi_chaveiro.py   geração do chaveiro
```

Histórico: [CHANGELOG.md](CHANGELOG.md). Licença: [MIT](LICENSE).
