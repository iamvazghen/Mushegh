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
    """Apply both shims. Returns a note describing what happened, or ''."""
    notes = []
    if not hasattr(_sp, "sph_harm"):
        _sp.sph_harm = _missing_sph_harm
        notes.append("scipy.special.sph_harm (import-only; raises if called)")
    notes.extend(_stub_k2_fsa())
    return "; ".join(notes)


def _stub_k2_fsa() -> list[str]:
    """Let speechbrain.processing import without the k2 native extension.

    openwakeword/data.py:33 does `from speechbrain.processing.signal_processing
    import reverberate`. Importing that module walks speechbrain's whole processing
    package, which exposes `integrations.k2_fsa` as a LazyModule -- and importing
    k2_fsa does `import k2` at module level (k2_fsa/__init__.py:12).

    `k2` is a native extension with no Windows wheel: `uv pip install k2` resolves
    and downloads ~45 MB, and `import k2` then fails on a missing `_k2` module.

    `reverberate` applies room impulse responses and does not use finite-state
    machinery, so binding an importable module that refuses if touched lets the
    training path proceed — and if something ever DOES reach for FSA, it raises
    with this text instead of silently doing something else.
    """
    import sys
    import types

    if "speechbrain.integrations.k2_fsa" in sys.modules:
        return []
    try:
        import speechbrain.integrations.k2_fsa  # noqa: F401

        return []  # k2 really is present; nothing to do
    except Exception:
        pass

    mod = types.ModuleType("speechbrain.integrations.k2_fsa")

    def _refuse(*_args, **_kwargs):
        raise NotImplementedError(
            "k2 is required for finite-state operations and has no Windows build. "
            "tools/ww_shim.py stubs it so speechbrain.processing can be imported -- "
            "reverberate() does not use FSA. If you reached this, something did."
        )

    def _getattr(name):
        # Dunders must raise AttributeError, not resolve to the refusal callable.
        # A __getattr__ that answers everything makes this module look like it has
        # attributes it does not, and inspect.getmodule() then trips over a
        # function where it expected a filename -- which is exactly what happened
        # the first time this shim was written.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _refuse

    mod.__getattr__ = _getattr
    sys.modules["speechbrain.integrations.k2_fsa"] = mod
    return ["stubbed speechbrain.integrations.k2_fsa (import-only; raises if called)"]


if __name__ == "__main__":
    print(apply() or "no shim needed")