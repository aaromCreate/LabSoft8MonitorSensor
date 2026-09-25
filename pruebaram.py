import time

bloques = []

print("Consumiento memoria...")

for i in range(20):
    bloques.append(bytearray(500 * 1024 * 1024))
    print(f"Reservados aproximadamente {(i + 1) * 100} MB")
    time.sleep(1)

print("Manteniendo memoria ocupada...")
time.sleep(60)