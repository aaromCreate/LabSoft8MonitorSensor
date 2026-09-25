""" 
sensores/red.py 
Trafico de red. 
  
Cuidado con esta metrica: psutil.net_io_counters() NO devuelve una 
velocidad, devuelve un contador acumulado desde que arranco el equipo. 
Para obtener KB/s hay que restar la lectura anterior y dividir entre el 
tiempo transcurrido. Es el mismo patron 'valor actual menos valor 
anterior' que se usa para detectar flancos. 
""" 
  
import time 
import ipaddress
import socket
import subprocess
import psutil 
  
ETIQUETA = "Red" 
UNIDAD = "KB/s" 
  
KB = 1024.0 
MB = 1024.0 ** 2 
  
# Estado anterior: sin el, no se puede calcular una velocidad. 
_anterior = {"enviados": 0, "recibidos": 0, "marca": 0.0} 
_iniciado = False
# LABORATORIO
def _wifi_conectada():
    try:
        resultado = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    for linea in resultado.stdout.splitlines():
        clave, separador, valor = linea.partition(":")
        if separador and clave.strip().lower() in ("state", "estado"):
            return valor.strip().lower() in ("connected", "conectado")
    return None


def conectada():
    try:
        wifi = _wifi_conectada()
        if wifi is not None:
            return wifi

        for nombre, datos in psutil.net_if_stats().items():
            if not datos.isup:
                continue
            for direccion in psutil.net_if_addrs().get(nombre, []):
                if direccion.family != socket.AF_INET:
                    continue
                ip = ipaddress.ip_address(direccion.address)
                if not ip.is_loopback and not ip.is_link_local:
                    return True
        return False
    except Exception:
        return False
  
  
def disponible(): 
    try: 
        return psutil.net_io_counters() is not None 
    except Exception: 
        return False 
  
  
def _iniciar(): 
    global _iniciado 
    c = psutil.net_io_counters() 
    _anterior.update({"enviados": c.bytes_sent, 
                      "recibidos": c.bytes_recv, 
                      "marca": time.time()}) 
    _iniciado = True 
  
  
def leer(): 
    global _iniciado 
    if not _iniciado: 
        _iniciar() 
        return None          # la primera vuelta no alcanza para una velocidad 
  
    try: 
        c = psutil.net_io_counters() 
    except Exception: 
        return None 
  
    ahora = time.time() 
    transcurrido = ahora - _anterior["marca"] 
    if transcurrido <= 0: 
        return None 
  
    subida = (c.bytes_sent - _anterior["enviados"]) / KB / transcurrido 
    bajada = (c.bytes_recv - _anterior["recibidos"]) / KB / transcurrido 
  
    _anterior.update({"enviados": c.bytes_sent, 
                      "recibidos": c.bytes_recv, 
                      "marca": ahora}) 
  
    total = subida + bajada 
    # La barra se escala contra el doble del umbral de pico. 
    import config 
    tope = max(config.RED_PICO_KBS * 2, 1.0) 
  
    return { 
        "valor": round(total, 1), 
        "unidad": UNIDAD, 
        "porcentaje": min(100.0, total / tope * 100.0), 
        "detalle": (f"sube {subida:.1f} | baja {bajada:.1f} KB/s | " 
                    f"total {(c.bytes_sent + c.bytes_recv) / MB:.0f} MB"), 
        "extra": {"subida_kbs": round(subida, 1), 
                  "bajada_kbs": round(bajada, 1)}, 
    }