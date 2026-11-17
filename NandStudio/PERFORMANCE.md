# Mesures de performance

Mesures locales, médiane de sept exécutions après échauffement, même machine et mêmes données.
Le facteur varie selon le matériel, l’image et les programmes ; il ne représente pas les FPS du jeu.

| Opération | Avant | Après | Facteur |
|---|---:|---:|---:|
| Décodage écran 512 × 256 | 13.54 ms | 0.75 ms | 18.0× |
| Encodage image → mots vidéo | 80.64 ms | 2.50 ms | 32.3× |
| Trame Bayer 512 × 256 | 37.42 ms | 3.21 ms | 11.7× |
| Suppression de fond 1024 × 512 | 697.45 ms | 18.53 ms | 37.6× |
| CPU Hack, 100 000 instructions | 49.67 ms | 38.21 ms | 1.3× |

Reproduire : `python benchmark.py`. Les mesures avant optimisation sont dans
`performance-before.json` ; les mesures courantes sont dans `performance-after.json`.

Les tests comparent les opérations accélérées à des références pixel par pixel et
le CPU par lots au moteur pas à pas. Les tâches de conversion gardent au plus une
demande active et une demande récente en attente ; les résultats périmés sont ignorés.
L’exécuteur rend la main après environ 8 ms (contrôle toutes les 256 instructions).
La vidéo est rafraîchie au plus 30 fois par seconde, uniquement si les pixels changent.
