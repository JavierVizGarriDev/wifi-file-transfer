import unittest
import subprocess
from server import main
from unittest.mock import patch, MagicMock
from server import detect_hotspot_ip  # Importamos la función a probar

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