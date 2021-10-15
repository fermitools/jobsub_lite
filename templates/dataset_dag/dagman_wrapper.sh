#!/bin/sh

# condor wants to copy in the condor_dagman executable, but we
# want it to run the local one, so we give it this one...

export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}.use

exec /usr/bin/condor_dagman "$@"
