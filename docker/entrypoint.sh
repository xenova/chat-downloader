#!/bin/sh

# Add local user and group
# Either use the uid and gid if passed in at runtime or
# fallback to 9001

USER_ID=${uid:-9001}
GROUP_ID=${gid:-9001}

echo "UID : $USER_ID \nGID : $GROUP_ID"

chown -R $USER_ID:$GROUP_ID /home/script

exec gosu $USER_ID "$@"