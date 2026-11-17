"""Repeatable local performance measurements; timings are not universal guarantees."""
import json
import statistics
import time
from pathlib import Path
from PIL import Image
from core import Settings,convert,words
from machines import framebuffer,HackCPU,assemble

ROOT=Path(__file__).parent


def bench(fn,n=7):
    fn();values=[]
    for _ in range(n):
        started=time.perf_counter();fn();values.append((time.perf_counter()-started)*1000)
    return round(statistics.median(values),3)


def main():
    image=Image.open(ROOT/'examples/grotte.png').convert('RGBA')
    large=image.resize((1024,512));ram=[0]*32768
    ram[16384:24576]=[(i*12347)&65535 for i in range(8192)]
    results={
        'video_decode_ms':bench(lambda:framebuffer(ram)),
        'video_encode_ms':bench(lambda:words(image)),
        'bayer_ms':bench(lambda:convert(image,Settings(dither='Bayer 4 × 4'))),
        'background_removal_ms':bench(lambda:convert(large,Settings(remove_background=True))),
        'cpu_100k_ms':bench(lambda:HackCPU(assemble('@0\nD=A\n@0\n0;JMP')).run(100000))}
    (ROOT/'performance-after.json').write_text(json.dumps(results,indent=2))
    before=json.loads((ROOT/'performance-before.json').read_text())
    labels={'video_decode_ms':'Décodage écran 512 × 256','video_encode_ms':'Encodage image vers mots vidéo',
            'bayer_ms':'Trame Bayer 512 × 256','background_removal_ms':'Suppression de fond 1024 × 512',
            'cpu_100k_ms':'CPU Hack, 100 000 instructions'}
    lines=['# Mesures de performance','',
           'Mesures locales, médiane de sept exécutions après échauffement, même machine et mêmes données.',
           'Le facteur varie selon le matériel, l’image et les programmes ; il ne représente pas les FPS du jeu.',
           '', '| Opération | Avant | Après | Facteur |','|---|---:|---:|---:|']
    for key,after in results.items():
        lines.append(f'| {labels[key]} | {before[key]:.2f} ms | {after:.2f} ms | {before[key]/after:.1f}× |')
    lines+=['','Reproduire : `python benchmark.py`. Les mesures avant optimisation sont dans',
            '`performance-before.json` ; les mesures courantes sont dans `performance-after.json`.','',
            'Les tests comparent les opérations accélérées à des références pixel par pixel et',
            'le CPU par lots au moteur pas à pas. Les tâches de conversion gardent au plus une',
            'demande active et une demande récente en attente ; les résultats périmés sont ignorés.',
            'L’exécuteur rend la main après environ 8 ms (contrôle toutes les 256 instructions).',
            'La vidéo est rafraîchie au plus 30 fois par seconde, uniquement si les pixels changent.']
    (ROOT/'PERFORMANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
