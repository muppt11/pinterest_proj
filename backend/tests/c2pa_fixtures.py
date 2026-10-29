"""Test-only Content Credentials: a throwaway CA + signer, and helpers to sign JPEGs.

The certificates are generated fresh per test session and are not on any C2PA trust list, so readers
report "signer not on a trust list" while the signature itself validates.
"""

import datetime
import io
import json
from functools import lru_cache

import c2pa
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from PIL import Image

IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"
DOCUMENT_SIGNING = x509.ObjectIdentifier("1.3.6.1.5.5.7.3.36")
C2PA_CLAIM_SIGNING = x509.ObjectIdentifier("1.3.6.1.4.1.62558.2.1")


def _usage(sign_certs: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=not sign_certs, content_commitment=False, key_encipherment=False, data_encipherment=False,
        key_agreement=False, key_cert_sign=sign_certs, crl_sign=sign_certs, encipher_only=False, decipher_only=False,
    )


@lru_cache(maxsize=1)
def signer_material() -> tuple[bytes, bytes]:
    """(PEM certificate chain, PEM private key) for a C2PA-compliant test signer."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MoodBoards Test CA"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MoodBoards Tests")])
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(_usage(sign_certs=True), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MoodBoards Test Signer"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MoodBoards Tests")])
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(ca_name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_usage(sign_certs=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION, DOCUMENT_SIGNING, C2PA_CLAIM_SIGNING]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    chain = cert.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    pkey = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return chain, pkey


def jpeg_bytes(color: tuple[int, int, int] = (200, 120, 160), exif: Image.Exif | None = None, xmp: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    kwargs = {}
    if exif is not None:
        kwargs["exif"] = exif.tobytes()
    if xmp is not None:
        kwargs["xmp"] = xmp
    Image.new("RGB", (64, 64), color).save(buf, format="JPEG", **kwargs)
    return buf.getvalue()


def sign_jpeg(data: bytes, source_type: str) -> bytes:
    """Embed a signed C2PA manifest whose c2pa.created action declares `source_type`."""
    chain, pkey = signer_material()
    manifest = {
        "claim_generator_info": [{"name": "moodboards-tests", "version": "1.0"}],
        "title": "fixture.jpg",
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created", "digitalSourceType": IPTC + source_type}]}}],
    }
    signer = c2pa.Signer.from_info(c2pa.C2paSignerInfo(b"es256", chain, pkey, None))
    out = io.BytesIO()
    c2pa.Builder(json.dumps(manifest)).sign(signer, "image/jpeg", io.BytesIO(data), out)
    return out.getvalue()


def iptc_xmp(source_type: str) -> bytes:
    return (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        b'Iptc4xmpExt:DigitalSourceType="' + (IPTC + source_type).encode() + b'"/></rdf:RDF></x:xmpmeta>'
    )
