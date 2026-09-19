"""Write a self-signed certificate for the phone.

Mobile browsers only give a page the camera on a secure origin, so the backend has to serve
HTTPS even on a laptop. The certificate covers localhost and every LAN address this machine
has, so the phone can reach it by IP and accept the warning once.

Run it with:

    uv run --project backend python scripts/make_cert.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import get_settings

VALID_DAYS = 365


def local_addresses() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Every address this machine answers on, so the phone can use any of them."""
    found: set[str] = {"127.0.0.1", "::1"}
    hostname = socket.gethostname()
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            for info in socket.getaddrinfo(hostname, None, family):
                found.add(info[4][0].split("%")[0])
        except socket.gaierror:
            continue
    # A UDP connect picks the address the default route would use, with no traffic sent.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for text in sorted(found):
        try:
            addresses.append(ipaddress.ip_address(text))
        except ValueError:
            continue
    return addresses


def build_cert(cert_dir: Path, force: bool = False) -> tuple[Path, Path]:
    """Write the certificate and its key. Returns the two paths. Neither file is printed."""
    cert_path = cert_dir / "dev-cert.pem"
    key_path = cert_dir / "dev-key.pem"
    if cert_path.exists() and key_path.exists() and not force:
        return cert_path, key_path

    cert_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    hostname = socket.gethostname()
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
        x509.DNSName(f"{hostname}.local"),
    ]
    names.extend(x509.IPAddress(address) for address in local_addresses())

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BinBooks development"),
        ]
    )
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a self-signed certificate for the phone.")
    parser.add_argument("--force", action="store_true", help="Replace an existing certificate.")
    args = parser.parse_args()

    conf = get_settings()
    cert_path, key_path = build_cert(conf.cert_dir, force=args.force)
    names = ", ".join(str(a) for a in local_addresses())
    print(f"certificate ready in {cert_path.parent}")
    print(f"covers localhost and {names}")
    print(f"files: {cert_path.name} and {key_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
