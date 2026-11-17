"""Hack video playback with a host-fed RAM buffer, never host-written SCREEN.

RAM[0] is a ready flag; RAM[16:8208] is the next image. A fixed Hack ROM
copies it to SCREEN, then clears the flag. This needs the Studio feeder and
is not a standalone movie fitting in the Hack ROM.
"""
import time
from PIL import Image
from core import words
from machines import HackCPU, assemble


VIDEO_ASM = '''// RAM[0]: 1 = image ready, 0 = copy complete
// RAM[16..8207]: 8192 Hack screen words, supplied by Studio
(WAIT)
@0
D=M
@WAIT
D;JEQ
@16
D=A
@R1
M=D
@SCREEN
D=A
@R2
M=D
(COPY)
@R1
A=M
D=M
@R2
A=M
M=D
@R1
M=M+1
@R2
MD=M+1
@KBD
D=D-A
@COPY
D;JLT
@0
M=0
@WAIT
0;JMP
'''


class VideoCPU(HackCPU):
    """Real Hack instructions plus an explicitly external video input feeder."""
    def __init__(self, clip, start=0):
        if not clip.frames or clip.fps <= 0:
            raise ValueError('La vidéo doit contenir des images et une cadence positive.')
        super().__init__(assemble(VIDEO_ASM))
        self.clip=clip;self.start=max(0,min(len(clip.frames)-1,start))
        self.next_index=self.start;self.displayed_index=None;self.pending_index=None
        self.completed=0;self.next_due=0.0

    def feed(self, now):
        if self.pending_index is not None or now < self.next_due:return False
        image=self.clip.image(self.next_index)
        if image.size != (512,256):
            image=image.resize((512,256),Image.Resampling.NEAREST)
        self.ram[16:8208]=words(image)
        self.ram[0]=1;self.pending_index=self.next_index
        self.next_due=now+1/self.clip.fps
        return True

    def finish(self, now):
        if self.pending_index is not None and self.ram[0]==0:
            self.displayed_index=self.pending_index;self.completed+=1
            self.next_index=(self.pending_index+1)%len(self.clip.frames)
            self.pending_index=None

    def run(self,budget,max_seconds=None):
        now=time.monotonic();self.feed(now)
        if self.pending_index is None:return
        super().run(budget,max_seconds)
        self.finish(time.monotonic())

    def step(self):
        # Manual stepping also allows starting the next frame without a wall-clock wait.
        if self.pending_index is None:self.feed(max(time.monotonic(),self.next_due))
        super().step();self.finish(time.monotonic())

    @property
    def video_status(self):
        index=self.pending_index if self.pending_index is not None else self.displayed_index
        number=0 if index is None else index+1
        return f'Vidéo CPU : image {number}/{len(self.clip.frames)}, {self.completed} dessinées, flux RAM externe'
