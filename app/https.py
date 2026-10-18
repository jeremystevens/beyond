"""A secure (https://) address for other devices on your network, so their browsers allow the microphone.

Browsers only let a page use the microphone (and some other features) on https:// pages, or on the PC's own
http://127.0.0.1. So when "Let other devices on my network use BEYOND" is on, beyond.py also serves BEYOND over
HTTPS on the next port (7771 by default), with a certificate BEYOND makes for itself on this PC.

The certificate is "self-signed": no company vouches for it, so each other device's browser shows a one-time
warning ("Your connection isn't private") the first time; choose Advanced → Continue. Everything still stays on your
own network. It is stored in data/https/ (git-ignored), covers this PC's network addresses and name, and is made
again automatically when those change or it is close to expiring.
"""
import ipaddress
import socket
from datetime import datetime, timedelta, timezone

from app import config, ports

FOLDER = config.DATA_DIR / 'https'
CERT = FOLDER / 'beyond-cert.pem'
KEY = FOLDER / 'beyond-key.pem'
DAYS = 397                 # browsers accept at most about 13 months for a certificate
RENEW_DAYS = 30


def names():
    """What the certificate must cover: (IP addresses, host names)."""
    addresses = {'127.0.0.1'} | {ip for _, ip in ports.network_addresses()}
    hosts = {'localhost'}
    try:
        hosts.add(socket.gethostname())
    except OSError:
        pass
    return sorted(addresses), sorted(h for h in hosts if h)


def _still_good(addresses, hosts):
    """True if the saved certificate exists, covers these names, and isn't close to expiring."""
    if not CERT.exists() or not KEY.exists():
        return False
    try:
        from cryptography import x509
        cert = x509.load_pem_x509_certificate(CERT.read_bytes())
        covered = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have_ips = {str(ip) for ip in covered.get_values_for_type(x509.IPAddress)}
        have_hosts = set(covered.get_values_for_type(x509.DNSName))
    except (ValueError, OSError, x509.ExtensionNotFound):
        return False
    fresh = cert.not_valid_after_utc - datetime.now(timezone.utc) > timedelta(days=RENEW_DAYS)
    return fresh and set(addresses) <= have_ips and set(hosts) <= have_hosts


def certificate():
    """(certificate file, key file), making a new pair first if needed. Raises ImportError if `cryptography` is
    missing."""
    addresses, hosts = names()
    if _still_good(addresses, hosts):
        return CERT, KEY
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    pc = next((h for h in hosts if h != 'localhost'), 'this PC')
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f'BEYOND on {pc}'),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'BEYOND (self-signed, this PC only)')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=DAYS))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts] +
                                                       [x509.IPAddress(ipaddress.ip_address(a)) for a in addresses]),
                           critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    FOLDER.mkdir(parents=True, exist_ok=True)
    KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return CERT, KEY
