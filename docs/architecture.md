# Architecture

The MVP separates UI (`ui/`), image validation (`services/`), engine integration (`engines/`), and shared runtime services (`core/`). The PhotoRec adapter owns availability detection and input validation. It currently refuses to launch scans because a safe and verified Windows CLI invocation has not been established. This boundary prevents UI code from guessing engine-specific behavior.

The next integration step is to pin and test a supported TestDisk release against disposable image fixtures, confirm its CLI options and output semantics, then implement a cancellable `QProcess` worker that parses genuine output. Results should have a common model and remain separate from engine-specific output parsing.
