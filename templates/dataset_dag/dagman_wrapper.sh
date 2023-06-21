#!/bin/sh

# condor wants to copy in the condor_dagman executable, but we
# want it to run the local one, so we give it this one...

# touch our transfer files so condor will copy them back
(sleep 1; touch {%for f in transfer_files%}{{f}} {%endfor%}) &

# mengel -- debug bits to get dagman submitting with token authentication
echo "\$_CONDOR_CREDS=" $_CONDOR_CREDS
echo "===="
ls -laR `pwd`
echo "===="
ls -laR $_CONDOR_CREDS
export _condor_ALL_DEBUG=D_ALL
echo "==="
printenv | grep '^_condor'

{% if role is defined and role and role != 'Analysis' %}
export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}_{{role | lower}}_{{oauth_handle}}.use
#export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}_{{role | lower}}.use
{% else %}
export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}_{{oauth_handle}}.use
#export BEARER_TOKEN_FILE=$_CONDOR_CREDS/{{group}}.use
{% endif %}

exec /usr/bin/condor_dagman "$@"
