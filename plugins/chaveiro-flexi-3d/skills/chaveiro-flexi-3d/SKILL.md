---
name: "chaveiro-flexi-3d"
description: "Transforma um STL de bichinho em chaveiro flexi print-in-place: corte na base, 2 juntas escondidas (3 partes) e túnel em arco para argola. Use quando pedir chaveiro articulado/flexi de um STL."
---

# Chaveiro flexi articulado a partir de STL

Padrão aprovado (v3 do Chubby T-Rex). Entrada: STL de um bichinho. Saída: **um único STL** com as 3 partes já montadas na posição, pronto pro Bambu Studio, impressão sem suporte.

## Padrão fixo
- **Base**: corte plano em Z pra área de apoio ≥ ~2000 mm² (escala com o tamanho), traseira/cauda encostando na mesa. Normalmente tira 1–1,5 mm.
- **3 partes**: 2 cortes transversais — **pescoço** e **cintura (entre braços e pernas)**. Nunca cortar membro, orelha ou pata (a emenda em V abre até ~0,16×|y| de cada lado; conferir pontas laterais).
- **Junta flexi escondida** de eixo vertical: emenda em V (meio-ângulo 9°, folga 0,45 mm, ±18° de giro) + cilindro interno com laje de baixo, lingueta, laje de cima e pino, coberto por tampa de 2,4 mm. Nada da junta aparece por fora além da emenda em V.
- **Bordas das emendas arredondadas** (raio 1 mm), visual infantil.
- **Argola**: túnel em arco (toro R=3,6 mm, tubo r=1,5 → canal Ø3 mm) atravessando a largura no topo da cauda/"bunda", entradas inclinadas nos flancos de cima. Ponte ≥ 3,5 mm, piso ≥ 2,5 mm, ≥ 1 mm de distância da junta.

## Passos

### 1. Preparar
```bash
pip install --break-system-packages -q trimesh manifold3d scipy scikit-image matplotlib shapely rtree fast-simplification
```
Copiar `scripts/flexi_chaveiro.py` (na pasta desta skill) para o diretório de trabalho.

### 2. Analisar o modelo
- Carregar, informar tamanho e bounds, fazer vistas (matplotlib Poly3DCollection, malha decimada pra ~8k faces) e olhar as imagens.
- O script supõe: **de bruços, Z pra cima, cabeça em −x, comprimento em x, centrado em y=0**. Se não estiver assim, rotacionar/transladar e salvar uma cópia antes.
- Perfil ao longo de x (passo de 2 mm): meia-largura (`mesh.section` com normal x → bounds em y) e topo em y=0 (raio de cima pra baixo). Área de fatias horizontais perto do fundo pra escolher `--zb`. Menor z da traseira pra garantir que ela encoste.

### 3. Escolher os parâmetros
- `--zb`: z do corte da base.
- `--cut=X:R` (duas vezes): X no pescoço (meia-largura mínima entre cabeça e braços) e na cintura (entre o fim dos braços e o começo das pernas). R ≈ 0,35–0,4 × meia-largura no corte, mantendo ≥ 1,5 mm de parede lateral. Ex. para bicho de 100 mm: pescoço R=4,5, cintura R=6,5.
- `--ring=X:Z`: X numa região da cauda/traseira com meia-largura ≥ ~5,5 mm e longe da junta (borda do toro em x = X±1,5; manter ≥ 1 mm do cilindro da junta, que vai até corte+R+0,45). Z ≈ topo em y=0 naquele X menos ~1,4 mm. Conferir: piso = Z − 5,1 − zb ≥ 2,5.
- Usar `=` nos argumentos com valor negativo (`--zb=-9.5`).

### 4. Rodar
```bash
python3 flexi_chaveiro.py entrada.stl saida.stl --zb=-9.5 --cut=-19:4.5 --cut=4:6.5 --ring=34:-1.9
```
O script imprime as medidas de cada junta (L/T/U, tampa, pino) e avisa se alguma camada ficar < 1,8 mm — aí reduzir R ou mover o corte. Também grava cada parte separada (`_parteN.stl`).

### 5. Verificar (obrigatório)
- Saída precisa terminar com `OK`: cada parte watertight, 1 corpo, sobreposição 0.
- Renderizar e olhar: vistas 3D coloridas por parte; corte lateral y=0; corte em z no meio da lingueta; corte transversal (normal x) no X do túnel mostrando ponte e piso.
- Conferir que nenhum membro foi cortado pela emenda e que o túnel não encosta na junta.
- Se o STL passar de ~20 MB, simplificar (fast-simplification) e rechecar watertight.

### 6. Entregar
- Enviar o STL único com SendUserFile.
- Resumo curto: onde ficaram os cortes, medidas das juntas, Ø do túnel.
- Dicas de impressão: **suporte desligado** (ou "só na mesa" — árvore automática pode travar a junta), camada 0,2 mm (0,16 se grudar), folga 0,45, dobrar cada junta devagar depois de imprimir. Oferecer aumentar túnel/folga se precisar.

## Armadilhas já resolvidas
- Não usar `mesh.contains` em grade grande → estoura memória. O script rasteriza fatias com matplotlib Path.
- marching_cubes com `allow_degenerate=False` e campo com `np.pad`; inverter normais **antes** de checar `is_volume`.
- Booleanas sempre com `engine='manifold'`.
