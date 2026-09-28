import os
import time
import shutil

ruta = "prueba_disco.tmp"

total, usado, libre = shutil.disk_usage(".")
porcentaje = usado / total * 100

print(f"Uso actual: {porcentaje:.2f}%")

necesario = int(total * 0.91) - usado

if necesario > 0:
    print(f"Escribiendo {necesario / (1024**3):.2f} GB...")

    bloque = b"0" * (16 * 1024 * 1024)  # 16 MB
    escritos = 0

    with open(ruta, "wb", buffering=16 * 1024 * 1024) as f:
        while escritos < necesario:
            cantidad = min(len(bloque), necesario - escritos)
            f.write(bloque[:cantidad])
            escritos += cantidad

    print("¡Superado el 90%!")
    time.sleep(2)

    os.remove(ruta)
    print("Prueba terminada.")
else:
    print("Ya estás por encima del 90%.")