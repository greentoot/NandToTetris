"""Measure local video throughput on a synthetic ten-second HD source."""
from pathlib import Path
import json
import statistics
import subprocess
import tempfile
from video import VideoEngine,VideoSettings,find_ffmpeg,WINDOWS_FLAGS

ROOT=Path(__file__).parent


def main():
    executable=find_ffmpeg()
    if not executable:raise SystemExit('FFmpeg est nécessaire pour ce benchmark.')
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'synthetic-hd.mp4'
        result=subprocess.run([executable,'-y','-hide_banner','-loglevel','error','-f','lavfi',
            '-i','testsrc2=size=1280x720:rate=30','-t','10','-c:v','mpeg4','-q:v','4',str(source)],
            capture_output=True,timeout=60,**WINDOWS_FLAGS)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        for name,width,fps in [('Rapide',256,8),('Nand complet',512,12)]:
            runs=[]
            for _ in range(3):
                clip=VideoEngine().decode(source,VideoSettings(duration=10,width=width,fps=fps))
                runs.append(clip.processing_seconds)
            elapsed=statistics.median(runs)
            results.append({'preset':name,'width':width,'height':width//2,'fps':fps,
                'frames':len(clip.frames),'seconds':round(elapsed,3),
                'frames_per_second':round(len(clip.frames)/elapsed,1),
                'memory_bytes':clip.memory_bytes,'faster_than_realtime':round(10/elapsed,1)})
    (ROOT/'video-performance.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Performance vidéo','',
        'Test local : source synthétique MP4 MPEG-4 de 10 s, 1280 × 720, 30 images/s.',
        'Médiane de trois conversions, sans trame, décodage FFmpeg sur CPU.',
        'Ces chiffres dépendent du codec, du disque et de la machine ; ils ne prédisent pas toute vidéo.',
        '', '| Préréglage | Images de sortie | Temps | Débit | Mémoire des images |',
        '|---|---:|---:|---:|---:|']
    for row in results:
        lines.append(f'| {row["preset"]} {row["width"]} × {row["height"]}, {row["fps"]} i/s | {row["frames"]} | {row["seconds"]:.3f} s | {row["frames_per_second"]} i/s | {row["memory_bytes"]/1048576:.2f} Mo |')
    lines+=['','Reproduire : `python benchmark_video.py`. FFmpeg doit être disponible dans le PATH.',
        'La vidéo source de test est temporaire et n’est pas incluse dans le paquet.',
        'Le lecteur conserve les images à 1 bit : 16 384 octets par image 512 × 256,',
        'soit 32 fois moins que les pixels RGBA équivalents. FFmpeg utilise aussi ses propres buffers.']
    (ROOT/'VIDEO_PERFORMANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
