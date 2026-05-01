# Test harness .zshrc — deterministic prompt + lightningterminal.rc for command tracking.
# Copied into a pseudo-home by the test fixture. In production, the studio's
# .zshrc sources lightningterminal.rc instead.

# Optional MOTD for testing tput scroll region reset behaviour.
# LIGHTNING_TERMINAL_TEST_MOTD=before — MOTD before lightningterminal.rc (before tput csr)
# LIGHTNING_TERMINAL_TEST_MOTD=after  — MOTD after lightningterminal.rc (after tput csr)
if [ "${LIGHTNING_TERMINAL_TEST_MOTD:-}" = "before" ]; then
    cat <<-EOF
	To run a command as administrator (user "root"), use "sudo <command>".
	See "man sudo_root" for details.

	EOF
fi

PROMPT='$ '
source "${LIGHTNING_TERMINAL_RC_PATH}"

if [ "${LIGHTNING_TERMINAL_TEST_MOTD:-}" = "after" ]; then
    echo "Welcome to Lightning Studios"
    echo "Documentation: https://docs.example.com"
    echo ""
fi

# Canary: this runs during shell init, AFTER lightningterminal.rc is sourced.
# If the deferred hook activation is working, this should NOT appear
# as last_command. If it does, the hook is firing too early.
INIT_CANARY_SHOULD_NOT_APPEAR_IN_LAST_COMMAND=1 || true
