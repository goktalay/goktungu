"""GOKTUNGU istemci paketleri icin bagimliliksiz Ed25519 imza dogrulamasi.

Guncelleme anahtari pakete gomuludur. Bu modul yalniz dogrulama yapar;
gizli anahtar veya imzalama yetenegi tasimaz.
"""
import base64
import hashlib

ACIK_ANAHTAR_B64 = "ZDnJD1vKUwNUkfAx84JcGoRHsU3Vwyh4s/CHzZXCVRo="
_q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _ters(x):
    return pow(x, _q - 2, _q)


_d = -121665 * _ters(121666) % _q
_I = pow(2, (_q + 3) // 8, _q)


def _x_geri_kazan(y):
    xx = (y * y - 1) * _ters(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    return x if x % 2 == 0 else _q - x


_By = 4 * _ters(5) % _q
_Bx = _x_geri_kazan(_By)
_B = (_Bx % _q, _By % _q, 1, _Bx * _By % _q)


def _topla(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _q
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _q
    C = 2 * P[3] * Q[3] * _d % _q
    D = 2 * P[2] * Q[2] % _q
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _q, G * H % _q, F * G % _q, E * H % _q)


def _ikile(P):
    A = P[0] * P[0] % _q
    B = P[1] * P[1] % _q
    C = 2 * P[2] * P[2] % _q
    H = A + B
    E = H - (P[0] + P[1]) ** 2 % _q
    G = A - B
    F = C + G
    return (E * F % _q, G * H % _q, F * G % _q, E * H % _q)


def _carp(P, e):
    if e == 0:
        return (0, 1, 1, 0)
    Q = _carp(P, e // 2)
    Q = _ikile(Q)
    return _topla(Q, P) if e & 1 else Q


def _esit(P, Q):
    return ((P[0] * Q[2] - Q[0] * P[2]) % _q == 0 and
            (P[1] * Q[2] - Q[1] * P[2]) % _q == 0)


def _coz(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    isaret = y >> 255
    y &= (1 << 255) - 1
    if y >= _q:
        return None
    xx = (y * y - 1) * _ters(_d * y * y + 1) % _q
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if (x * x - xx) % _q != 0:
        return None
    if x % 2 != isaret:
        x = _q - x
    return (x, y, 1, x * y % _q)


def _saf_dogrula(acik, imza, ileti):
    if len(imza) != 64 or len(acik) != 32:
        return False
    R, A = _coz(imza[:32]), _coz(acik)
    if R is None or A is None:
        return False
    S = int.from_bytes(imza[32:], "little")
    if S >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(imza[:32] + acik + ileti).digest(), "little") % _L
    return _esit(_carp(_B, S), _topla(R, _carp(A, k)))


def dogrula(ileti, imza_b64):
    """Gomulu acik anahtarla standart Base64 Ed25519 imzasini dogrular."""
    try:
        imza = base64.b64decode(str(imza_b64 or ""), validate=True)
        acik = base64.b64decode(ACIK_ANAHTAR_B64, validate=True)
    except Exception:
        return False
    if len(imza) != 64 or len(acik) != 32:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            Ed25519PublicKey.from_public_bytes(acik).verify(imza, ileti)
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False
    except ImportError:
        return _saf_dogrula(acik, imza, ileti)
