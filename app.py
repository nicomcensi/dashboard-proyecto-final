import base64
import sqlite3
import pandas as pd
import plotly.express as px
from flask import Flask, redirect, render_template, request, session, url_for
import dash
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output, State

# 1. CONFIGURACIÓN INICIAL
server = Flask(__name__, template_folder='templates')
server.secret_key = 'timoteo'

# 2. CREACIÓN DE LA APP DE DASH
# Defino la hoja de estilos que quiero usar
external_stylesheets = ['https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css']

app = dash.Dash(
    __name__, 
    server=server, 
    url_base_pathname='/dashboard/',
    external_stylesheets=external_stylesheets
)


# 3. CARGA Y PREPARACIÓN DE DATOS
try:
    conn = sqlite3.connect('dashboard.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()

    # errors='coerce' convierte las fechas inválidas en 'NaT' (Not a Time) en lugar de dar error.
    df['fecha_venta'] = pd.to_datetime(df['fecha_venta'], errors='coerce')
    # Eliminamos cualquier fila que tenga una fecha inválida (NaT)
    df.dropna(subset=['fecha_venta'], inplace=True)
    

    df['mes'] = df['fecha_venta'].dt.strftime('%Y-%m')
    
    opciones_mes = [{'label': mes, 'value': mes} for mes in sorted(df['mes'].unique(), reverse=True)]
    opciones_generales = [{'label': 'Últimos 90 días', 'value': '90d'}]
    opciones_filtro = opciones_generales + opciones_mes

    diccionario_categorias = {'AB': 'Aceto Balsámico', 'AC': 'Aceites de Oliva', 'AL': 'Alimentos', 'AR': 'Artículos Refrigerados', 'BA': 'Bebidas Alcohólicas', 'VI': 'Vinos'}
    df['id_producto'] = df['id_producto'].astype(str)
    df['categoria_principal'] = df['id_producto'].str[:2].map(diccionario_categorias)
    df['facturacion'] = df['cantidad_vendida'] * df['precio_unitario_final']

    df_productos = df.groupby('nombre_producto')['facturacion'].sum().sort_values(ascending=False).reset_index()
    total_ventas = df_productos['facturacion'].sum()
    df_productos['porcentaje_acumulado'] = df_productos['facturacion'].cumsum() / total_ventas
    def clasificar_abc(porcentaje):
        if porcentaje <= 0.8: return 'A'
        elif porcentaje <= 0.95: return 'B'
        else: return 'C'
    df_productos['clase_abc'] = df_productos['porcentaje_acumulado'].apply(clasificar_abc)
    df = pd.merge(df, df_productos[['nombre_producto', 'clase_abc']], on='nombre_producto', how='left')
    
    DATA_LOADED = True
except Exception as e:
    print(f"Error cargando los datos: {e}")
    df = pd.DataFrame()
    DATA_LOADED = False
    opciones_filtro = [{'label': 'Error cargando datos', 'value': 'error'}]

# 4. LAYOUT DE LA APP DE DASH 
app.layout = html.Div(children=[
    dcc.Store(id='memoria-clase'),
    html.Div([
        html.H1('Dashboard de Análisis Estratégico'),
        html.A("Cerrar Sesión", href="/logout", style={'marginLeft': '20px'})
    ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}),
    
    html.Div([
        html.Label('Seleccionar Período:'),
        dcc.Dropdown(
            id='filtro-tiempo',
            options=opciones_filtro,
            value='90d', # Valor por defecto
            clearable=False
        )
    ], style={'width': '30%', 'marginBottom': '20px'}),
    
    html.Hr(),
    dcc.Graph(id='grafico-pareto'),
    html.Hr(),
    html.Div(id='contenedor-intermedio', style={'display': 'none'}, children=[
        html.H2('Desglose por Categoría'),
        dcc.Graph(id='grafico-desglose-categoria')
    ]),
    html.Hr(),
    html.Div(id='contenedor-tabla', style={'display': 'none'})
], style={'padding': '10px'})

# --- 5. CALLBACKS (Interactividad) ---

# Callback 1: Se activa cuando cambia el filtro de tiempo.
@app.callback(
    Output('grafico-pareto', 'figure'), # Actualiza el gráfico principal
    Input('filtro-tiempo', 'value')   # Se dispara con el cambio del dropdown
)
def actualizar_grafico_pareto(periodo_seleccionado):
    """
    Filtra los datos según el período seleccionado y genera el gráfico de Pareto
    mostrando la FACTURACIÓN por clase y el total.
    """
    # 1. Filtra el DataFrame principal según la selección de tiempo.
    if periodo_seleccionado == '90d':
        fecha_maxima = df['fecha_venta'].max()
        df_filtrado_tiempo = df[df['fecha_venta'] > fecha_maxima - pd.to_timedelta('90day')]
    else:
        df_filtrado_tiempo = df[df['mes'] == periodo_seleccionado]

    # Si no hay datos para el período, muestra un gráfico vacío.
    if df_filtrado_tiempo.empty:
        return px.bar(title='No hay datos para el período seleccionado')

    # 2. Recalcula la clasificación ABC usando solo los datos filtrados.
    df_prods_filt = df_filtrado_tiempo.groupby('nombre_producto')['facturacion'].sum().sort_values(ascending=False).reset_index()
    total_ventas_filt = df_prods_filt['facturacion'].sum()
    df_prods_filt['porcentaje_acumulado'] = df_prods_filt['facturacion'].cumsum() / total_ventas_filt
    df_prods_filt['clase_abc'] = df_prods_filt['porcentaje_acumulado'].apply(clasificar_abc)

    # 3. Calcula la FACTURACIÓN por cada clase (A, B, C).
    df_pareto_facturacion = df_prods_filt.groupby('clase_abc')['facturacion'].sum().reset_index()

    # 4. Genera el nuevo gráfico de Pareto basado en facturación.
    titulo_grafico = f"Facturación por Clase para: {periodo_seleccionado} (Total: ${total_ventas_filt:,.2f})"
    figura_pareto_actualizada = px.bar(
        df_pareto_facturacion,
        x='clase_abc',
        y='facturacion',
        title=titulo_grafico,
        labels={'clase_abc': 'Clase', 'facturacion': 'Facturación Total'},
        text_auto='.2s' # Formato para mostrar el valor en la barra
    )
    figura_pareto_actualizada.update_layout(xaxis={'categoryorder':'array', 'categoryarray':['A', 'B', 'C']})

    return figura_pareto_actualizada


# Callback 2: Se activa al hacer clic en el gráfico de Pareto (Drill-down Nivel 1)
@app.callback(
    [Output('grafico-desglose-categoria', 'figure'),
     Output('contenedor-intermedio', 'style'),
     Output('memoria-clase', 'data')],
    [Input('grafico-pareto', 'clickData')],
    [State('filtro-tiempo', 'value')] # Necesita saber el período de tiempo actual
)
def actualizar_grafico_categoria(clickData, periodo_seleccionado):
    """
    Genera el gráfico de torta de desglose por categoría, respetando el filtro de tiempo.
    """
    if clickData is None:
        return dash.no_update, {'display': 'none'}, None
    
    # Filtra los datos por el período de tiempo seleccionado
    if periodo_seleccionado == '90d':
        fecha_maxima = df['fecha_venta'].max()
        df_filtrado_tiempo = df[df['fecha_venta'] > fecha_maxima - pd.to_timedelta('90day')]
    else:
        df_filtrado_tiempo = df[df['mes'] == periodo_seleccionado]

    clase_seleccionada = clickData['points'][0]['x']
    df_filtrado_clase = df_filtrado_tiempo[df_filtrado_tiempo['clase_abc'] == clase_seleccionada]
    df_desglose = df_filtrado_clase.groupby('categoria_principal')['facturacion'].sum().reset_index()
    
    fig_desglose = px.pie(
        df_desglose,
        names='categoria_principal',
        values='facturacion',
        title=f'Facturación en Clase "{clase_seleccionada}" por Categoría'
    )
    
    return fig_desglose, {'display': 'block'}, clase_seleccionada

# Callback 3: Se activa al hacer clic en el gráfico de categorías

@app.callback(
    [Output('contenedor-tabla', 'children'),
     Output('contenedor-tabla', 'style')],
    [Input('grafico-desglose-categoria', 'clickData')],
    [State('memoria-clase', 'data'),
     State('filtro-tiempo', 'value')]
)
def actualizar_tabla(clickData, clase_seleccionada, periodo_seleccionado):
    if clickData is None or clase_seleccionada is None:
        return [], {'display': 'none'}

    # 1. Filtra los datos por el período de tiempo
    if periodo_seleccionado == '90d':
        fecha_maxima = df['fecha_venta'].max()
        df_filtrado_tiempo = df[df['fecha_venta'] > fecha_maxima - pd.to_timedelta('90day')]
    else:
        df_filtrado_tiempo = df[df['mes'] == periodo_seleccionado]

    categoria_seleccionada = clickData['points'][0]['label']
    
    # 2. Doble filtro por clase y categoría
    df_filtrado_final = df_filtrado_tiempo[(df_filtrado_tiempo['clase_abc'] == clase_seleccionada) & (df_filtrado_tiempo['categoria_principal'] == categoria_seleccionada)]
    
    # 3. Agrupa para obtener facturación, unidades vendidas Y EL STOCK
    df_tabla = df_filtrado_final.groupby(['id_producto', 'nombre_producto', 'subcategoria', 'unidad_de_medida']).agg(
        facturacion=('facturacion', 'sum'),
        unidades_vendidas=('cantidad_vendida', 'sum'),
        unidades_stock=('unidades_stock', 'first') # Tomamos el primer valor de stock (debería ser el mismo para el mismo producto)
    ).reset_index()

    # 4. Función para calcular y clasificar la rotación
    def calcular_rotacion(row):
        try:
            stock = 0 if row['unidades_stock'] < 0 else row['unidades_stock']
            if stock == 0:
                return "Agotado" if row['unidades_vendidas'] > 0 else "Inactivo"
            rotacion = row['unidades_vendidas'] / stock
            if row['unidad_de_medida'] == 'Unidad':
                if rotacion >= 0.5: return "Saludable"
                elif rotacion >= 0.1: return "Lento"
                else: return "Estancado"
            elif row['unidad_de_medida'] == 'Kg':
                if rotacion >= 0.2: return "Saludable"
                elif rotacion >= 0.05: return "Lento"
                else: return "Estancado"
            else: return "Sin UDM"
        except Exception as e:
            print(f"Error calculando rotación para el producto {row['id_producto']}: {e}")
            return "Error Calc."

    df_tabla['rotacion_stock'] = df_tabla.apply(calcular_rotacion, axis=1)
    df_tabla = df_tabla.sort_values(by='facturacion', ascending=False).round(2)
    
    # 5. Creamos la tabla y añadimos el formato condicional
    titulo_tabla = html.H2(f"Detalle: Clase '{clase_seleccionada}', Categoría '{categoria_seleccionada}'")
    tabla = dash_table.DataTable(
        columns=[
            {"name": "Producto", "id": "nombre_producto"},
            {"name": "Subcategoría", "id": "subcategoria"},
            {"name": "Facturación", "id": "facturacion"},
            {"name": "Rotación de Stock", "id": "rotacion_stock"},
        ],
        data=df_tabla.to_dict('records'),
        sort_action="native", page_size=10, style_table={'overflowX': 'auto'},
        style_data_conditional=[
            {'if': {'filter_query': '{rotacion_stock} = "Saludable"'}, 'backgroundColor': '#d4edda', 'color': '#155724'},
            {'if': {'filter_query': '{rotacion_stock} = "Agotado"'}, 'backgroundColor': '#cce5ff', 'color': '#004085'},
            {'if': {'filter_query': '{rotacion_stock} = "Lento"'}, 'backgroundColor': '#fff3cd', 'color': '#856404'},
            {'if': {'filter_query': '{rotacion_stock} = "Estancado"'}, 'backgroundColor': '#f8d7da', 'color': '#721c24'},
            {'if': {'filter_query': '{rotacion_stock} = "Inactivo"'}, 'backgroundColor': '#e2e3e5', 'color': '#383d41'},
        ]
    )
    
    return [titulo_tabla, tabla], {'display': 'block'}
# 6. RUTAS DE FLASK (Control de Acceso)
@server.route('/')
def home():
    """
    Ruta principal. Redirige al dashboard si el usuario ya inició sesión,
    o a la página de login si no.
    """
    if 'username' in session:
        return redirect('/dashboard')
    else:
        return redirect(url_for('login'))

@server.route('/login', methods=['GET', 'POST'])
def login():
    """
    Muestra el formulario de login (GET) y procesa el inicio de sesión (POST).
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('dashboard.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM usuarios WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        if user:
            password_guardada = base64.b64decode(user[0]).decode('utf-8')
            if password == password_guardada:
                session['username'] = username
                return redirect('/dashboard')
        return render_template('login.html', error='Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@server.route('/logout')
def logout():
    """
    Cierra la sesión del usuario y lo redirige al login.
    """
    session.pop('username', None)
    return redirect(url_for('login'))

@server.route('/dashboard')
def render_dashboard():
    """
    Protege y sirve la aplicación de Dash. Solo es accesible si el usuario
    ha iniciado sesión.
    """
    if 'username' in session:
        return app.index()
    else:
        return redirect(url_for('login'))


# 7. EJECUTAR LA APP
if __name__ == '__main__':
    server.run(debug=True)