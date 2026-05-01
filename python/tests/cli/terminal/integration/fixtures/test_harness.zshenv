# Runs before /etc/zsh/zshrc. Prevents compinit from prompting about
# "insecure directories" in CI where directory ownership doesn't match
# the running user.
skip_global_compinit=1
