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
    if metrica == "memoria":
        valor = config.RAM_ALTA + 5
        for _ in range(config.VENTANA):
            registro.agregar(metrica, valor)
        lectura = {"valor": valor, "extra": {"usa_swap": True, "swap_pct": 50.0}}
    else:
        valor = config.DISCO_LLENO + 1
        for _ in range(config.VENTANA):
            registro.agregar(metrica, valor)
        lectura = {"valor": valor}
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

        marco = ttk.Frame(ventana, padding=14)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="Generador de pruebas", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(marco, text="Ejecuta cada prueba en segundo plano.").pack(anchor="w", pady=(2, 12))

        botones = ttk.Frame(marco)
        botones.pack(fill="x")
        for texto, funcion in (("CPU", cargar_cpu), ("RAM", cargar_memoria),
                               ("Disco", cargar_disco), ("Procesos", abrir_procesos)):
            ttk.Button(botones, text=texto,
                       command=lambda f=funcion, n=texto: self.ejecutar(n, f)).pack(side="left", padx=3)

        alertas = ttk.Frame(marco)
        alertas.pack(fill="x", pady=8)
        for texto, metrica in (("Alerta RAM", "memoria"), ("Alerta disco", "disco")):
            ttk.Button(alertas, text=texto,
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
        nombre = "RAM" if metrica == "memoria" else "disco"
        resultado = simular_alerta(metrica)
        self.estado.set(f"Alerta {nombre} generada")
        self.escribir(f"Alerta {nombre}: {resultado}")

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
