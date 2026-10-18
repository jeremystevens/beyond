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
                        patch.object(https, 'KEY', folder / 'k.pem'), patch.object(https, 'CA_CERT', folder / 'ca.pem'),
                        patch.object(https, 'CA_KEY', folder / 'ca-k.pem'),
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
        for path in (https.CERT, https.KEY, https.CA_CERT, https.CA_KEY):
            path.write_text('not a certificate')
        https.certificate()
        self.assertTrue(self.load().serial_number)

    def verify(self, leaf, name):
        """Check `leaf` the way a browser that installed the authority does (chain, names, name constraints)."""
        from cryptography.x509.verification import PolicyBuilder, Store
        ca = x509.load_pem_x509_certificate(https.authority_file().read_bytes())
        return PolicyBuilder().store(Store([ca])).build_server_verifier(name).verify(leaf, [])

    def test_trusted_through_the_authority_which_outlives_renewals(self):
        import ipaddress
        https.certificate()
        ca_serial = x509.load_pem_x509_certificate(https.CA_CERT.read_bytes()).serial_number
        for name in (x509.IPAddress(ipaddress.ip_address('192.168.1.20')), x509.DNSName('PC1')):
            self.verify(self.load(), name)
        with patch.object(https, 'names', return_value=(['127.0.0.1', '10.0.0.5'], ['PC1', 'localhost'])):
            https.certificate()                      # a new address: new server certificate…
            self.verify(self.load(), x509.IPAddress(ipaddress.ip_address('10.0.0.5')))
        self.assertEqual(x509.load_pem_x509_certificate(https.CA_CERT.read_bytes()).serial_number, ca_serial)
        # …but the same authority, so devices that installed it keep trusting BEYOND

    def test_authority_cannot_vouch_for_real_websites(self):
        """Even with its key, a certificate for a real website (or a public address) is rejected."""
        import ipaddress
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        ca, ca_key = https.authority()
        nc = ca.extensions.get_extension_for_class(x509.NameConstraints)
        self.assertTrue(nc.critical)
        now = datetime.now(timezone.utc)
        for name in (x509.DNSName('www.bank.com'), x509.IPAddress(ipaddress.ip_address('8.8.8.8'))):
            key = ec.generate_private_key(ec.SECP256R1())
            forged = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'x')]))
                      .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
                      .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=30))
                      .add_extension(x509.SubjectAlternativeName([name]), critical=False)
                      .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                                     critical=False)
                      .sign(ca_key, hashes.SHA256()))
            from cryptography.x509.verification import VerificationError
            with self.subTest(name=str(name.value)), self.assertRaises(VerificationError):
                self.verify(forged, name)

    def test_only_home_addresses_are_listed(self):
        """A VPN or public address would break the name constraints, so it's left out of the certificate."""
        self.patches.pop().stop()   # use the real names() here
        with patch.object(https.ports, 'network_addresses', return_value=[('Wi-Fi', '192.168.1.20'),
                                                                         ('VPN', '100.64.3.4'), ('Lab', '10.1.2.3')]):
            addresses, hosts = https.names()
        self.assertEqual(addresses, ['10.1.2.3', '127.0.0.1', '192.168.1.20'])
        self.assertIn('localhost', hosts)


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
