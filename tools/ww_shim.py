"""Import-only shim that lets `acoustics` load on SciPy >= 1.15.

    openwakeword.train -> openwakeword.data -> import acoustics   (data.py:36)
    acoustics/__init__ -> acoustics.directivity -> from scipy.special import sph_harm

SciPy removed `sph_harm` in 1.15; it is now `sph_harm_y`, with the arguments
in the other order — (n, m, theta, phi) against the old (m, n, theta, phi). This
venv is on 1.17.x, so the import raises and `openwakeword.train` cannot load.

Nothing on the wake-word training path ever CALLS sph_harm. The only thing
openwakeword uses from acoustics is `acoustics.generator.noise(...)`, for
coloured-noise augmentation (openwakeword/data.py:434). The broken function is in
`directivity`, which is imported and never invoked.

So this binds a name that exists and RAISES when used. Aliasing sph_harm to
sph_harm_y would have "worked" and every result would have been silently wrong,
with degree and mode swapped. A shim that refuses is honest; one that guesses is
not — and if a future code path does call it, the error names the cause instead
of poisoning a model with wrong room acoustics.

Import this module (or call apply()) in EVERY process that imports
openwakeword.train, including subprocesses: the patch lives in `scipy.special` at
runtime and nothing is written to site-packages.

    from ww_shim import apply; apply()
"""

from __future__ import annotations

import scipy.special as _sp


def _missing_sph_harm(*_args, **_kwargs):
    raise NotImplementedError(
        "scipy.special.sph_harm was removed in SciPy 1.15. The wake-word "
        "training path never calls it (only acoustics.generator.noise is used), "
        "so tools/ww_shim.py exists solely to let `acoustics` import. If you are "
        "reading this, something started using acoustics.directivity and it "
        "needs scipy.special.sph_harm_y with (n, m, theta, phi) instead."
    )


def apply() -> str:
    """Patch if needed. Returns a note describing what happened, or ''."""
    if hasattr(_sp, "sph_harm"):
        return ""
    _sp.sph_harm = _missing_sph_harm
    return "shimmed scipy.special.sph_harm (import-only; raises if called)"


if __name__ == "__main__":
    print(apply() or "no shim needed")