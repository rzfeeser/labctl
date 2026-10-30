#!/bin/bash

# Download the repository.
git clone https://github.com/rzfeeser/labctl.git ~/labctl

# Install the program and catalog together.
mkdir -p ~/.local/share/labctl ~/.local/bin
install -m 755 ~/labctl/labctl.py ~/.local/share/labctl/labctl.py
install -m 644 ~/labctl/actions.json ~/.local/share/labctl/actions.json

# Preserve an existing personal labctl command.
if [ -e ~/.local/bin/labctl ] || [ -L ~/.local/bin/labctl ]; then
    mv ~/.local/bin/labctl ~/.local/bin/labctl.backup-$(date +%s)
fi

# Put the command on PATH.
ln -s ~/.local/share/labctl/labctl.py ~/.local/bin/labctl
export PATH="$HOME/.local/bin:$PATH"
grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc ||
    printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> ~/.bashrc
hash -r

# Open the usage guide.
labctl help
