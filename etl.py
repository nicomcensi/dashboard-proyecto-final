import pandas as pd
import sqlite3

# 1. EXTRACCIÓN (Leemos los archivos de Excel)

# Definimos los nombres de los archivos para que sea fácil modificarlos
archivo_ventas = 'data/EnoBoutique-VentasJunio-Sept-12.09.xlsx'
archivo_stock = 'data/EnoBoutique-StockActual-12.09.xlsx'
archivo_mapeo_productos = 'data/Mapeo de Productos.xlsx'
archivo_catalogo_subcategorias = 'data/Catalogo de Subcategorias.xlsx'

# Leemos cada archivo Excel y lo cargamos en un DataFrame
df_ventas = pd.read_excel(archivo_ventas)
df_stock = pd.read_excel(archivo_stock)
df_mapeo_productos = pd.read_excel(archivo_mapeo_productos)
df_catalogo_subcategorias = pd.read_excel(archivo_catalogo_subcategorias)

# Imprimimos las primeras filas de cada tabla para verificar que se cargaron bien
print("Ventas cargadas:")
print(df_ventas.head())
print("\nStock cargado:")
print(df_stock.head())
print("\nMapeo de Productos cargado:")
print(df_mapeo_productos.head())
print("\nCatálogo de Subcategorías cargado:")
print(df_catalogo_subcategorias.head())

# 2. TRANSFORMACIÓN (Limpiamos y preparamos los datos) 

# Limpieza de Stock 
# Negativos se convierten a 0 y nulos se rellenan con 0
print("\nLimpiando datos de stock...")
df_stock['unidades_stock'] = df_stock['unidades_stock'].clip(lower=0).fillna(0) # .clip(lower=0) convierte negativos a 0. fillna(0) convierte nulos a 0.
print("Verificación de Stock: El valor mínimo ahora debería ser 0.")
print(df_stock['unidades_stock'].describe()) #Si en el resultado de .describe() vemos que el valor min es 0.0, tenemos la confirmación instantánea de que nuestra limpieza funcionó perfectamente.


# Limpieza de Ventas 
# Mantenemos únicamente las filas donde la cantidad vendida es mayor que cero
print("\nLimpiando datos de ventas...")
filas_originales = len(df_ventas)
df_ventas = df_ventas[df_ventas['cantidad_vendida'] > 0] #crea una nueva tabla de ventas que contiene únicamente las filas donde la venta fue de una cantidad positiva, descartando todo lo demás.
filas_limpias = len(df_ventas)
print(f"Se eliminaron {filas_originales - filas_limpias} filas de ventas inválidas.")


# Estandarización de IDs 
# Las convertiremos a texto (string)
df_ventas['id_producto'] = df_ventas['id_producto'].astype(str)
df_stock['id_producto'] = df_stock['id_producto'].astype(str)
df_mapeo_productos['id_producto'] = df_mapeo_productos['id_producto'].astype(str)

print("\nLimpieza y estandarización completadas")

# 3. COMBINACIÓN (Unimos todas las tablas en una sola) 

print("\nCombinando todas las tablas...")

# Unión 1: Añadimos la info del mapeo (nombre, subcat) a las ventas.
# Usamos un 'left' join para asegurarnos de mantener todas las ventas,
# incluso si un producto, por error, no estuviera en el archivo de mapeo.
df_combinado = pd.merge(df_ventas, df_mapeo_productos, on='id_producto', how='left')

# Unión 2: Añadimos la unidad de medida usando la subcategoría.
df_combinado = pd.merge(df_combinado, df_catalogo_subcategorias, on='subcategoria', how='left')

# Unión 3: Añadimos la información del stock actual.
df_final = pd.merge(df_combinado, df_stock, on='id_producto', how='left')

# Rellenamos posibles nulos que hayan surgido de las uniones.
# Por ejemplo, si un producto vendido no tiene stock registrado, le ponemos 0.
df_final['unidades_stock'] = df_final['unidades_stock'].fillna(0)


# Verificamos la tabla final
print("\nTodas las tablas han sido combinadas")
print("Información de nuestra tabla maestra:")
df_final.info()

print("\nPrimeras 5 filas de la tabla maestra:")
print(df_final.head())

# 4. CARGA (Load - Guardar en la base de datos) 

print("\nGuardando datos limpios en la base de datos...")

# Nombre para nuestro archivo de base de datos
nombre_db = 'dashboard.db'

# Creamos la conexión
conexion = sqlite3.connect(nombre_db)

# Usamos la función to_sql de pandas para guardar nuestro DataFrame en una tabla SQL.
# 'if_exists='replace'' significa que si la tabla ya existe, la borrará y creará de nuevo.
df_final.to_sql(
    name='ventas',          # Le daremos este nombre a la tabla dentro de la base de datos
    con=conexion,
    if_exists='replace',
    index=False
)

conexion.close()

print(f"Proceso ETL completado.Tus datos están listos en el archivo '{nombre_db}'")