# Performance vidéo

Test local : source synthétique MP4 MPEG-4 de 10 s, 1280 × 720, 30 images/s.
Médiane de trois conversions, sans trame, décodage FFmpeg sur CPU.
Ces chiffres dépendent du codec, du disque et de la machine ; ils ne prédisent pas toute vidéo.

| Préréglage | Images de sortie | Temps | Débit | Mémoire des images |
|---|---:|---:|---:|---:|
| Rapide 256 × 128, 8 i/s | 80 | 0.168 s | 474.9 i/s | 0.31 Mo |
| Nand complet 512 × 256, 12 i/s | 120 | 0.174 s | 689.3 i/s | 1.88 Mo |

Reproduire : `python benchmark_video.py`. FFmpeg doit être disponible dans le PATH.
La vidéo source de test est temporaire et n’est pas incluse dans le paquet.
Le lecteur conserve les images à 1 bit : 16 384 octets par image 512 × 256,
soit 32 fois moins que les pixels RGBA équivalents. FFmpeg utilise aussi ses propres buffers.
