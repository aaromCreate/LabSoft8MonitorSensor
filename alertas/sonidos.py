# LABORATORIO
import time
from collections import deque
import config

try:
    import winsound
except ImportError:
    winsound = None

_cola = deque()
_actual = None
_hasta = 0.0


def agregar(nombre):
    # LABORATORIO
    if not config.SONIDO_SILENCIOSO:
        _cola.append(nombre)


def actualizar():
    # LABORATORIO
    global _actual, _hasta

    if winsound is None:
        _cola.clear()
        return

    ahora = time.monotonic()

    if _actual is not None and ahora < _hasta:
        return

    if not _cola:
        _actual = None
        return

    nombre = _cola.popleft()
    ruta, duracion = config.SONIDOS[nombre]

    winsound.PlaySound(
        ruta,
        winsound.SND_FILENAME | winsound.SND_ASYNC
    )

    _actual = nombre
    _hasta = ahora + duracion