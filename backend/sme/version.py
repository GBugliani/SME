"""Identificador do código Python efetivamente carregado pelo backend."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@lru_cache(maxsize=1)
def backend_code_id():
    root = Path(__file__).resolve().parents[1]
    digest = sha256()
    files = (path for path in root.rglob('*') if path.is_file()
             and (path.suffix == '.py' or path.name == 'requirements.txt')
             and not any(part.startswith('.') or part == '__pycache__'
                         for part in path.relative_to(root).parts))
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(f'backend/{path.relative_to(root).as_posix()}'.encode())
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()[:8]


@require_GET
def version(request):
    return JsonResponse({'backend_code_id': backend_code_id()})
