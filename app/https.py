"""A secure (https://) address for other devices on your network, so their browsers allow the microphone.

Browsers only let a page use the microphone (and some other features) on https:// pages, or on the PC's own
http://127.0.0.1. So when "Let other devices on my network use BEYOND" is on, beyond.py also serves BEYOND over
HTTPS on the next port (7771 by default), with certificates BEYOND makes for itself on this PC:

- **BEYOND's certificate authority** ("BEYOND on <this PC>", valid 10 years). Installing it on another device
  (Settings → Download certificate) makes that device trust BEYOND, so the browser warning goes away for good. It
  is restricted with "name constraints" to home-network addresses (10.x, 172.16–31.x, 192.168.x, 127.x) and this
  PC's own name, so even if its key were copied it could never vouch for real websites.
- **The server certificate**, signed by it, covering this PC's network addresses and name. It is made again
  automatically when those change or it nears expiry; devices that installed the authority keep trusting it.

Without the authority installed, a device's browser shows a one-time warning ("Your connection isn't private");
choose Advanced → Continue. Everything stays on your own network. All files are in data/https/ (git-ignored).
"""
import ipaddress
import socket
from datetime import datetime, timedelta, timezone

from app import config, ports

FOLDER = config.DATA_DIR / 'https'
CA_CERT = FOLDER / 'beyond-ca.pem'
CA_KEY = FOLDER / 'beyond-ca-key.pem'
CERT = FOLDER / 'beyond-cert.pem'
KEY = FOLDER / 'beyond-key.pem'
CA_DAYS = 3650             # the authority you install: ten years
DAYS = 397                 # the server certificate: browsers accept at most about 13 months
RENEW_DAYS = 30
HOME_NETWORKS = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8')


def _home(ip):
    """True for addresses the authority may vouch for (home-network ranges)."""
    return any(ipaddress.ip_address(ip) in ipaddress.ip_network(n) for n in HOME_NETWORKS)


def names():
    """What the server certificate must cover: (IP addresses, host names). Only home-network addresses: listing any
    other (e.g. a VPN address) would break the authority's name constraints and browsers would reject it."""
    addresses = {'127.0.0.1'} | {ip for _, ip in ports.network_addresses() if _home(ip)}
    hosts = {'localhost'}
    try:
        hosts.add(socket.gethostname())
    except OSError:
        pass
    return sorted(addresses), sorted(h for h in hosts if h)


def _pc(hosts):
    return next((h for h in hosts if h != 'localhost'), 'this PC')


def _load(cert_path, key_path):
    """(certificate, key) from files, or None if missing or unreadable."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    try:
        return (x509.load_pem_x509_certificate(cert_path.read_bytes()),
                serialization.load_pem_private_key(key_path.read_bytes(), password=None))
    except (OSError, ValueError, TypeError):
        return None


def _save(cert, key, cert_path, key_path):
    from cryptography.hazmat.primitives import serialization
    FOLDER.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _fresh(cert, days=RENEW_DAYS):
    return cert.not_valid_after_utc - datetime.now(timezone.utc) > timedelta(days=days)


def _allowed_hosts(ca):
    """The host names the authority may vouch for (from its name constraints)."""
    from cryptography import x509
    try:
        limits = ca.extensions.get_extension_for_class(x509.NameConstraints).value
    except x509.ExtensionNotFound:
        return set()
    return {n.value.lower() for n in limits.permitted_subtrees or [] if isinstance(n, x509.DNSName)}


def authority():
    """(certificate, key) of BEYOND's certificate authority, made first if needed (or if this PC was renamed)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    _, hosts = names()
    found = _load(CA_CERT, CA_KEY)
    if found and _fresh(found[0], 365) and {h.lower() for h in hosts} <= _allowed_hosts(found[0]):
        return found
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f'BEYOND on {_pc(hosts)}'),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'BEYOND (this PC only, home network only)')])
    now = datetime.now(timezone.utc)
    permitted = [x509.DNSName(h) for h in hosts] + [x509.IPAddress(ipaddress.ip_network(n)) for n in HOME_NETWORKS]
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    _save(cert, key, CA_CERT, CA_KEY)
    return cert, key


def _still_good(cert, ca, addresses, hosts):
    """True if the server certificate is signed by the current authority, covers these names and isn't expiring."""
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    try:
        cert.verify_directly_issued_by(ca)   # e.g. an older self-signed one, or one from a previous authority
        covered = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (InvalidSignature, ValueError, TypeError, x509.ExtensionNotFound):
        return False
    have_ips = {str(ip) for ip in covered.get_values_for_type(x509.IPAddress)}
    have_hosts = set(covered.get_values_for_type(x509.DNSName))
    return _fresh(cert) and set(addresses) <= have_ips and set(hosts) <= have_hosts


def certificate():
    """(server certificate file, key file), making a new pair (and the authority) first if needed. Raises
    ImportError if `cryptography` is missing."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    ca, ca_key = authority()
    addresses, hosts = names()
    found = _load(CERT, KEY)
    if found and _still_good(found[0], ca, addresses, hosts):
        return CERT, KEY
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f'BEYOND on {_pc(hosts)}')]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(min(now + timedelta(days=DAYS), ca.not_valid_after_utc))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts] +
                                                       [x509.IPAddress(ipaddress.ip_address(a)) for a in addresses]),
                           critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _save(cert, key, CERT, KEY)
    return CERT, KEY


def authority_file():
    """The authority's certificate (public, safe to share) for "Download certificate"; made first if needed."""
    authority()
    return CA_CERT
