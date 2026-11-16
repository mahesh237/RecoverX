# Architecture

The MVP separates UI (`ui/`), image validation (`services/`), engine integration (`engines/`), and shared runtime services (`core/`). The PhotoRec adapter owns executable discovery, source/destination validation, documented command construction, process launch, cancellation, and actual output discovery. A `QThread` worker runs the blocking process outside the GUI thread. Scan percentage is indeterminate because PhotoRec does not provide a stable machine-readable percentage through this interface.

The scripted invocation follows CGSecurity's documented `/cmd` and `/d` interface. RecoverX currently scans whole images using PhotoRec's default format set. Integration CI installs the system PhotoRec package and carves a JPEG from a disposable image while writing to a separate tmpfs. Results are filesystem entries actually created by PhotoRec; format integrity checks and preview remain future work.
