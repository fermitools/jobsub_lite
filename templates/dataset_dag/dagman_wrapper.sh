#!/bin/sh

# condor wants to copy in the condor_dagman executable, but we
# want it to run the local one, so we give it this one...

{% if role and role != 'Analysis' %}
export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}_{{role}}.use
{% else %}
export BEARER_TOKEN_FILE=$PWD/.condor_creds/{{group}}.use
{% endif %}
export BEARER_TOKEN=`cat "$BEARER_TOKEN_FILE"`

exec /usr/bin/condor_dagman "$@"
