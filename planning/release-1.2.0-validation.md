# Release 1.2.0 validation

Release procedure: docs/RELEASING.md. Includes Phases 49–53. Root VERSION is changed only after publication/download verification.

Pending: full Windows/Python 3.14 and browser CI; artifact build; isolated 1.1.0 ZIP installation with its own environment; Update now through local assets; data preservation and version checks; publication and download/hash verification; release signal.

A prior main push (40167242771) failed in the Windows job-object fixture: it read child.pid between file creation and PID content publication. The fixture now publishes the PID atomically and verifies actual child exit with a bounded wait (retained Windows handles need not imply a running process). Parent/child cleanup assertions remain active. This is a test-readiness fix; production process ownership is unchanged.
