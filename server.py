# =============================================================================
#  BLOQUE 0: PRÓLOGO Y CONFIGURACIÓN GLOBAL
#  - Imports de módulos estándar y de Flask.
#  - Definición de constantes: UPLOAD_FOLDER, OUTBOX_FOLDER, PORT.
#  - Instancia de la aplicación Flask.
# =============================================================================
import os
import re
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort, send_from_directory

# Constantes de carpetas y puerto
UPLOAD_FOLDER = "uploads"
OUTBOX_FOLDER = "outbox"
PORT = 5000

# Instancia principal de la aplicación Flask
app = Flask(__name__)

# =============================================================================
#  BLOQUE 1: GESTIÓN DEL ESTADO EN MEMORIA (COLA DE PUSH)
#  - Variable global push_queue = []
#  - Función enqueue_file(filename, raw_data)
#  - Función peek_queue()
#  - Función pop_if_match(filename)
# =============================================================================
# Cola global de archivos pendientes de enviar
push_queue = []

def enqueue_file(filename, raw_data):
    """
    Añade un archivo a la cola de push.
    """
    push_queue.append({
        'filename': filename,
        'data': raw_data
    })

def peek_queue():
    """
    Devuelve el primer elemento de la cola sin eliminarlo.
    Si la cola está vacía, devuelve None.
    """
    if not push_queue:
        return None
    return push_queue[0]

def pop_if_match(filename):
    """
    Elimina y devuelve el primer elemento de la cola si su nombre coincide con 'filename'.
    Si no coincide o la cola está vacía, devuelve None.
    """
    if not push_queue:
        return None
    if push_queue[0]['filename'] == filename:
        return push_queue.pop(0)
    return None


# =============================================================================
#  BLOQUE 2: UTILIDADES DE RED (DETECCIÓN DEL HOTSPOT)
#  - Función detect_hotspot_ip()
# =============================================================================

def detect_hotspot_ip():
    """
    Detecta la dirección IP del adaptador del Hotspot en Windows.
    Prioridad:
    1. Busca la IP típica del Hotspot: 192.168.137.1
    2. Si no, busca cualquier IP privada (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
       en interfaces que no sean loopback.
    3. Si no encuentra nada, devuelve '127.0.0.1' (fallback) y muestra advertencia.
    """
    try:
        # 1. Ejecutar ipconfig y capturar salida
        output = subprocess.check_output(['ipconfig'], encoding='cp850', errors='ignore')
        
        # 2. Buscar primero la IP del Hotspot por defecto (más común)
        hotspot_match = re.search(r'192\.168\.137\.\d{1,3}', output)
        if hotspot_match:
            return hotspot_match.group(0)
        
        # 3. Si no está, buscar cualquier IPv4 privada en interfaces activas
        #    Las IP privadas tienen estos rangos:
        #      - 10.0.0.0/8
        #      - 172.16.0.0/12 (172.16.x.x - 172.31.x.x)
        #      - 192.168.0.0/16
        #    Usamos una expresión regular que captura estas direcciones,
        #    pero evitando la loopback (127.x.x.x).
        private_ip_pattern = re.compile(
            r'\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
            r'172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|'
            r'192\.168\.\d{1,3}\.\d{1,3})\b'
        )
        
        # Buscar todas las IPs privadas en la salida
        matches = private_ip_pattern.findall(output)
        
        # Filtrar para quedarnos con la primera que no sea loopback (aunque el patrón ya lo excluye)
        for ip in matches:
            # En el caso de que el findall devuelva tuplas por los grupos de captura,
            # convertimos a string limpio.
            if isinstance(ip, tuple):
                ip = ip[0]
            # Descartar 127.0.0.1 por si acaso
            if ip != '127.0.0.1':
                return ip
        
        # 4. Fallback: no se encontró IP privada
        print("⚠️  No se pudo detectar la IP del Hotspot automáticamente.")
        print("   Usando 127.0.0.1 (localhost). Asegúrate de que el móvil use la IP correcta.")
        return '127.0.0.1'
    
    except subprocess.CalledProcessError:
        # Si ipconfig falla (muy raro), también fallback
        print("❌ Error al ejecutar ipconfig. Usando 127.0.0.1 por defecto.")
        return '127.0.0.1'
    except Exception as e:
        # Cualquier otro error inesperado
        print(f"❌ Error inesperado al detectar IP: {e}")
        return '127.0.0.1'

    
