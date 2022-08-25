#! /bin/bash

tmux kill-session -t avalon &>/dev/null
tmux new -s avalon -d
tmux new-window -t avalon
tmux split-pane -t avalon:1.0
tmux split-pane -t avalon:1.1 -h
tmux split-pane -t avalon:1.0 -h
tmux split-pane -t avalon:1.3 -h
tmux split-pane -t avalon:1.2 -h
tmux split-pane -t avalon:1.1 -h
tmux split-pane -t avalon:1.0 -h
tmux send-keys -t avalon:0 "./avalon_cli.py" Enter
until tmux capture-pane -t avalon:0 -p | grep -q "Waiting"; do
    sleep .2
done
for i in $(seq 0 7); do
    tmux send-keys -t avalon:1.$i "./avalon_cli.py @player$i" Enter
done
tmux a -t avalon
