import unittest
import subprocess
import os
import tempfile
import io
from unittest.mock import patch

from server import (
    main,
    detect_hotspot_ip,
    app,
    process_outbox,
    push_queue,
    UPLOAD_FOLDER,
    OUTBOX_FOLDER,
)


# =================== PRUEBAS BLOQUE 2 ================================ #
class TestDetectHotspotIP(unittest.TestCase):
    """Pruebas para la función detect_hotspot_ip()."""

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


# =================== PRUEBAS BLOQUE 3 ================================ #
class TestMonitorOutbox(unittest.TestCase):
    """Pruebas para el monitor de outbox (process_outbox)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('server.OUTBOX_FOLDER', self.temp_dir)
        self.patcher.start()
        push_queue.clear()
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        self.patcher.stop()
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_process_outbox_empty(self):
        """Verifica que no falla si outbox está vacío."""
        process_outbox()
        self.assertEqual(len(push_queue), 0)

    def test_process_outbox_single_file(self):
        """Verifica que un archivo se encola y se purga del disco."""
        test_file = os.path.join(self.temp_dir, 'prueba.txt')
        with open(test_file, 'wb') as f:
            f.write(b'Hola mundo')

        process_outbox()

        self.assertEqual(len(push_queue), 1)
        self.assertEqual(push_queue[0]['filename'], 'prueba.txt')
        self.assertEqual(push_queue[0]['data'], b'Hola mundo')
        self.assertFalse(os.path.exists(test_file))

    def test_process_outbox_multiple_files(self):
        """Verifica que múltiples archivos se encolan en orden."""
        files = ['a.txt', 'b.txt', 'c.txt']
        for name in files:
            path = os.path.join(self.temp_dir, name)
            with open(path, 'wb') as f:
                f.write(name.encode())

        process_outbox()

        self.assertEqual(len(push_queue), 3)
        for i, name in enumerate(files):
            self.assertEqual(push_queue[i]['filename'], name)
            self.assertEqual(push_queue[i]['data'], name.encode())
        self.assertEqual(len(os.listdir(self.temp_dir)), 0)

    def test_process_outbox_skips_directories(self):
        """Verifica que ignora subcarpetas."""
        subdir = os.path.join(self.temp_dir, 'subcarpeta')
        os.makedirs(subdir)
        test_file = os.path.join(self.temp_dir, 'prueba.txt')
        with open(test_file, 'wb') as f:
            f.write(b'contenido')

        process_outbox()

        self.assertEqual(len(push_queue), 1)
        self.assertEqual(push_queue[0]['filename'], 'prueba.txt')
        self.assertTrue(os.path.exists(subdir))


# =================== PRUEBAS BLOQUE 5 ================================ #
class TestControladores(unittest.TestCase):
    """Pruebas para las rutas / y /upload."""

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
        file_data = (io.BytesIO(test_content), test_filename)
        data = {'file': file_data}

        response = self.app.post('/upload', data=data, content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200)
        data_json = response.get_json()
        self.assertTrue(data_json['ok'])
        self.assertEqual(data_json['filename'], 'prueba.txt')

        saved_path = os.path.join(self.temp_dir, 'prueba.txt')
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, 'rb') as f:
            self.assertEqual(f.read(), test_content)

    def test_upload_rename_if_exists(self):
        existing_path = os.path.join(self.temp_dir, 'prueba.txt')
        with open(existing_path, 'wb') as f:
            f.write(b'contenido original')

        test_content = b'Nuevo contenido'
        file_data = (io.BytesIO(test_content), 'prueba.txt')
        data = {'file': file_data}

        response = self.app.post('/upload', data=data, content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200)
        data_json = response.get_json()
        self.assertTrue(data_json['ok'])
        self.assertEqual(data_json['filename'], 'prueba(1).txt')
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, 'prueba.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, 'prueba(1).txt')))


# =================== PRUEBAS BLOQUE 7 ================================ #
class TestArranque(unittest.TestCase):
    """Pruebas para la función main() (arranque del servidor)."""

    @patch('server.os.startfile', create=True)
    @patch('server.generate_qr')
    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_carpetas_creadas(
        self, mock_print, mock_app_run, mock_detect_ip,
        mock_makedirs, mock_generate_qr, mock_startfile
    ):
        """Verifica que se crean las tres carpetas del servidor."""
        mock_detect_ip.return_value = "192.168.1.100"

        main()

        self.assertEqual(mock_makedirs.call_count, 3)
        mock_makedirs.assert_any_call(UPLOAD_FOLDER, exist_ok=True)
        mock_makedirs.assert_any_call(OUTBOX_FOLDER, exist_ok=True)
        mock_makedirs.assert_any_call('qr', exist_ok=True)

    @patch('server.os.startfile', create=True)
    @patch('server.generate_qr')
    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_error_crear_carpetas(
        self, mock_print, mock_app_run, mock_detect_ip,
        mock_makedirs, mock_generate_qr, mock_startfile
    ):
        """Verifica que si falla la creación de carpetas, se llama a exit(1)."""
        mock_detect_ip.return_value = "192.168.1.100"
        mock_makedirs.side_effect = PermissionError("Permiso denegado")

        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_any_call("❌ Error al crear las carpetas: Permiso denegado")

    @patch('server.os.startfile', create=True)
    @patch('server.generate_qr')
    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_ip_impresa_en_consola(
        self, mock_print, mock_app_run, mock_detect_ip,
        mock_makedirs, mock_generate_qr, mock_startfile
    ):
        """Verifica que la IP detectada aparece en la URL impresa."""
        mock_detect_ip.return_value = "192.168.1.200"

        main()

        mock_print.assert_any_call("🌐 Servidor listo en: http://192.168.1.200:5000")

    @patch('server.os.startfile', create=True)
    @patch('server.generate_qr')
    @patch('server.os.makedirs')
    @patch('server.detect_hotspot_ip')
    @patch('server.app.run')
    @patch('builtins.print')
    def test_app_run_llamado(
        self, mock_print, mock_app_run, mock_detect_ip,
        mock_makedirs, mock_generate_qr, mock_startfile
    ):
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