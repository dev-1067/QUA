"""Self-signed TLS certificate for serving the app over https on the local network, so phones get
a secure context (browsers only allow GPS, microphone and service workers on https)."""
from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def ensure_cert(folder: Path, ips: list[str]) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    cert_path, key_path, ips_path = folder / "cert.pem", folder / "key.pem", folder / "ips.txt"
    wanted = sorted(set(ips) | {"127.0.0.1"})
    if cert_path.exists() and key_path.exists() and ips_path.exists() and ips_path.read_text().split() == wanted:
        return cert_path, key_path
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "RecoverIQ local"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RecoverIQ demo")])
    san = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(i)) for i in wanted]
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ips_path.write_text("\n".join(wanted))
    return cert_path, key_path
