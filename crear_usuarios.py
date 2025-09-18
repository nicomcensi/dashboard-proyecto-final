import sqlite3
import base64
from getpass import getpass

print("--- Añadir Nuevos Usuarios ---")

# Pedimos los datos del nuevo usuario
username = input("Introduce el nombre del nuevo usuario: ")
password = getpass("Introduce la contraseña para el nuevo usuario: ")

if not username or not password:
    print("El nombre de usuario y la contraseña no pueden estar vacíos.")
else:
    try:
        # Conectamos a la base de datos
        conn = sqlite3.connect('dashboard.db')
        cursor = conn.cursor()

        
        # Nos aseguramos de que la tabla 'usuarios' exista antes de intentar insertar
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        ''')

        # Codificamos la contraseña en Base64
        password_encoded = base64.b64encode(password.encode('utf-8')).decode('utf-8')

        # Intentamos insertar el nuevo usuario
        cursor.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)", (username, password_encoded))
        
        conn.commit()
        
        # Verificamos si la fila fue insertada
        if cursor.rowcount > 0:
            print(f"\nEl usuario '{username}' fue añadido a la base de datos.")
        else:
            print(f"\nEl usuario '{username}' ya existía. No se realizaron cambios.")

        conn.close()

    except Exception as e:
        print(f"\nOcurrió un error: {e}")