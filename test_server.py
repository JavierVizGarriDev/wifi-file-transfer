import unittest
import subprocess
from unittest.mock import patch, MagicMock
from server import detect_hotspot_ip  # Importamos la función a probar


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


if __name__ == '__main__':
    unittest.main()