"""Generador grafico de carga y alertas para el monitor IoT."""

import multiprocessing
import os
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk

import almacenamiento as registro
import config
import eventos
from alertas import sonidos

MAX_SEGUNDOS = 60
MAX_MB_MEMORIA = 800
MAX_MB_DISCO = 500


def _quemar(fin):
    while time.time() < fin:
        pass


def cargar_cpu(segundos=15, nucleos=None):
    segundos = min(segundos, MAX_SEGUNDOS)
    nucleos = nucleos or os.cpu_count() or 1
    fin = time.time() + segundos
    procesos = [multiprocessing.Process(target=_quemar, args=(fin,)) for _ in range(nucleos)]
    for proceso in procesos:
        proceso.start()
    for proceso in procesos:
        proceso.join()


def cargar_memoria(megabytes=700, segundos=20):
    megabytes = min(megabytes, MAX_MB_MEMORIA)
    segundos = min(segundos, MAX_SEGUNDOS)
    bloques = []
    try:
        for _ in range(megabytes):
            bloque = bytearray(1024 * 1024)
            bloque[0] = 1
            bloques.append(bloque)
        time.sleep(segundos)
    except MemoryError:
        pass
    finally:
        bloques.clear()


def cargar_disco(megabytes=200, segundos=10):
    megabytes = min(megabytes, MAX_MB_DISCO)
    segundos = min(segundos, MAX_SEGUNDOS)
    ruta = os.path.join(tempfile.gettempdir(), "lab_iot_relleno.tmp")
    try:
        with open(ruta, "wb") as archivo:
            bloque = b"0" * (1024 * 1024)
            for _ in range(megabytes):
                archivo.write(bloque)
            archivo.flush()
            os.fsync(archivo.fileno())
        time.sleep(segundos)
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def abrir_procesos(cantidad=5, segundos=15):
    segundos = min(segundos, MAX_SEGUNDOS)
    procesos = [multiprocessing.Process(target=time.sleep, args=(segundos,)) for _ in range(cantidad)]
    for proceso in procesos:
        proceso.start()
    for proceso in procesos:
        proceso.join()


def simular_alerta(metrica):
    if metrica in ("cpu", "memoria", "disco", "red"):
        umbrales = {
            "cpu": config.CPU_ALTO,
            "memoria": config.RAM_ALTA,
            "disco": config.DISCO_LLENO,
            "red": config.RED_PICO_KBS,
        }
        umbrales_bajos = {
            "cpu": config.CPU_BAJO,
            "memoria": config.RAM_BAJA,
            "disco": config.DISCO_ALIVIADO,
            "red": config.RED_CALMA_KBS,
        }
        valor_bajo = umbrales_bajos[metrica]
        valor = umbrales[metrica]
        extra = {"nucleos": [0.0]} if metrica == "cpu" else None
        if metrica == "memoria":
            extra = {"usa_swap": False, "swap_pct": 0.0}
        lectura_baja = {"valor": valor_bajo}
        lectura_alta = {"valor": valor}
        if extra is not None:
            lectura_baja["extra"] = extra
            lectura_alta["extra"] = extra
        for _ in range(config.VENTANA):
            registro.agregar(metrica, valor_bajo)
        for nombre, dato in eventos.detectar(metrica, lectura_baja):
            eventos.atender(nombre, dato)
        for _ in range(config.VENTANA):
            registro.agregar(metrica, valor)
        lectura = lectura_alta
    elif metrica == "procesos":
        lectura = {
            "valor": 1,
            "extra": {
                "identidades": {},
                "top": [{"nombre": "Proceso simulado",
                         "cpu": config.PROCESO_PESADO}],
            },
        }
    elif metrica == "bateria":
        lectura = {"valor": config.BATERIA_RECUPERADA,
                   "extra": {"conectado": False}}
        for nombre, dato in eventos.detectar(metrica, lectura):
            eventos.atender(nombre, dato)
        lectura["valor"] = config.BATERIA_BAJA
    else:
        raise ValueError(f"Metrica no soportada: {metrica}")
    generados = eventos.detectar(metrica, lectura)
    for nombre, dato in generados:
        eventos.atender(nombre, dato)
    sonidos.actualizar()
    return ", ".join(nombre for nombre, _ in generados) or "sin evento"


class GeneradorVentana:
    def __init__(self, ventana):
        self.ventana = ventana
        self.estado = tk.StringVar(value="Listo")
        ventana.title("Generador de pruebas - Monitor IoT")
        ventana.geometry("560x360")
        self.sonidos_programados = False

        marco = ttk.Frame(ventana, padding=14)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="Generador de pruebas", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(marco, text="Ejecuta cada prueba en segundo plano.").pack(anchor="w", pady=(2, 12))

        botones = ttk.Frame(marco)
        botones.pack(fill="x", pady=8)
        for texto, metrica in (("RAM", "memoria"), ("DISCO", "disco"),
                               ("PROCESOS", "procesos"), ("CPU", "cpu"),
                               ("TODOS LOS SENSORES", "todos")):
            ttk.Button(botones, text=texto,
                       command=lambda m=metrica: self.alerta(m)).pack(side="left", padx=3)

        ttk.Label(marco, textvariable=self.estado).pack(anchor="w", pady=5)
        self.salida = tk.Text(marco, height=10, state="disabled")
        self.salida.pack(fill="both", expand=True)

    def escribir(self, texto):
        self.salida.configure(state="normal")
        self.salida.insert(tk.END, texto + "\n")
        self.salida.see(tk.END)
        self.salida.configure(state="disabled")

    def ejecutar(self, nombre, funcion):
        self.estado.set(f"Ejecutando {nombre}...")
        self.escribir(f"Iniciando {nombre}")
        threading.Thread(target=self._trabajo, args=(nombre, funcion), daemon=True).start()

    def _trabajo(self, nombre, funcion):
        try:
            funcion()
            self.ventana.after(0, lambda: self.termino(nombre, "completada"))
        except Exception as error:
            self.ventana.after(0, lambda: self.termino(nombre, f"error: {error}"))

    def alerta(self, metrica):
        if metrica == "todos":
            sensores = (("CPU", "cpu"), ("RAM", "memoria"),
                        ("DISCO", "disco"), ("PROCESOS", "procesos"),
                        ("RED", "red"), ("BATERIA", "bateria"))
            resultado = " | ".join(
                f"{nombre}: {simular_alerta(sensor)}"
                for nombre, sensor in sensores
            )
            nombre = "todos los sensores"
        else:
            nombre = {"memoria": "RAM", "disco": "DISCO",
                      "procesos": "PROCESOS", "cpu": "CPU"}[metrica]
            resultado = simular_alerta(metrica)
        self.estado.set(f"Prueba de {nombre} generada")
        self.escribir(f"{nombre}: {resultado}")
        self._sondear_sonidos()

    def _sondear_sonidos(self):
        sonidos.actualizar()
        if sonidos.hay_pendientes() and not self.sonidos_programados:
            self.sonidos_programados = True
            self.ventana.after(100, self._actualizar_sonidos)

    def _actualizar_sonidos(self):
        self.sonidos_programados = False
        self._sondear_sonidos()

    def termino(self, nombre, resultado):
        self.estado.set(f"{nombre}: {resultado}")
        self.escribir(f"{nombre}: {resultado}")


def main():
    raiz = tk.Tk()
    GeneradorVentana(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