# =============================================================================
#  BLOQUE 3: ORQUESTADOR DE ARCHIVOS (MONITOR DE OUTBOX)
#  - Función process_outbox()
#    (Escanea outbox, lee archivos, los encola y los elimina del disco)
# =============================================================================

def process_outbox():
    """
    Escanea la carpeta OUTBOX_FOLDER en busca de archivos.
    Por cada archivo encontrado:
      - Lo lee en memoria (bytes)
      - Lo encola usando enqueue_file()
      - Lo elimina del disco
    Esta función se ejecuta antes de cada petición HTTP.
    """
    # Verificar que la carpeta existe
    if not os.path.exists(OUTBOX_FOLDER):
        return  # Si no existe, no hacemos nada (ya se creará en el arranque)
    
    try:
        # Listar todos los archivos en outbox
        files = os.listdir(OUTBOX_FOLDER)
        if not files:
            return  # Carpeta vacía, salir
        
        for filename in files:
            file_path = os.path.join(OUTBOX_FOLDER, filename)
            
            # Saltar directorios (por si acaso)
            if os.path.isdir(file_path):
                continue
            
            try:
                # Leer el archivo completo en memoria
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                # Encolar el archivo (usando el Bloque 1)
                enqueue_file(filename, file_data)
                
                # Eliminar el archivo del disco (purga)
                os.remove(file_path)
                
                # Log en consola (opcional, útil para depuración)
                print(f"📤 Archivo '{filename}' encolado para envío ({len(file_data)} bytes)")
                
            except Exception as e:
                # Si falla un archivo, lo dejamos en outbox y seguimos con los demás
                print(f"⚠️ Error al procesar '{filename}': {e}")
                continue
                
    except Exception as e:
        # Error general al listar la carpeta
        print(f"❌ Error al escanear outbox: {e}")

# Registrar la función para que se ejecute ANTES de cada petición
app.before_request(process_outbox)


# =============================================================================
#  BLOQUE 4: LA INTERFAZ DE USUARIO (FRONTEND)
#  - Carga el HTML desde un archivo externo para mantener el código limpio.
# =============================================================================

def load_html_page():
    """Carga el contenido del archivo templates/index.html."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {template_path}")
        print("   Asegúrate de que existe la carpeta 'templates' y dentro el archivo 'index.html'.")
        # Fallback: mensaje de error simple (para que el servidor no explote)
        return "<h1>Error: No se encontró la página HTML.</h1>"
    except Exception as e:
        print(f"❌ Error al leer {template_path}: {e}")
        return f"<h1>Error al cargar la página: {e}</h1>"

# Cargar el HTML una sola vez al iniciar el servidor (o cada vez que se necesite)
HTML_PAGE = load_html_page()


# =============================================================================
#  BLOQUE 5: CONTROLADORES DE RUTAS (PARTE 1 - RAÍZ Y SUBIDA)
#  - @app.route('/') -> index()
#  - @app.route('/upload', methods=['POST']) -> upload_file()
# =============================================================================

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Recibe un archivo desde el móvil y lo guarda en UPLOAD_FOLDER.
    Si el nombre ya existe, añade un sufijo numérico (ej. archivo(1).ext).
    """
    # Verificar que se envió un archivo
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No se envió ningún archivo'}), 400
    
    file = request.files['file']
    
    # Si el usuario no seleccionó archivo (nombre vacío)
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'Nombre de archivo vacío'}), 400
    
    # Obtener el nombre original y limpiarlo (eliminar rutas)
    original_filename = file.filename
    # Por seguridad, extraemos solo el nombre base
    safe_filename = os.path.basename(original_filename)
    
    # Construir la ruta de destino
    base, ext = os.path.splitext(safe_filename)
    dest_path = os.path.join(UPLOAD_FOLDER, safe_filename)
    counter = 1
    
    # Si ya existe, buscar un nombre alternativo
    while os.path.exists(dest_path):
        new_name = f"{base}({counter}){ext}"
        dest_path = os.path.join(UPLOAD_FOLDER, new_name)
        counter += 1
    
    try:
        file.save(dest_path)
        # Respuesta exitosa con el nombre final guardado
        final_filename = os.path.basename(dest_path)
        return jsonify({'ok': True, 'filename': final_filename})
    except Exception as e:
        # Error al guardar
        return jsonify({'ok': False, 'error': f'Error al guardar: {str(e)}'}), 500

