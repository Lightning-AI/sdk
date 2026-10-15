"""Live job progress: the tracker behind ``lightning job watch``.

``tracker`` holds the pure progress rules, ``store`` the on-disk state shared with other tools
(a status line, a Monitor), and ``watch`` the watcher that feeds a job's log stream into both.
"""
