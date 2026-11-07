"""Ejecuta los tres notebooks con el kernel local .venv; no requiere red."""
from pathlib import Path
import os
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
import nbformat
from nbclient import NotebookClient


def main():
    root=Path(__file__).resolve().parents[1]
    os.environ['IPYTHONDIR']=str(root/'.venv/ipython')
    os.environ['JUPYTER_RUNTIME_DIR']=str(root/'.venv/jupyter-runtime')
    directory=root/'.venv/share/jupyter/kernels'
    specs=KernelSpecManager(kernel_dirs=[str(directory)])
    for name in ['01_eda_personal_finance.ipynb','02_eda_my_expenses.ipynb','03_comparacion_datasets.ipynb']:
        path=root/'notebooks'/name
        nb=nbformat.read(path,as_version=4)
        nb.metadata.kernelspec.name='fintwin-eda'
        nb.metadata.kernelspec.display_name='Python (.venv FinTwin EDA)'
        km=KernelManager(kernel_name='fintwin-eda',kernel_spec_manager=specs)
        client=NotebookClient(nb,km=km,timeout=120,resources={'metadata':{'path':str(root)}})
        try:
            client.execute()
        finally:
            if km.has_kernel:
                km.shutdown_kernel(now=True)
        errors=[o for c in nb.cells if c.cell_type=='code' for o in c.get('outputs',[]) if o.output_type=='error']
        if errors:raise RuntimeError(f'Errores en {name}')
        nbformat.validate(nb)
        nbformat.write(nb,path)
        print(name, 'ejecutado:',sum(c.cell_type=='code' for c in nb.cells),'celdas; errores:',len(errors),flush=True)

if __name__=='__main__':main()
