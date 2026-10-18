"""Secure address for other devices (Phase 26 follow-up): python -m unittest discover -s tests -v.
Makes certificates in a temporary folder; never touches data/https."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509

from app import https


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.patches = [patch.object(https, 'FOLDER', folder), patch.object(https, 'CERT', folder / 'c.pem'),
                        patch.object(https, 'KEY', folder / 'k.pem'),
                        patch.object(https, 'names', return_value=(['127.0.0.1', '192.168.1.20'], ['PC1', 'localhost']))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def load(self):
        return x509.load_pem_x509_certificate(https.CERT.read_bytes())

    def test_covers_this_pc_and_is_not_a_ca(self):
        https.certificate()
        cert = self.load()
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        self.assertEqual({str(ip) for ip in names.get_values_for_type(x509.IPAddress)}, {'127.0.0.1', '192.168.1.20'})
        self.assertEqual(set(names.get_values_for_type(x509.DNSName)), {'PC1', 'localhost'})
        self.assertFalse(cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
        self.assertIn('BEYOND on PC1', cert.subject.rfc4514_string())
        self.assertLessEqual(cert.not_valid_after_utc - datetime.now(timezone.utc), timedelta(days=https.DAYS))

    def test_kept_while_good_and_renewed_for_a_new_address(self):
        https.certificate()
        first = self.load().serial_number
        https.certificate()
        self.assertEqual(self.load().serial_number, first)   # reused
        with patch.object(https, 'names', return_value=(['127.0.0.1', '10.0.0.5'], ['PC1', 'localhost'])):
            https.certificate()
        self.assertNotEqual(self.load().serial_number, first)   # the PC got a new address: made again

    def test_unreadable_files_are_replaced(self):
        https.FOLDER.mkdir(exist_ok=True)
        https.CERT.write_text('not a certificate')
        https.KEY.write_text('not a key')
        https.certificate()
        self.assertTrue(self.load().serial_number)


class RunAllTests(unittest.TestCase):
    def test_secure_server_stops_with_the_main_one(self):
        import beyond

        class FakeServer:
            def __init__(self, delay):
                self.delay, self.should_exit, self.stopped = delay, False, False

            async def serve(self):
                if self.delay:
                    await asyncio.sleep(self.delay)
                    return
                while not self.should_exit:
                    await asyncio.sleep(0.01)
                self.stopped = True

        main, secure = FakeServer(0.05), FakeServer(0)
        asyncio.run(asyncio.wait_for(beyond.run_all([main, secure]), 5))
        self.assertTrue(secure.stopped)


if __name__ == '__main__':
    unittest.main()
