#!/bin/sh

# condor wants to copy in the condor_dagman executable, but we
# want it to run the local one, so we give it this one...


# touch our transfer files so condor will copy them back

exec /usr/bin/condor_dagman "$@"
