#!/bin/sh

# condor wants to copy in the condor_dagman executable, but we
# want it to run the local one, so we give it this one...

{% if role is defined and role  and role != 'Analysis' %}
export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}_{{role}}.use
{% else %}
export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}.use
{% endif %}

exec /usr/bin/condor_dagman "$@"
