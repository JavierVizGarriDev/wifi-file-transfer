import unittest
import subprocess
import os
import tempfile
import io
from server import main
from unittest.mock import patch, MagicMock
from server import detect_hotspot_ip  # Importamos la función a probar
from unittest.mock import patch, MagicMock
from server import app


# =================== PRUEBAS BLOQUE 2 ================================ #
class TestDetectHotspotIP(unittest.TestCase):
    """Pruebas para la función detect_hotspot_ip()"""

    # Caso 1: IP típica del Hotspot
    @patch('subprocess.check_output')
    def test_typical_hotspot_ip(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.137.1
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.137.1")

    # Caso 2: Otra IP privada (sin la típica)
    @patch('subprocess.check_output')
    def test_other_private_ip(self, mock_check_output):
        # Cambiamos el orden: la primera IP privada es 192.168.1.10
        mock_check_output.return_value = """
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 10.0.0.5
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.1.10")

    # Caso 3: Múltiples IPs privadas (devuelve la primera encontrada)
    @patch('subprocess.check_output')
    def test_multiple_private_ips_first(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 172.16.0.1
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        """
        self.assertEqual(detect_hotspot_ip(), "172.16.0.1")

    # Caso 5: Sin IP privada (solo loopback y APIPA)
    @patch('subprocess.check_output')
    def test_no_private_ip(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de bucle invertido de Loopback Pseudo-Interfaz 1:
           Dirección IPv4. . . . . . . . . . . . . . : 127.0.0.1
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 169.254.12.34
        """
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    # Caso 6: CalledProcessError
    @patch('subprocess.check_output')
    def test_called_process_error(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, 'ipconfig')
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    # Caso 7: Otra excepción (genérica)
    @patch('subprocess.check_output')
    def test_other_exception(self, mock_check_output):
        mock_check_output.side_effect = Exception("Simulated error")
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    # Caso 8: Problemas de encoding (caracteres extraños, pero IP válida)
    @patch('subprocess.check_output')
    def test_encoding_issues(self, mock_check_output):
        # Simulamos una salida con caracteres no estándar (ej. tildes)
        mock_check_output.return_value = """
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.137.1
        Servicio de acceso telefónico:
           Ñandú
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.137.1")

# =================== PRUEBAS BLOQUE 3 ================================ #

class TestMonitorOutbox(unittest.TestCase):
    """Pruebas para el Bloque 3 (Monitor de outbox)"""

    def setUp(self):
        # Crear carpeta temporal para outbox
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('server.OUTBOX_FOLDER', self.temp_dir)
        self.patcher.start()
        # Resetear la cola antes de cada test (importar la variable global)
        from server import push_queue
        push_queue.clear()  # Vaciar la cola
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        self.patcher.stop()
        # Eliminar todos los archivos y subcarpetas recursivamente
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_process_outbox_empty(self):
        """Verifica que no falla si outbox está vacío."""
        from server import process_outbox
        process_outbox()  # No debe lanzar excepción
        from server import push_queue
        self.assertEqual(len(push_queue), 0)

    def test_process_outbox_single_file(self):
        """Verifica que un archivo se encola correctamente."""
        # Crear archivo de prueba
        test_file = os.path.join(self.temp_dir, 'prueba.txt')
        with open(test_file, 'wb') as f:
            f.write(b'Hola mundo')
        
        from server import process_outbox
        process_outbox()
        
        from server import push_queue
        # Verificar que se encoló
        self.assertEqual(len(push_queue), 1)
        self.assertEqual(push_queue[0]['filename'], 'prueba.txt')
        self.assertEqual(push_queue[0]['data'], b'Hola mundo')
        # Verificar que el archivo se eliminó
        self.assertFalse(os.path.exists(test_file))

    def test_process_outbox_multiple_files(self):
        """Verifica que múltiples archivos se encolan en orden."""
        # Crear varios archivos
        files = ['a.txt', 'b.txt', 'c.txt']
        for name in files:
            path = os.path.join(self.temp_dir, name)
            with open(path, 'wb') as f:
                f.write(name.encode())
        
        from server import process_outbox
        process_outbox()
        
        from server import push_queue
        # Verificar que todos se encolaron
        self.assertEqual(len(push_queue), 3)
        for i, name in enumerate(files):
            self.assertEqual(push_queue[i]['filename'], name)
            self.assertEqual(push_queue[i]['data'], name.encode())
        # Verificar que no quedan archivos
        self.assertEqual(len(os.listdir(self.temp_dir)), 0)

    def test_process_outbox_skips_directories(self):
        """Verifica que ignora subcarpetas."""
        # Crear una subcarpeta
        subdir = os.path.join(self.temp_dir, 'subcarpeta')
        os.makedirs(subdir)
        # Crear archivo en la raíz
        test_file = os.path.join(self.temp_dir, 'prueba.txt')
        with open(test_file, 'wb') as f:
            f.write(b'contenido')
        
        from server import process_outbox
        process_outbox()
        
        from server import push_queue
        # Solo debe encolar el archivo, no la carpeta
        self.assertEqual(len(push_queue), 1)
        self.assertEqual(push_queue[0]['filename'], 'prueba.txt')
        # La subcarpeta debe seguir existiendo
        self.assertTrue(os.path.exists(subdir))

# =================== PRUEBAS BLOQUE 5 ================================ #

class TestDetectHotspotIP(unittest.TestCase):
    """Pruebas para la función detect_hotspot_ip()"""

    @patch('subprocess.check_output')
    def test_typical_hotspot_ip(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.137.1
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.137.1")

    @patch('subprocess.check_output')
    def test_other_private_ip(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 10.0.0.5
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.1.10")

    @patch('subprocess.check_output')
    def test_multiple_private_ips_first(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 172.16.0.1
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.1.10
        """
        self.assertEqual(detect_hotspot_ip(), "172.16.0.1")

    @patch('subprocess.check_output')
    def test_no_private_ip(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de bucle invertido de Loopback Pseudo-Interfaz 1:
           Dirección IPv4. . . . . . . . . . . . . . : 127.0.0.1
        Adaptador de Ethernet Ethernet:
           Dirección IPv4. . . . . . . . . . . . . . : 169.254.12.34
        """
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    @patch('subprocess.check_output')
    def test_called_process_error(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, 'ipconfig')
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    @patch('subprocess.check_output')
    def test_other_exception(self, mock_check_output):
        mock_check_output.side_effect = Exception("Simulated error")
        self.assertEqual(detect_hotspot_ip(), "127.0.0.1")

    @patch('subprocess.check_output')
    def test_encoding_issues(self, mock_check_output):
        mock_check_output.return_value = """
        Adaptador de LAN inalámbrica Wi-Fi:
           Dirección IPv4. . . . . . . . . . . . . . : 192.168.137.1
        Servicio de acceso telefónico:
           Ñandú
        """
        self.assertEqual(detect_hotspot_ip(), "192.168.137.1")


class TestArranque(unittest.TestCase):
    """Pruebas para el Bloque 7 (Arranque)"""

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_carpetas_creadas(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        mock_detect_ip.return_value = "192.168.1.100"
        main()
        self.assertEqual(mock_makedirs.call_count, 2)
        mock_makedirs.assert_any_call('uploads', exist_ok=True)
        mock_makedirs.assert_any_call('outbox', exist_ok=True)

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_error_crear_carpetas(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        mock_detect_ip.return_value = "192.168.1.100"
        mock_makedirs.side_effect = PermissionError("Permiso denegado")
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_any_call("❌ Error al crear las carpetas: Permiso denegado")

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_ip_impresa_en_consola(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        mock_detect_ip.return_value = "192.168.1.200"
        main()
        mock_print.assert_any_call(f"🌐 Servidor listo en: http://192.168.1.200:5000")

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_app_run_llamado(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        mock_detect_ip.return_value = "192.168.1.100"
        main()
        mock_app_run.assert_called_once_with(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=False
        )


class TestControladores(unittest.TestCase):
    """Pruebas para el Bloque 5 (rutas / y /upload)"""

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('server.UPLOAD_FOLDER', self.temp_dir)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)

    def test_index_returns_html(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        # Decodificar la respuesta para buscar texto con tildes
        content = response.data.decode('utf-8')
        self.assertIn('Transferencia Móvil', content)
        self.assertIn('<form id="uploadForm"', content)

    def test_upload_no_file(self):
        response = self.app.post('/upload', data={})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['ok'])
        self.assertIn('No se envió ningún archivo', data['error'])

    def test_upload_empty_filename(self):
        data = {'file': (b'', '')}
        response = self.app.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['ok'])
        self.assertIn('Nombre de archivo vacío', data['error'])

    def test_upload_success(self):
        test_content = b'Hola mundo'
        test_filename = 'prueba.txt'
        # Crear un objeto BytesIO que simule un archivo
        file_data = (io.BytesIO(test_content), test_filename)
        data = {
            'file': file_data
        }
        response = self.app.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        data_json = response.get_json()
        self.assertTrue(data_json['ok'])
        self.assertEqual(data_json['filename'], 'prueba.txt')
        # Verificar que el archivo se guardó
        saved_path = os.path.join(self.temp_dir, 'prueba.txt')
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

    def test_upload_rename_if_exists(self):
        # Crear archivo existente
        existing_path = os.path.join(self.temp_dir, 'prueba.txt')
        with open(existing_path, 'wb') as f:
            f.write(b'contenido original')
        
        test_content = b'Nuevo contenido'
        test_filename = 'prueba.txt'
        file_data = (io.BytesIO(test_content), test_filename)
        data = {
            'file': file_data
        }
        response = self.app.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        data_json = response.get_json()
        self.assertTrue(data_json['ok'])
        self.assertEqual(data_json['filename'], 'prueba(1).txt')
        # Verificar que ambos archivos existen
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, 'prueba.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, 'prueba(1).txt')))

# =================== PRUEBAS BLOQUE 7 ================================ #
class TestArranque(unittest.TestCase):
    """Pruebas para el Bloque 7 (Arranque)"""

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_carpetas_creadas(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        """Verifica que se crean las carpetas correctamente."""
        mock_detect_ip.return_value = "192.168.1.100"
        main()
        # Verificar que os.makedirs fue llamado dos veces con exist_ok=True
        self.assertEqual(mock_makedirs.call_count, 2)
        mock_makedirs.assert_any_call('uploads', exist_ok=True)
        mock_makedirs.assert_any_call('outbox', exist_ok=True)

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_error_crear_carpetas(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        """Verifica que si falla la creación de carpetas, se llama a exit(1)."""
        mock_detect_ip.return_value = "192.168.1.100"
        # Simular error en la primera llamada a makedirs
        mock_makedirs.side_effect = PermissionError("Permiso denegado")
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)
        # Verificar que se imprimió el error
        mock_print.assert_any_call("❌ Error al crear las carpetas: Permiso denegado")

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_ip_impresa_en_consola(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        """Verifica que la IP detectada aparece en la URL impresa."""
        mock_detect_ip.return_value = "192.168.1.200"
        main()
        # Buscar que se haya impreso la URL correcta
        mock_print.assert_any_call(f"🌐 Servidor listo en: http://192.168.1.200:5000")

    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_app_run_llamado(self, mock_print, mock_app_run, mock_detect_ip, mock_makedirs):
        """Verifica que app.run se llama con los parámetros correctos."""
        mock_detect_ip.return_value = "192.168.1.100"
        main()
        mock_app_run.assert_called_once_with(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=False
        )


if __name__ == '__main__':
    unittest.main()