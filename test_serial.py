import serial

# Ouvrir le port série
ser = serial.Serial('/dev/serial0', 9600, timeout = 2, bytesize=8, parity=serial.PARITY_NONE , stopbits=1)

# Écrire un message sur le port série
# message = "Salut, je suis un Raspberry Pi !"
# ser.write(message.encode())
# ser.write(message.encode())
# message = bytearray([0xaa, 5, 6, 1, 0, 0, 0, 0, 0, 0, 0xbb])
# ser.write(message)
# Fermer le port série
for i in range(65, 66):
    ser.write(bytes([i]))
    print(bytes([i])) 
data = ser.read(1)  # Lire 1 octet de données
if data:
    # Convertir les données en chaîne de caractères et les afficher sur le log
    data_str = data.decode('latin-1')
    print(data_str  )    
ser.close()