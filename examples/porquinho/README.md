# Porquinho com as 3 juntas

Gerado a partir do porquinho flexi da v1. Como o STL original não estava disponível, o modelo foi reconstruído juntando as 3 partes e fechando as folgas, e por isso alguns detalhes da pele podem estar um pouco suavizados. Todos têm 100 mm de comprimento.

| Arquivo | Junta | Movimento | Observação |
|---|---|---|---|
| `porco_pino_6-15.3mf` | pino | gira ±18°, sobe 6°, desce 15° | recomendada: resistência igual à da v1, emenda de ~2 mm no dorso |
| `porco_pino_12-12.3mf` | pino | gira ±18°, sobe 12°, desce 12° | emenda de ~4 mm no dorso |
| `porco_bola.3mf` | bola | gira ±18°, sobe 12°, desce 12° | trava de 0,5–0,9 mm, pode soltar ao puxar |
| `porco_elos.3mf` | elos | gira ±18°, sobe 12°, desce 12°, com folga | não solta; no pescoço só coube arame de 1,7 mm |

Parâmetros usados (`--zb=0.2 --ring=41:21.5` em todos):

```bash
python3 flexi_chaveiro.py build porco.stl porco_pino_6-15.stl --joint=pino --cut=-15:4.5 --cut=20:6 --pitch_up=6 --pitch_down=15 --zb=0.2 --ring=41:21.5
```

```bash
python3 flexi_chaveiro.py build porco.stl porco_bola.stl --joint=bola --cut=-15:4 --cut=20:5.5 --zb=0.2 --ring=41:21.5
```

```bash
python3 flexi_chaveiro.py build porco.stl porco_elos.stl --joint=elos --cut=-15:3 --cut=20:5 --zb=0.2 --ring=41:21.5
```

Se imprimir a 60% no fatiador, a folga cai de 0,45 para 0,27 mm e a junta pode colar. Prefira regerar com `--length=60`. Ao importar, o Bambu Studio pode avisar de 1 ou 2 arestas não-manifold na traseira; aceite o reparo automático.