# =============================================================================
#  BLOQUE 6: CONTROLADORES DE RUTAS (PARTE 2 - POLLING Y PUSH)
#  - @app.route('/poll') -> poll_queue()
#  - @app.route('/download_push/<filename>') -> download_push(filename)
# =============================================================================

@app.route('/poll')
def poll_queue():
    """
    Endpoint para que el móvil consulte si hay archivos pendientes.
    Responde con JSON:
      - Si no hay: {"pending": false}
      - Si hay: {"pending": true, "filename": "archivo.txt", "size": 1234}
    """
    # Usar peek_queue() del Bloque 1 para ver el primer elemento sin eliminarlo
    item = peek_queue()
    if item is None:
        return jsonify({'pending': False})
    else:
        return jsonify({
            'pending': True,
            'filename': item['filename'],
            'size': len(item['data'])
        })


@app.route('/download_push/<filename>')
def download_push(filename):
    """
    Endpoint para descargar el archivo que está en la cabecera de la cola.
    Solo permite la descarga si el nombre coincide con el primer elemento de la cola.
    Si coincide, sirve el archivo y lo elimina de la cola.
    Si no coincide o la cola está vacía, devuelve 404.
    """
    # Intentar consumir el primer elemento si coincide con el nombre
    item = pop_if_match(filename)
    if item is None:
        # No coincide o cola vacía
        abort(404, description="Archivo no encontrado en la cola")
    
    # Construir la respuesta con los datos binarios
    from flask import Response
    response = Response(
        item['data'],
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="{item["filename"]}"'
        }
    )
    return response

# =============================================================================
#  (BLOQUE 8: GESTIÓN DE ERRORES Y LOGS - TRANSVERSAL)
#  - Decoradores @app.errorhandler (si se usan)
#  - try/except y prints estratégicos dentro de los bloques 3, 5 y 6.
#  - No tiene una sección fija; se esparce donde sea necesario.
# =============================================================================

# =============================================================================
#  BLOQUE 7: ARRANQUE Y PUESTA EN MARCHA (BOOTSTRAPPER)
#  - Función main() con toda la lógica de arranque.
#  - if __name__ == "__main__": main()
# =============================================================================

def main():
    """Función principal que orquesta el arranque del servidor."""
    # 1. Detectar la IP del Hotspot
    ip = detect_hotspot_ip()
    
    # 2. Crear las carpetas necesarias (si no existen)
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(OUTBOX_FOLDER, exist_ok=True)
    except Exception as e:
        print(f"❌ Error al crear las carpetas: {e}")
        print("   Verifica que tienes permisos de escritura en el directorio.")
        exit(1)
    
    # 3. Mostrar información en consola
    print("=" * 60)
    print("  🚀 SERVIDOR DE TRANSFERENCIA LIGERO (MVP)")
    print("=" * 60)
    print(f"🌐 Servidor listo en: http://{ip}:{PORT}")
    print(f"📂 Archivos subidos se guardan en: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"📤 Coloca archivos en: {os.path.abspath(OUTBOX_FOLDER)} para enviar al móvil")
    print(f"📱 El móvil debe abrir la URL desde el navegador")
    print(f"⏹️  Presiona Ctrl+C para detener el servidor")
    print("=" * 60)
    print("Esperando conexiones...")
    
    # 4. Lanzar el servidor Flask
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=False)


if __name__ == "__main__":
    main()