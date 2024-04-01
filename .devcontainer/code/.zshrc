# Basic zsh configuration

# Path to your oh-my-zsh installation.
export ZSH="/home/vscode/.oh-my-zsh"

# Theme
ZSH_THEME="gentoo"

# Auto update if required
zstyle ':omz:update' mode auto

# Auto update every 90 days
zstyle ':omz:update' frequency 90

# Enable additional plugins
plugins=(git conda-zsh-completion poetry)

# Source oh-my-zsh
source $ZSH/oh-my-zsh.sh

# Enable completion
autoload -U compinit && compinit

# Add pipx autocompletion
eval "$(register-python-argcomplete pipx)"

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/vscode/conda/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/vscode/conda/etc/profile.d/conda.sh" ]; then
        . "/home/vscode/conda/etc/profile.d/conda.sh"
    else
        export PATH="/home/vscode/conda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

# Use conda environment by default
conda activate exacheck

# Add useful aliases
## Testing related
alias pytest-html="pytest --html=/code/pytest-report.html --self-contained-html"
