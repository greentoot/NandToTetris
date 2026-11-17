"""Use the bundled group's Jack compiler without a dependency on the parent repo."""
from pathlib import Path
import importlib.util
import sys
import contextlib
import os


def compile_jack(source,destination):
    vendor=Path(__file__).parent/'vendor'/'jack'
    if str(vendor) not in sys.path: sys.path.insert(0,str(vendor))
    import generator
    try:
        with open(os.devnull,'w') as silent, contextlib.redirect_stdout(silent):
            instance=generator.Generator(str(source))
            instance.generate()
    except SystemExit as error:
        raise ValueError('Compilation interrompue : erreur de syntaxe dans '+Path(source).name) from error
    code='\n'.join(instance.vm_lines)+'\n'
    if not code.strip(): raise ValueError('Le compilateur n’a produit aucun code VM.')
    Path(destination).write_text(code,encoding='utf-8')
    return code
