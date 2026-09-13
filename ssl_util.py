"""Create a local self-signed TLS certificate for phone camera / LAN HTTPS."""
from __future__ import annotations

import datetime as dt
import ipaddress
import os
import socket
from pathlib import Path


def cert_paths(root: str | Path | None = None) -> tuple[Path, Path]:
    base = Path(root or os.path.dirname(os.path.abspath(__file__))) / "certs"
    base.mkdir(parents=True, exist_ok=True)
    return base / "cert.pem", base / "key.pem"


def local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips)


def ensure_ssl_certs(root: str | Path | None = None) -> tuple[str, str]:
    """Return (certfile, keyfile), generating them if missing."""
    cert_file, key_file = cert_paths(root)
    if cert_file.is_file() and key_file.is_file():
        return str(cert_file), str(key_file)

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as e:
        raise RuntimeError(
            "Install cryptography for HTTPS: pip install cryptography"
        ) from e

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BillingPro Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, "BillingPro LAN"),
    ])
    alt_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName("*.local"),
    ]
    for ip in local_ips():
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.utcnow() - dt.timedelta(minutes=1))
        .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_file), str(key_file)


if __name__ == "__main__":
    c, k = ensure_ssl_certs()
    print("cert:", c)
    print("key:", k)
    print("IPs:", ", ".join(local_ips()))
