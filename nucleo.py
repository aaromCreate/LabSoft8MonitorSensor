import time
import config
import sensores
from sensores import red
import eventos
import almacenamiento as registro

# LABORATORIO
from alertas import sonidos

GRUPO_RAPIDO = ["cpu", "memoria", "red"]
GRUPO_LENTO = ["disco", "procesos", "bateria"]

_marcas = {"rapido": 0.0, "lento": 0.0, "reporte": 0.0}

_ultimas = {}
_activos = []

# LABORATORIO
_ultima_alerta_red = 0.0


def iniciar():
    global _activos

    _activos = sensores.disponibles()

    ahora = time.time()

    for clave in _marcas:
        _marcas[clave] = ahora

    for clave in _activos:
        _ultimas[clave] = sensores.leer(clave)

    ausentes = [c for c in sensores.LECTORES if c not in _activos]

    for clave in ausentes:
        eventos.atender("sensor_ausente", {"metrica": clave})

    registro.registrar_evento(
        "INFO",
        "sistema",
        f"Nodo {config.NODO} iniciado | sensores activos: "
        f"{', '.join(_activos)}"
    )

    return _activos


def _leer_grupo(claves):
    nuevos = []

    for clave in claves:
        if clave not in _activos:
            continue

        lectura = sensores.leer(clave)
        _ultimas[clave] = lectura

        if lectura is not None:
            registro.agregar(clave, lectura["valor"])

        for nombre, dato in eventos.detectar(clave, lectura):
            nuevos.append(eventos.atender(nombre, dato))

    return nuevos


def ciclo():
    global _ultima_alerta_red

    ahora = time.time()
    nuevos = []

    if ahora - _marcas["rapido"] >= config.PERIODO_RAPIDO:
        nuevos += _leer_grupo(GRUPO_RAPIDO)
        _marcas["rapido"] = ahora

    if ahora - _marcas["lento"] >= config.PERIODO_LENTO:
        nuevos += _leer_grupo(GRUPO_LENTO)
        _marcas["lento"] = ahora

    # LABORATORIO
    estado_red = red.conectada()

    # LABORATORIO
    for nombre, dato in eventos.detectar_estado_red(estado_red):
        nuevos.append(eventos.atender(nombre, dato))

    # LABORATORIO
    if not estado_red:
        if ahora - _ultima_alerta_red >= config.RED_RECORDATORIO_S:
            nuevos.append(
                eventos.atender(
                    "red_sigue_desconectada",
                    {"conectada": False}
                )
            )
            _ultima_alerta_red = ahora

    if ahora - _marcas["reporte"] >= config.PERIODO_REPORTE:
        nuevos.append(generar_reporte())
        _marcas["reporte"] = ahora

    # LABORATORIO
    sonidos.actualizar()

    return {
        "lecturas": dict(_ultimas),
        "eventos": nuevos
    }


def generar_reporte():
    datos = registro.resumen()
    registro.guardar_bitacora(datos)
    registro.limpiar_periodo()

    return eventos.atender(
        "reporte",
        {"metricas": len(datos["metricas"])}
    )


def lecturas():
    return dict(_ultimas)


def activos():
    return list(_activos)


if __name__ == "__main__":
    iniciar()

    for _ in range(10):
        resultado = ciclo()

        for e in resultado["eventos"]:
            print(
                f"{e['hora']} "
                f"[{e['nivel']}] "
                f"{e['mensaje']}"
            )

        time.sleep(0.5)